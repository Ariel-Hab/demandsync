"""Manifiesto de la corrida: semilla, parámetros y métricas de calibración logradas vs.
objetivo del EDA. Es la evidencia del gate de S0 — se commitea junto al script (los
archivos generados, no)."""

import json
from datetime import date
from pathlib import Path

import pandas as pd

from . import parametros as P
from .clasificacion import (
    clasificar_productos,
    desvios_vs_objetivo,
    distribucion_cuadrantes,
)


def calcular_metricas(
    tablas: dict, hoy: date, semilla: int, n_productos: int, n_clientes: int
) -> dict:
    hecho_producto = tablas["hecho_venta_mensual_producto"]
    hecho_cliente_producto = tablas["hecho_venta_mensual_cliente_producto"]

    clasificacion = clasificar_productos(hecho_producto)
    dist_cuadrantes = distribucion_cuadrantes(clasificacion)
    desvios = desvios_vs_objetivo(dist_cuadrantes)
    gate_cuadrantes_ok = all(abs(d) <= P.TOLERANCIA_CALIBRACION_PUNTOS for d in desvios.values())

    ultimo_mes = hecho_producto["anio_mes"].max()
    ventana_ini = ultimo_mes - pd.DateOffset(months=P.VENTANA_INTERMITENCIA_MESES - 1)
    detalle_ventana = hecho_cliente_producto[hecho_cliente_producto["anio_mes"] >= ventana_ini]
    meses_por_par = detalle_ventana.groupby(["id_cliente", "id_producto"])["anio_mes"].nunique()
    dist_pares = (
        pd.cut(
            meses_por_par,
            bins=[0, 2, 5, 11, 23, P.VENTANA_INTERMITENCIA_MESES],
            labels=["1-2", "3-5", "6-11", "12-23", "24+"],
            include_lowest=True,
        )
        .value_counts(normalize=True)
        .mul(100)
        .round(1)
        .to_dict()
    )

    ult_3_meses = hecho_producto["anio_mes"] > (ultimo_mes - pd.DateOffset(months=3))
    productos_con_venta_reciente = set(hecho_producto.loc[ult_3_meses, "id_producto"].unique())
    todos_los_productos = set(hecho_producto["id_producto"].unique())
    pct_sin_ancla = 100 * (1 - len(productos_con_venta_reciente) / len(todos_los_productos))

    return {
        "semilla": semilla,
        "fecha_generacion": hoy.isoformat(),
        "n_productos": n_productos,
        "n_clientes": n_clientes,
        "n_meses": P.N_MESES,
        "cuadrantes_intermitencia": {
            "objetivo_pct": {k: round(v * 100, 1) for k, v in P.PROPORCION_ARQUETIPOS.items()},
            "logrado_pct": {k: round(v, 1) for k, v in dist_cuadrantes.items()},
            "desvio_puntos": desvios,
            "tolerancia_puntos": P.TOLERANCIA_CALIBRACION_PUNTOS,
            "gate_ok": gate_cuadrantes_ok,
        },
        "intermitencia_cliente_producto": {
            "objetivo_pct": {"1-2": 53.5, "3-5": 20.4, "6-11": 14.2, "12-23": 8.7, "24+": 3.2},
            "logrado_pct": dist_pares,
            "nota": "calibración best-effort, no forma parte del gate de S0",
        },
        "productos_sin_ancla_propia": {
            "objetivo_pct": round(P.PORCENTAJE_SIN_ANCLA_PROPIA * 100, 1),
            "logrado_pct": round(pct_sin_ancla, 1),
        },
        "notas_credito": {
            "objetivo_pct_comprobantes": round(P.PORCENTAJE_NOTAS_CREDITO * 100, 1),
        },
        **_metricas_t0_4(tablas),
    }


