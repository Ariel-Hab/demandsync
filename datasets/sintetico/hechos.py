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
            rng, prod["arquetipo"], prod["tamanio_base"], prod["sin_ancla_propia"]
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

    hecho_cliente_producto = detalle[["id_cliente", "id_producto", "anio_mes", "unidades", "revenue"]].astype(
        {"id_cliente": "int64", "id_producto": "int64", "unidades": "float64", "revenue": "float64"}
    )

    hecho_producto = hecho_cliente_producto.groupby(["id_producto", "anio_mes"], as_index=False).agg(
        unidades=("unidades", "sum"), revenue=("revenue", "sum")
    )
    hecho_producto["precio_prom"] = hecho_producto["revenue"] / hecho_producto["unidades"]
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


def _construir_cliente_feature(
    hecho_cliente_producto: pd.DataFrame, catalogo_producto: pd.DataFrame, clientes: pd.DataFrame
) -> pd.DataFrame:
    ultimo_mes = MESES[-1]
    df = hecho_cliente_producto.merge(
        catalogo_producto[["id_producto", "categoria"]], on="id_producto", how="left"
    )

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
