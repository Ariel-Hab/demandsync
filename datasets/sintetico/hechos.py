"""Arma las tablas de hechos (esquema de `motor.datos.diccionario`) a partir de la
simulación de demanda + precios. La agregación cliente×producto → producto es la misma
que el ETL de R1 tiene que reproducir a partir de los renglones de venta (ADR-009)."""

import numpy as np
import pandas as pd

from . import parametros as P
from .catalogo import generar_clientes, generar_productos
from .demanda import repartir_entre_clientes, simular_serie_producto
from .precios import indice_inflacion

MESES = pd.date_range(P.PRIMER_MES, periods=P.N_MESES, freq="MS")


def generar_todo(
    rng: np.random.Generator, n_productos: int = P.N_PRODUCTOS, n_clientes: int = P.N_CLIENTES
) -> tuple[dict, dict, pd.DataFrame]:
    """Devuelve (tablas del diccionario T0.3, series de producto por id, catálogo de productos)."""
    productos = generar_productos(rng, n_productos)
    clientes = generar_clientes(rng, n_clientes)
    indice = indice_inflacion(rng, P.N_MESES)

    series_producto = {}
    detalle_filas = []
    for _, prod in productos.iterrows():
        serie = simular_serie_producto(
            rng,
            prod["arquetipo"],
            prod["tamanio_base"],
            prod["sin_ancla_propia"],
            mes_alta=int(prod["mes_alta"]),
            mes_baja=int(prod["mes_baja"]),
        )
        series_producto[int(prod["id_producto"])] = serie

        detalle = repartir_entre_clientes(rng, serie, clientes, prod["arquetipo"])
        if detalle.empty:
            continue
        detalle["id_producto"] = prod["id_producto"]
        precio_lista_mes = prod["precio_base"] * indice
        detalle["precio_lista"] = precio_lista_mes[detalle["mes_idx"].to_numpy()]
        detalle_filas.append(detalle)

    detalle = pd.concat(detalle_filas, ignore_index=True)
    descuento_por_cliente = clientes.set_index("id_cliente")["descuento"]
    detalle["descuento"] = detalle["id_cliente"].map(descuento_por_cliente)
    detalle["precio_efectivo"] = detalle["precio_lista"] * (1 - detalle["descuento"])
    detalle["revenue"] = detalle["unidades"] * detalle["precio_efectivo"]
    detalle["anio_mes"] = MESES[detalle["mes_idx"].to_numpy()]
    detalle = _sembrar_devoluciones(rng, detalle)

    hecho_cliente_producto = detalle[["id_cliente", "id_producto", "anio_mes", "unidades", "revenue"]].astype(
        {"id_cliente": "int64", "id_producto": "int64", "unidades": "float64", "revenue": "float64"}
    )

    hecho_producto = hecho_cliente_producto.groupby(["id_producto", "anio_mes"], as_index=False).agg(
        unidades=("unidades", "sum"), revenue=("revenue", "sum")
    )
    # `precio_prom` con neto cero queda **NaN, no infinito** — misma regla que
    # `motor/scripts/extraer_snap.py:187` sobre datos reales. Un mes de neto cero no tiene
    # precio, y un infinito metido en la cadena de deflación de M2 se propaga en silencio.
    unidades_netas = hecho_producto["unidades"]
    hecho_producto["precio_prom"] = hecho_producto["revenue"] / unidades_netas.where(
        unidades_netas != 0
    )
    hecho_producto = hecho_producto.astype(
        {"id_producto": "int64", "unidades": "float64", "revenue": "float64", "precio_prom": "float64"}
    )

    catalogo_producto = productos[["id_producto", "categoria", "laboratorio"]].copy()
    catalogo_producto["activo"] = True
    catalogo_producto = catalogo_producto.astype(
        {"id_producto": "int64", "categoria": "object", "laboratorio": "object", "activo": "bool"}
    )

    cliente_feature = _construir_cliente_feature(hecho_cliente_producto, catalogo_producto, clientes)

    tablas = {
        "hecho_venta_mensual_producto": hecho_producto,
        "hecho_venta_mensual_cliente_producto": hecho_cliente_producto,
        "catalogo_producto": catalogo_producto,
        "cliente_feature": cliente_feature,
    }
    return tablas, series_producto, productos


