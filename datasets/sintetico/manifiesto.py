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
    }


def escribir_manifiesto(metricas: dict, archivo: Path) -> Path:
    archivo.parent.mkdir(parents=True, exist_ok=True)
    with archivo.open("w", encoding="utf-8") as f:
        json.dump(metricas, f, ensure_ascii=False, indent=2)
    return archivo
