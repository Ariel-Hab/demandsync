"""Tests de `motor.backtesting.cortes` (M1.1).

Casos a mano, sin depender del generador sintético: si algo acá se rompe, el
problema está en la lógica de corte, no en datos ruidosos.
"""

import pandas as pd
import pytest

from motor.backtesting.cortes import generar_cortes


def _meses(inicio: str, cantidad: int) -> pd.Series:
    return pd.Series(pd.date_range(inicio, periods=cantidad, freq="MS"))


def test_devuelve_n_cortes_consecutivos():
    fechas = _meses("2024-01-01", 24)  # 2024-01 .. 2025-12
    cortes = generar_cortes(fechas, n_cortes=18)

    assert len(cortes) == 18
    assert cortes == list(pd.date_range("2024-06-01", periods=18, freq="MS"))


def test_excluye_el_ultimo_mes_de_la_serie():
    fechas = _meses("2024-01-01", 24)
    cortes = generar_cortes(fechas, n_cortes=18)

    assert cortes[-1] == pd.Timestamp("2025-11-01")
    assert pd.Timestamp("2025-12-01") not in cortes


def test_ignora_duplicados_y_desorden():
    # una tabla real trae una fecha repetida por cada producto/cliente, no una por mes
    fechas = pd.concat([_meses("2024-01-01", 20)] * 3).sample(frac=1, random_state=0)
    cortes = generar_cortes(fechas, n_cortes=18)

    assert len(cortes) == 18
    assert cortes == sorted(cortes)


def test_error_si_no_alcanzan_los_meses():
    fechas = _meses("2024-01-01", 10)
    with pytest.raises(ValueError, match="abarca solo 10 meses"):
        generar_cortes(fechas, n_cortes=18)
