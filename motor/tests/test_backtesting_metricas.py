"""Tests de `motor.backtesting.metricas` (M1.2).

`wape` y `sesgo` se verifican contra cálculos hechos a mano. `mase` se verifica
contra un valor de referencia obtenido corriendo `utilsforecast` directamente
(ver el comentario en `test_mase_...`) — no confiamos ciegamente en la librería,
pero tampoco reimplementamos su lógica: solo probamos que el wrapper (con el
rename por el bug de compatibilidad) le pasa los datos correctos.
"""

import numpy as np
import pandas as pd
import pytest

from motor.backtesting.metricas import mase, sesgo, wape


@pytest.fixture
def df_grupos():
    # grupo A: error absoluto 4 sobre real absoluto 30 -> wape 0.1333...; sesgo neto 0
    # grupo B: predicción perfecta -> wape 0, sesgo 0
    # grupo C: sin actividad real (real=0 en ambas filas) -> wape/sesgo indefinidos (NaN)
    return pd.DataFrame(
        {
            "grupo": ["A", "A", "B", "B", "C", "C"],
            "real": [10.0, 20.0, 5.0, 0.0, 0.0, 0.0],
            "pred": [12.0, 18.0, 5.0, 0.0, 1.0, 0.0],
        }
    )


def test_wape_agregado_por_grupo(df_grupos):
    resultado = wape(df_grupos, ["grupo"]).set_index("grupo")["wape"]

    assert resultado["A"] == pytest.approx(4 / 30)
    assert resultado["B"] == pytest.approx(0.0)
    assert np.isnan(resultado["C"])


def test_sesgo_agregado_por_grupo(df_grupos):
    resultado = sesgo(df_grupos, ["grupo"]).set_index("grupo")["sesgo"]

    # A: (12-10)+(18-20) = 0 -> sin sesgo neto pese a errores individuales
    assert resultado["A"] == pytest.approx(0.0)
    assert resultado["B"] == pytest.approx(0.0)
    assert np.isnan(resultado["C"])


def test_sesgo_detecta_sobre_y_sub_pronostico():
    sobre = pd.DataFrame({"grupo": ["X"], "real": [10.0], "pred": [15.0]})
    sub = pd.DataFrame({"grupo": ["X"], "real": [10.0], "pred": [5.0]})

    assert sesgo(sobre, ["grupo"])["sesgo"].iloc[0] > 0
    assert sesgo(sub, ["grupo"])["sesgo"].iloc[0] < 0


def test_wape_admite_grupos_compuestos(df_grupos):
    df = df_grupos.assign(horizonte=[1, 2, 1, 2, 1, 2])
    resultado = wape(df, ["grupo", "horizonte"])

    assert len(resultado) == 6
    # `n` y `cobertura` acompañan a toda métrica desde el arreglo del defecto 4: sin
    # ellas, dos tablas con cobertura muy distinta son indistinguibles.
    assert set(resultado.columns) == {"grupo", "horizonte", "wape", "n", "cobertura"}


def test_mase_wrapper_delega_correctamente_en_utilsforecast():
    # Historia (train): unidades = [10, 12, 9, 11] en 4 meses consecutivos. Nótese
    # que train_df usa "unidades" (la tabla cruda del repositorio) mientras que df
    # usa "real" (el reporte del arnés) — son nombres distintos a propósito, es
    # justo el caso que rompía antes de separar `columna_objetivo_train`.
    # Escala MASE (estacionalidad=1, naive de un paso) = media(|12-10|,|9-12|,|11-9|)
    #   = media(2, 3, 2) = 2.3333...
    # Corte = último mes de historia; predicción del mes siguiente = 15, real = 13.
    # MASE esperado = |13-15| / 2.3333... = 0.857142857...
    # (valor confirmado corriendo utilsforecast.losses.mase directamente con las
    # mismas cifras, antes de escribir el wrapper — no es una cifra inventada)
    train_df = pd.DataFrame(
        {
            "id_producto": ["P1"] * 4,
            "anio_mes": pd.date_range("2026-01-01", periods=4, freq="MS"),
            "unidades": [10.0, 12.0, 9.0, 11.0],
        }
    )
    df = pd.DataFrame(
        {
            "id_producto": ["P1"],
            "anio_mes": [pd.Timestamp("2026-05-01")],
            "corte": [pd.Timestamp("2026-04-01")],
            "real": [13.0],
            "pred_modelo": [15.0],
        }
    )

    resultado = mase(df, modelos=["pred_modelo"], train_df=train_df, estacionalidad=1)

    assert resultado["pred_modelo"].iloc[0] == pytest.approx(2 / (7 / 3))
    assert list(resultado.columns) == ["corte", "id_producto", "pred_modelo"]
