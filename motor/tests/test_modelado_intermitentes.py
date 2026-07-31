"""Tests de la rama intermitente (M1.6): `CrostonSBA` y `TSB`.

Foco: (1) contrato `PredictorFn` + corre dentro del arnés; (2) predicciones nunca
negativas (no hay demanda negativa); (3) planas en el horizonte — comportamiento
esperado de estos métodos (modelan una tasa de largo plazo, no un patrón mes a mes), así
que queda fijado en un test en vez de sorprender a alguien que mire el reporte y vea el
mismo número repetido 12 veces; (4) una serie sin ninguna venta no rompe la corrida.
"""

import pandas as pd
import pytest

from motor.backtesting.arnes import ejecutar_backtest
from motor.modelado.intermitentes import predecir_intermitentes

COLUMNAS_MODELOS = ["CrostonSBA", "TSB"]


@pytest.fixture
def historia_intermitente():
    """Una venta cada 3 meses — el patrón intermitente/lumpy que motiva esta rama."""
    meses = pd.date_range("2023-01-01", periods=24, freq="MS")
    unidades = [10.0 if i % 3 == 0 else 0.0 for i in range(24)]
    return pd.DataFrame({"id_producto": 1, "anio_mes": meses, "unidades": unidades})


def test_predecir_intermitentes_cumple_el_contrato_del_arnes(historia_intermitente):
    reporte = ejecutar_backtest(
        historia_intermitente, predecir_intermitentes, n_cortes=3, horizonte_max=3
    )

    for columna in COLUMNAS_MODELOS:
        assert columna in reporte.columns


def test_predicciones_nunca_negativas(historia_intermitente):
    corte = historia_intermitente["anio_mes"].max()
    predicciones = predecir_intermitentes(historia_intermitente, corte, horizonte_max=6)

    for columna in COLUMNAS_MODELOS:
        assert (predicciones[columna] >= 0).all()


def test_predicciones_planas_en_el_horizonte(historia_intermitente):
    """Croston/TSB modelan una tasa de demanda de largo plazo, no un patrón mes a mes:
    el mismo valor se repite en todo el horizonte. No es un bug — ver el docstring del
    módulo."""
    corte = historia_intermitente["anio_mes"].max()
    predicciones = predecir_intermitentes(historia_intermitente, corte, horizonte_max=6)

    for columna in COLUMNAS_MODELOS:
        assert predicciones[columna].nunique() == 1


def test_serie_toda_cero_no_rompe_la_corrida():
    datos = pd.DataFrame(
        {
            "id_producto": 1,
            "anio_mes": pd.date_range("2024-01-01", periods=6, freq="MS"),
            "unidades": 0.0,
        }
    )
    corte = datos["anio_mes"].max()

    predicciones = predecir_intermitentes(datos, corte, horizonte_max=3)

    assert (predicciones[COLUMNAS_MODELOS] == 0).all().all()
