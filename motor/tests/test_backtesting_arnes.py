"""Tests de `motor.backtesting.arnes` (M1.1).

Usan un predictor "naive" (repite el último valor conocido) escrito a mano en
este módulo, solo para probar la plomería del arnés — no es un baseline real
(esos son M1.5/M1.6). Los datos son una serie creciente conocida para poder
calcular el error esperado sin ambigüedad.
"""

import pandas as pd
import pytest

from motor.backtesting.arnes import ejecutar_backtest


@pytest.fixture
def datos_un_producto():
    # unidades = 10, 11, ..., 19 en Ene..Oct 2025 (10 meses)
    return pd.DataFrame(
        {
            "id_producto": [1] * 10,
            "anio_mes": pd.date_range("2025-01-01", periods=10, freq="MS"),
            "unidades": [float(10 + i) for i in range(10)],
        }
    )


def predictor_naive(
    historia: pd.DataFrame, corte: pd.Timestamp, horizonte_max: int
) -> pd.DataFrame:
    """Repite el último valor conocido de cada producto para los próximos meses."""
    ultimo = (
        historia.sort_values("anio_mes")
        .groupby("id_producto", as_index=False)
        .tail(1)[["id_producto", "unidades"]]
        .rename(columns={"unidades": "pred_naive"})
    )
    fechas = pd.date_range(corte + pd.DateOffset(months=1), periods=horizonte_max, freq="MS")
    return ultimo.merge(pd.DataFrame({"anio_mes": fechas}), how="cross")


def test_arnes_no_filtra_futuro_al_predictor(datos_un_producto):
    fechas_vistas = []

    def predictor_espia(historia, corte, horizonte_max):
        fechas_vistas.append((corte, historia["anio_mes"].max()))
        return predictor_naive(historia, corte, horizonte_max)

    ejecutar_backtest(datos_un_producto, predictor_espia, n_cortes=6, horizonte_max=3)

    assert len(fechas_vistas) == 6
    for corte, ultima_fecha_vista in fechas_vistas:
        assert ultima_fecha_vista <= corte, (
            f"el predictor vio {ultima_fecha_vista.date()} en un corte de {corte.date()}: leakage"
        )


def test_arnes_calcula_error_esperado_con_predictor_naive(datos_un_producto):
    reporte = ejecutar_backtest(datos_un_producto, predictor_naive, n_cortes=6, horizonte_max=3)

    # corte = 2025-04 (unidades=13): predice 13 para may/jun/jul (reales 14/15/16)
    fila_h1 = reporte[(reporte["corte"] == "2025-04-01") & (reporte["horizonte"] == 1)].iloc[0]
    fila_h3 = reporte[(reporte["corte"] == "2025-04-01") & (reporte["horizonte"] == 3)].iloc[0]

    assert fila_h1["real"] == 14.0
    assert fila_h1["pred_naive"] == 13.0
    assert fila_h3["real"] == 16.0
    assert fila_h3["pred_naive"] == 13.0


def test_arnes_trunca_en_el_borde_de_la_historia(datos_un_producto):
    # corte = 2025-09 (el último de los 6): horizonte_max=3 pide oct/nov/dic,
    # pero la historia termina en oct -> solo debe sobrevivir horizonte=1
    reporte = ejecutar_backtest(datos_un_producto, predictor_naive, n_cortes=6, horizonte_max=3)

    filas_ultimo_corte = reporte[reporte["corte"] == "2025-09-01"]
    assert list(filas_ultimo_corte["horizonte"]) == [1]


def test_arnes_exige_columnas_minimas_del_predictor(datos_un_producto):
    def predictor_incompleto(historia, corte, horizonte_max):
        return pd.DataFrame({"anio_mes": [corte + pd.DateOffset(months=1)]})  # falta id_producto

    with pytest.raises(ValueError, match="id_producto"):
        ejecutar_backtest(datos_un_producto, predictor_incompleto, n_cortes=6, horizonte_max=3)