def _sembrar_devoluciones(rng: np.random.Generator, detalle: pd.DataFrame) -> pd.DataFrame:
    """Mete devoluciones a nivel de HECHOS, no solo en el JSON del contrato (T0.4 #2).

    El generador ya emitía ~9,5% de notas de crédito, pero solo al exportar
    `ventas_<AAAAMM>.json`, y capadas al 10-40% de un renglón. Resultado: **cero filas con
    unidades netas negativas** en las tablas que lee el motor, cuando los datos reales
    traen 281. Ni el motor ni el ETL de R1 ejercitaban nunca ese camino.

    Siembra tres casos, todos medidos sobre el extract:

    - **neto negativo** (0,205%): la devolución supera las ventas del producto en ese mes.
    - **neto exactamente cero** (3,53%): deja `precio_prom` indefinido — el insumo
      degenerado que la deflación de M2.1 tiene que sobrevivir.
    - **precio implícito negativo** (0,016%): la devolución va a un precio distinto del de
      la venta, así que unidades y revenue netean con **signos opuestos** (§5.5 #6). Es el
      caso contra el que existe el clamp de ratios de M2.1, y no se produce solo.
    """
    neto = detalle.groupby(["id_producto", "anio_mes"], as_index=False).agg(
        unidades=("unidades", "sum"), revenue=("revenue", "sum")
    )
    neto = neto[neto["unidades"] > 0].reset_index(drop=True)
    if neto.empty:
        return detalle

    n_total = len(neto)
    cupos = {
        "negativo": round(n_total * P.PORCENTAJE_MESES_NETO_NEGATIVO),
        "cero": round(n_total * P.PORCENTAJE_MESES_NETO_CERO),
        "cruzado": round(n_total * P.PORCENTAJE_MESES_PRECIO_CRUZADO),
    }
    elegidos = rng.choice(n_total, size=min(sum(cupos.values()), n_total), replace=False)

    # Un representante por (producto, mes) para heredar cliente, mes_idx y precio: la
    # devolución tiene que ser de alguien que efectivamente compró.
    representantes = detalle.drop_duplicates(subset=["id_producto", "anio_mes"]).set_index(
        ["id_producto", "anio_mes"]
    )

    filas, desde = [], 0
    for caso, cupo in cupos.items():
        for pos in elegidos[desde : desde + cupo]:
            objetivo = neto.iloc[pos]
            base = representantes.loc[(objetivo["id_producto"], objetivo["anio_mes"])]
            unidades_netas, revenue_neto = objetivo["unidades"], objetivo["revenue"]

            if caso == "cero":
                devueltas = unidades_netas
                precio = base["precio_efectivo"]
            elif caso == "negativo":
                devueltas = unidades_netas * rng.uniform(1.05, 1.60)
                precio = base["precio_efectivo"]
            else:
                devueltas = unidades_netas * rng.uniform(1.05, 1.60)
                # Precio de devolución por debajo del promedio del mes: alcanza para que
                # el revenue quede positivo mientras las unidades ya son negativas.
                precio = 0.5 * revenue_neto / devueltas

            filas.append(
                {
                    "id_cliente": base["id_cliente"],
                    "mes_idx": base["mes_idx"],
                    "unidades": -float(devueltas),
                    "id_producto": objetivo["id_producto"],
                    "precio_lista": base["precio_lista"],
                    "descuento": base["descuento"],
                    "precio_efectivo": precio,
                    "revenue": -float(devueltas) * precio,
                    "anio_mes": objetivo["anio_mes"],
                }
            )
        desde += cupo

    if not filas:
        return detalle
    return pd.concat([detalle, pd.DataFrame(filas)], ignore_index=True)


