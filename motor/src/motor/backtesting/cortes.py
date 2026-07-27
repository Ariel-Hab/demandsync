"""Cortes rolling-origin para el arnés de backtesting (M1.1, plan-diseno.md §Protocolo).

Sin shuffle, sin k-fold: los cortes son puntos en el tiempo, ordenados, y cada uno
solo mira hacia atrás. Ver `arnes.py` para cómo se usan.
"""

import pandas as pd


def generar_cortes(fechas: pd.Series, n_cortes: int = 18) -> list[pd.Timestamp]:
    """Devuelve los últimos `n_cortes` meses de **calendario** que tienen al menos un
    mes posterior contra el cual medir.

    Excluye el último mes: un corte ahí no tendría ningún real futuro que comparar.
    Ej.: con datos hasta 2026-06 y `n_cortes=18`, devuelve los meses de 2024-12 a
    2026-05 (18 meses) — no incluye 2026-06.

    Los cortes salen del **calendario** entre el primer y el último mes de `fechas`,
    no de los meses observados (ADR-010). Con una serie dispersa —una venta cada tres
    meses, por ejemplo— tomar los observados daba "cortes mensuales" separados por
    saltos de hasta 15 meses, y hacía fallar el arnés por serie individual que exige
    M1.7 con el mensaje engañoso de que faltaban meses de datos.
    """
    fechas = pd.to_datetime(fechas)
    meses = pd.date_range(fechas.min(), fechas.max(), freq="MS")
    if len(meses) < n_cortes + 1:
        raise ValueError(
            f"Se pidieron {n_cortes} cortes pero el calendario abarca solo {len(meses)} "
            f"meses (hacen falta al menos {n_cortes + 1}: los cortes más uno de real futuro)"
        )
    return list(meses[-(n_cortes + 1) : -1])
