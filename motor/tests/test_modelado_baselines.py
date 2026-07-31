"""Tests de los baselines statsforecast (M1.5).

Tres focos, no solo "corre sin error": (1) el contrato `PredictorFn` se cumple y corre
dentro del arnés real; (2) un producto recién entrado al catálogo (1 mes de historia en
un corte temprano) no tira abajo la corrida completa — el caso real que hacía explotar
`AutoETS`/`AutoTheta` antes de agregar `fallback_model`, verificado a mano contra el
dataset real antes de escribir el módulo; (3) `SeasonalNaive` acierta exacto contra una
estacionalidad conocida, como ancla de que el recorte de columnas y el `reset_index()`
no corrompen los datos en el camino.
"""

import pandas as pd
import pytest

from motor.backtesting.arnes import ejecutar_backtest
from motor.modelado.baselines import predecir_baselines

COLUMNAS_MODELOS = ["SeasonalNaive", "WindowAverage", "AutoETS", "AutoTheta", "AutoARIMA"]


@pytest.fixture
def historia_dos_productos():
    """Producto 1: 30 meses de historia. Producto 2: entra al catálogo con solo 2 meses
    antes del corte que se prueba — el caso de un producto nuevo con historia mínima."""
    meses_p1 = pd.date_range("2023-01-01", periods=30, freq="MS")
    p1 = pd.DataFrame(
        {"id_producto": 1, "anio_mes": meses_p1, "unidades": [float(i + 1) for i in range(30)]}
    )
    meses_p2 = pd.date_range("2025-05-01", periods=2, freq="MS")
    p2 = pd.DataFrame({"id_producto": 2, "anio_mes": meses_p2, "unidades": [3.0, 5.0]})
    return pd.concat([p1, p2], ignore_index=True)


def test_predecir_baselines_cumple_el_contrato_del_arnes(historia_dos_productos):
    reporte = ejecutar_backtest(
        historia_dos_productos, predecir_baselines, n_cortes=2, horizonte_max=3
    )

    for columna in COLUMNAS_MODELOS:
        assert columna in reporte.columns
    assert set(reporte["id_producto"].unique()) <= {1, 2}


def test_producto_recien_entrado_no_rompe_la_corrida(historia_dos_productos):
    # el corte que deja al producto 2 con exactamente 1 mes de historia
    corte = pd.Timestamp("2025-05-01")
    historia = historia_dos_productos[historia_dos_productos["anio_mes"] <= corte]
    assert (historia["id_producto"] == 2).sum() == 1  # el caso degenerado, no un promedio

    predicciones = predecir_baselines(historia, corte, horizonte_max=3)

    fila_p2 = predicciones[predicciones["id_producto"] == 2]
    assert len(fila_p2) == 3
    for columna in ["AutoETS", "AutoTheta"]:
        assert fila_p2[columna].notna().all(), (
            f"{columna} debería caer al fallback_model con 1 mes de historia, no a NaN"
        )


def test_no_rompe_con_columnas_extra_como_revenue_y_precio(historia_dos_productos):
    """Gotcha real: pasarle a `StatsForecast` columnas además de id/fecha/objetivo las
    interpreta como regresores exógenos obligatorios y explota pidiendo `X_df`. Los
    datos reales siempre traen `revenue`/`precio_prom` además de `unidades` (ver
    `motor/src/motor/datos/diccionario.py`), así que este caso no es hipotético."""
    con_extra = historia_dos_productos.assign(
        revenue=historia_dos_productos["unidades"] * 100.0, precio_prom=100.0
    )
    corte = con_extra["anio_mes"].max()

    predicciones = predecir_baselines(con_extra, corte, horizonte_max=3)

    assert len(predicciones) > 0


def test_seasonalnaive_acierta_exacto_contra_estacionalidad_conocida():
    # 24 meses con un patrón 1..12 repetido dos veces: el segundo ciclo repite el primero
    patron = (list(range(1, 13)) * 2)[:24]
    datos = pd.DataFrame(
        {
            "id_producto": 1,
            "anio_mes": pd.date_range("2024-01-01", periods=24, freq="MS"),
            "unidades": [float(v) for v in patron],
        }
    )
    corte = datos["anio_mes"].max()

    predicciones = predecir_baselines(datos, corte, horizonte_max=12)

    esperado = patron[-12:]  # el último ciclo completo, que SeasonalNaive debe repetir
    obtenido = predicciones.sort_values("anio_mes")["SeasonalNaive"].tolist()
    assert obtenido == pytest.approx(esperado)