def _metricas_t0_4(tablas: dict) -> dict:
    """Las cuatro condiciones de gate de T0.4.

    Todas se miden sobre la **salida**, no sobre los parámetros: que `TASA_BAJA_OBJETIVO`
    diga 5% no prueba que el dataset tenga 5% de bajas. Y se miden con la **misma
    definición** con que se midieron los datos reales, o los números no son comparables
    contra los objetivos del roadmap §12.1.
    """
    hecho_producto = tablas["hecho_venta_mensual_producto"]
    catalogo = tablas["catalogo_producto"]
    cliente_feature = tablas["cliente_feature"]

    n_versiones = int(cliente_feature["fecha_calculo"].nunique())

    negativos = int((hecho_producto["unidades"] < 0).sum())
    ceros = int((hecho_producto["unidades"] == 0).sum())
    cruzados = int(
        ((hecho_producto["unidades"] < 0) & (hecho_producto["revenue"] > 0)).sum()
    )
    sin_precio = int(hecho_producto["precio_prom"].isna().sum())

    altas, bajas = _altas_y_bajas(hecho_producto)
    dist_categorias, desvios_categorias = _distribucion_categorias(catalogo)

    return {
        "cliente_feature_versionada": {
            "n_fecha_calculo": n_versiones,
            "paso_meses": P.PASO_MESES_CLIENTE_FEATURE,
            "gate_ok": n_versiones > 1,
        },
        "meses_degenerados": {
            "neto_negativo": negativos,
            "neto_cero": ceros,
            "precio_implicito_negativo": cruzados,
            "sin_precio_prom": sin_precio,
            "gate_ok": negativos > 0 and ceros > 0,
        },
        "altas_y_bajas": {
            "objetivo_pct_alta_en_ventana": 20.0,
            "logrado_pct_alta_en_ventana": altas["en_ventana"],
            "logrado_pct_alta_posterior_al_inicio": altas["posterior_al_inicio"],
            "objetivo_pct_baja": round(P.TASA_BAJA_OBJETIVO * 100, 1),
            "logrado_pct_baja": bajas,
            "criterio_baja": (
                f"silencio > {P.MESES_MIN_SILENCIO_BAJA - 1}m que además supera el hueco "
                "más largo del propio producto"
            ),
            "tolerancia_puntos": P.TOLERANCIA_CALIBRACION_PUNTOS,
            "gate_ok": (
                abs(altas["en_ventana"] - 20.0) <= P.TOLERANCIA_CALIBRACION_PUNTOS
                and abs(bajas - P.TASA_BAJA_OBJETIVO * 100) <= P.TOLERANCIA_CALIBRACION_PUNTOS
            ),
        },
        "categorias": {
            "objetivo_pct": _objetivo_categorias(),
            "logrado_pct": dist_categorias,
            "desvio_puntos": desvios_categorias,
            "tolerancia_puntos": P.TOLERANCIA_CATEGORIAS_PUNTOS,
            "gate_ok": all(
                abs(d) <= P.TOLERANCIA_CATEGORIAS_PUNTOS for d in desvios_categorias.values()
            ),
        },
    }


def _altas_y_bajas(hecho_producto: pd.DataFrame) -> tuple[dict, float]:
    """% de productos con alta (dentro de la ventana y en total) y % de bajas.

    El criterio de baja **no** es "sin venta hace más de N meses": con 42% de series
    intermitentes, un hueco largo es comportamiento normal. Exige además que el silencio
    final supere el hueco más largo que ese producto ya había tenido estando vivo. Es el
    criterio con que se midió el 5,8% real, y medir de otra forma daría un número que no
    se puede comparar contra nada.
    """
    con_venta = hecho_producto[hecho_producto["unidades"] > 0]
    if con_venta.empty:
        return {"en_ventana": 0.0, "posterior_al_inicio": 0.0}, 0.0

    primer_mes = con_venta["anio_mes"].min()
    ultimo_mes = con_venta["anio_mes"].max()
    inicio_ventana = ultimo_mes - pd.DateOffset(months=P.VENTANA_INTERMITENCIA_MESES - 1)

    n_bajas = 0
    n_productos = 0
    n_alta_en_ventana = 0
    n_alta_posterior = 0
    for _, grupo in con_venta.groupby("id_producto", sort=False):
        meses = grupo["anio_mes"].sort_values().to_numpy()
        n_productos += 1
        if meses[0] > primer_mes:
            n_alta_posterior += 1
        if meses[0] >= inicio_ventana:
            n_alta_en_ventana += 1

        silencio = _distancia_meses(meses[-1], ultimo_mes)
        huecos = [_distancia_meses(a, b) - 1 for a, b in zip(meses, meses[1:])]
        if silencio >= P.MESES_MIN_SILENCIO_BAJA and silencio > max(huecos, default=0):
            n_bajas += 1

    pct = lambda k: round(100 * k / n_productos, 1)  # noqa: E731
    return (
        {"en_ventana": pct(n_alta_en_ventana), "posterior_al_inicio": pct(n_alta_posterior)},
        pct(n_bajas),
    )


def _distancia_meses(desde, hasta) -> int:
    a, b = pd.Timestamp(desde), pd.Timestamp(hasta)
    return (b.year - a.year) * 12 + (b.month - a.month)


def _objetivo_categorias() -> dict[str, float]:
    total = sum(P.CATEGORIAS_CONTEO.values())
    return {k: round(100 * v / total, 2) for k, v in P.CATEGORIAS_CONTEO.items()}


def _distribucion_categorias(catalogo: pd.DataFrame) -> tuple[dict, dict]:
    logrado = (catalogo["categoria"].value_counts(normalize=True) * 100).round(2).to_dict()
    objetivo = _objetivo_categorias()
    desvios = {
        categoria: round(logrado.get(categoria, 0.0) - objetivo_pct, 2)
        for categoria, objetivo_pct in objetivo.items()
    }
    return logrado, desvios


def escribir_manifiesto(metricas: dict, archivo: Path) -> Path:
    archivo.parent.mkdir(parents=True, exist_ok=True)
    with archivo.open("w", encoding="utf-8") as f:
        json.dump(metricas, f, ensure_ascii=False, indent=2)
    return archivo