def _construir_cliente_feature(
    hecho_cliente_producto: pd.DataFrame, catalogo_producto: pd.DataFrame, clientes: pd.DataFrame
) -> pd.DataFrame:
    """Una versión de la tabla **por cada `PASO_MESES_CLIENTE_FEATURE` meses** (T0.4 #1).

    Antes emitía una sola foto, con `fecha_calculo` del último mes para todas las filas.
    M2.2 la quiere como feature, y un predictor que la consumiera en un corte de 2024
    estaría leyendo volumen y recency calculados con datos de 2026. El arnés ya tenía el
    hook para recortarla (`tablas_auxiliares`, recorta por `fecha_calculo <= corte`), pero
    no había nada que recortar.

    **El esquema no cambia** — `fecha_calculo` ya estaba en el diccionario. Lo que cambia
    es la cardinalidad: la clave pasa de `id_cliente` a `(id_cliente, fecha_calculo)`.

    Cada versión se calcula **solo con datos hasta su propia fecha**. Si se calculara sobre
    la historia completa y solo se le cambiara la etiqueta, el leakage seguiría ahí y
    encima invisible.
    """
    df = hecho_cliente_producto.merge(
        catalogo_producto[["id_producto", "categoria"]], on="id_producto", how="left"
    )
    paso = P.PASO_MESES_CLIENTE_FEATURE
    fechas = MESES[paso - 1 :: paso]

    versiones = [
        _version_cliente_feature(df[df["anio_mes"] <= fecha], clientes, fecha) for fecha in fechas
    ]
    versiones = [v for v in versiones if not v.empty]
    return pd.concat(versiones, ignore_index=True).astype(
        {
            "id_cliente": "int64",
            "categoria_principal": "object",
            "frecuencia_compra": "object",
            "volumen_anual": "float64",
            "valor_anual_estimado": "float64",
            "tendencia_volumen_3m": "float64",
            "recency_dias": "int64",
            "fecha_calculo": "datetime64[ns]",
        }
    )


def _version_cliente_feature(
    df: pd.DataFrame, clientes: pd.DataFrame, ultimo_mes: pd.Timestamp
) -> pd.DataFrame:
    """La tabla tal como se habría calculado el `ultimo_mes`, con `df` ya recortado a esa
    fecha por el llamador."""
    if df.empty:
        return pd.DataFrame()

    ventana_12m_ini = ultimo_mes - pd.DateOffset(months=11)
    agg_12m = df[df["anio_mes"] >= ventana_12m_ini].groupby("id_cliente").agg(
        volumen_anual=("unidades", "sum"), valor_anual_estimado=("revenue", "sum")
    )

    vol_por_categoria = df.groupby(["id_cliente", "categoria"])["unidades"].sum().reset_index()
    categoria_principal = (
        vol_por_categoria.sort_values("unidades", ascending=False)
        .drop_duplicates("id_cliente")
        .set_index("id_cliente")["categoria"]
    )

    ult_3m_ini = ultimo_mes - pd.DateOffset(months=2)
    prev_3m_ini = ultimo_mes - pd.DateOffset(months=5)
    u_ult = df[df["anio_mes"] >= ult_3m_ini].groupby("id_cliente")["unidades"].sum()
    u_prev = df[(df["anio_mes"] >= prev_3m_ini) & (df["anio_mes"] < ult_3m_ini)].groupby("id_cliente")[
        "unidades"
    ].sum()
    tendencia = ((u_ult - u_prev) / u_prev.replace(0, np.nan)).fillna(0.0)

    ultima_compra = df.groupby("id_cliente")["anio_mes"].max()
    recency_dias = (ultimo_mes - ultima_compra).dt.days

    n_meses_activo = df.groupby("id_cliente")["anio_mes"].nunique()
    frecuencia = pd.cut(
        n_meses_activo, bins=[-1, 3, 9, P.N_MESES], labels=["esporadica", "trimestral", "mensual"]
    ).astype(str)

    activos = clientes[clientes["id_cliente"].isin(df["id_cliente"].unique())].copy()
    resultado = activos.set_index("id_cliente")
    resultado["categoria_principal"] = categoria_principal
    resultado["frecuencia_compra"] = frecuencia
    resultado["volumen_anual"] = agg_12m["volumen_anual"]
    resultado["valor_anual_estimado"] = agg_12m["valor_anual_estimado"]
    resultado["tendencia_volumen_3m"] = tendencia
    resultado["recency_dias"] = recency_dias
    resultado = resultado.fillna(
        {"volumen_anual": 0.0, "valor_anual_estimado": 0.0, "tendencia_volumen_3m": 0.0}
    )
    resultado["fecha_calculo"] = ultimo_mes

    resultado = resultado.reset_index()[
        [
            "id_cliente",
            "categoria_principal",
            "frecuencia_compra",
            "volumen_anual",
            "valor_anual_estimado",
            "tendencia_volumen_3m",
            "recency_dias",
            "fecha_calculo",
        ]
    ]
    return resultado.astype(
        {
            "id_cliente": "int64",
            "categoria_principal": "object",
            "frecuencia_compra": "object",
            "volumen_anual": "float64",
            "valor_anual_estimado": "float64",
            "tendencia_volumen_3m": "float64",
            "recency_dias": "int64",
            "fecha_calculo": "datetime64[ns]",
        }
    )
