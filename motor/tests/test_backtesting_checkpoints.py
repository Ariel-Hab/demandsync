"""Tests de `motor.backtesting.checkpoints` (M2.5).

El módulo existe para una sola cosa: cruzar dos corridas ya ejecutadas sin reajustar
modelos. Todo lo que se testea acá es que **falle** cuando el cruce no es legítimo — un
cruce mal hecho no explota, produce una tabla de error con cara de válida, que es el modo
de falla que §5.6.1 ya pagó una vez.
"""

import numpy as np
import pandas as pd
import pytest

from motor.backtesting.arnes import ejecutar_backtest
from motor.backtesting.checkpoints import (
    cargar_desde_checkpoints,
    columnas_de_modelo,
    cruzar_reportes,
)


def _datos(n_productos: int = 4, n_meses: int = 30, semilla: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(semilla)
    meses = pd.date_range("2022-01-01", periods=n_meses, freq="MS")
    return pd.DataFrame(
        {
            "id_producto": np.repeat([f"P{i}" for i in range(n_productos)], n_meses),
            "anio_mes": np.tile(meses, n_productos),
            "unidades": rng.integers(0, 40, n_productos * n_meses).astype(float),
        }
    )


def _predictor(nombre: str, valor: float):
    """Predictor constante: lo que importa acá es la forma del reporte, no la precisión."""

    def predecir(historia: pd.DataFrame, corte: pd.Timestamp, horizonte_max: int) -> pd.DataFrame:
        futuro = pd.date_range(corte + pd.DateOffset(months=1), periods=horizonte_max, freq="MS")
        productos = historia["id_producto"].unique()
        return pd.DataFrame(
            {
                "id_producto": np.repeat(productos, len(futuro)),
                "anio_mes": np.tile(futuro, len(productos)),
                nombre: valor,
            }
        )

    return predecir


def _correr(datos: pd.DataFrame, directorio, nombre: str, valor: float) -> pd.DataFrame:
    return ejecutar_backtest(
        datos, _predictor(nombre, valor), n_cortes=4, horizonte_max=3,
        directorio_checkpoint=directorio,
    )


# --- cargar_desde_checkpoints -------------------------------------------------------


def test_relee_la_corrida_entera_sin_invocar_al_predictor(tmp_path):
    datos = _datos()
    original = _correr(datos, tmp_path / "ck", "ModeloA", 5.0)

    releido = cargar_desde_checkpoints(datos, tmp_path / "ck", n_cortes=4, horizonte_max=3)

    pd.testing.assert_frame_equal(original, releido)


def test_el_id_de_corrida_sobrevive_a_la_relectura(tmp_path):
    datos = _datos()
    original = _correr(datos, tmp_path / "ck", "ModeloA", 5.0)

    releido = cargar_desde_checkpoints(datos, tmp_path / "ck", n_cortes=4, horizonte_max=3)

    assert releido.attrs["corrida"].id == original.attrs["corrida"].id
    assert releido.attrs["corrida"].huella_datos == original.attrs["corrida"].huella_datos


def test_si_falta_un_corte_corta_en_vez_de_predecirlo(tmp_path):
    """El caso peligroso: completar en silencio daría un reporte mitad checkpoint, mitad
    recalculado, sin nada que lo distinga del completo."""
    datos = _datos()
    _correr(datos, tmp_path / "ck", "ModeloA", 5.0)
    for parquet in sorted((tmp_path / "ck").glob("corte_*.parquet"))[-1:]:
        parquet.unlink()

    with pytest.raises(ValueError, match="Falta el checkpoint del corte"):
        cargar_desde_checkpoints(datos, tmp_path / "ck", n_cortes=4, horizonte_max=3)


def test_releer_con_otros_datos_no_devuelve_los_checkpoints_ajenos(tmp_path):
    """La guarda de `id` del arnés es la que hace confiable a todo el módulo: el `id` se
    recalcula desde los datos que después alimentan el MASE, no se lee del manifiesto."""
    _correr(_datos(), tmp_path / "ck", "ModeloA", 5.0)
    otros = _datos(semilla=99)

    with pytest.raises(ValueError, match="checkpoints de la corrida"):
        cargar_desde_checkpoints(otros, tmp_path / "ck", n_cortes=4, horizonte_max=3)


def test_directorio_inexistente_corta_con_su_ruta(tmp_path):
    with pytest.raises(ValueError, match="No existe el directorio"):
        cargar_desde_checkpoints(_datos(), tmp_path / "no-esta")


# --- cruzar_reportes ----------------------------------------------------------------


def test_cruza_dos_corridas_de_la_misma_configuracion(tmp_path):
    """El caso real de M2.5: baselines y global corridos por separado, mismos datos."""
    datos = _datos()
    izq = _correr(datos, tmp_path / "a", "ModeloA", 5.0)
    der = _correr(datos, tmp_path / "b", "ModeloB", 9.0)

    cruzado = cruzar_reportes({"baselines": izq, "global": der})

    assert len(cruzado) == len(izq) == len(der)
    assert columnas_de_modelo(cruzado) == ["ModeloA", "ModeloB"]
    assert (cruzado["ModeloA"] == 5.0).all()
    assert (cruzado["ModeloB"] == 9.0).all()
    # El `real` no se duplica: queda uno solo, el de los dos.
    assert list(cruzado.columns).count("real") == 1


def test_el_cruce_conserva_el_real_y_el_id(tmp_path):
    datos = _datos()
    izq = _correr(datos, tmp_path / "a", "ModeloA", 5.0)
    der = _correr(datos, tmp_path / "b", "ModeloB", 9.0)

    cruzado = cruzar_reportes({"baselines": izq, "global": der})

    esperado = izq.sort_values(list(("id_producto", "anio_mes", "corte", "horizonte")))
    obtenido = cruzado.sort_values(list(("id_producto", "anio_mes", "corte", "horizonte")))
    assert np.array_equal(esperado["real"].to_numpy(), obtenido["real"].to_numpy())
    assert cruzado["id_corrida"].nunique() == 1


def test_corridas_distintas_no_se_cruzan(tmp_path):
    """Otro extract, otros cortes: las filas cruzarían por casualidad de nombre."""
    izq = _correr(_datos(), tmp_path / "a", "ModeloA", 5.0)
    der = _correr(_datos(semilla=99), tmp_path / "b", "ModeloB", 9.0)

    with pytest.raises(ValueError, match="corridas distintas"):
        cruzar_reportes({"baselines": izq, "global": der})


def test_una_clave_que_falta_de_un_lado_corta(tmp_path):
    """Comparar sobre la intersección premia al que predijo menos filas — el sesgo por
    omisión que §5.6.1 midió en el piso retrospectivo."""
    datos = _datos()
    izq = _correr(datos, tmp_path / "a", "ModeloA", 5.0)
    der = _correr(datos, tmp_path / "b", "ModeloB", 9.0).iloc[:-3]

    with pytest.raises(ValueError, match="no es fila a fila"):
        cruzar_reportes({"baselines": izq, "global": der})


def test_real_discrepante_corta_aunque_el_id_coincida(tmp_path):
    datos = _datos()
    izq = _correr(datos, tmp_path / "a", "ModeloA", 5.0)
    der = _correr(datos, tmp_path / "b", "ModeloB", 9.0)
    der.loc[der.index[0], "real"] = der["real"].iloc[0] + 1

    with pytest.raises(ValueError, match="distinto `real`"):
        cruzar_reportes({"baselines": izq, "global": der})


def test_real_nulo_en_los_dos_lados_no_es_discrepancia(tmp_path):
    """`NaN == NaN` es False en pandas: sin el tratamiento explícito, dos corridas
    idénticas con un real ausente se rechazarían entre sí."""
    datos = _datos()
    izq = _correr(datos, tmp_path / "a", "ModeloA", 5.0)
    der = _correr(datos, tmp_path / "b", "ModeloB", 9.0)
    izq.loc[izq.index[0], "real"] = np.nan
    der.loc[der.index[0], "real"] = np.nan

    cruzado = cruzar_reportes({"baselines": izq, "global": der})

    assert len(cruzado) == len(izq)


def test_columnas_de_modelo_repetidas_cortan(tmp_path):
    """Sin esta guarda el merge devuelve `pred_x`/`pred_y` y la selección toma una sola."""
    datos = _datos()
    izq = _correr(datos, tmp_path / "a", "Modelo", 5.0)
    der = _correr(datos, tmp_path / "b", "Modelo", 9.0)

    with pytest.raises(ValueError, match="columnas de modelo repetidas"):
        cruzar_reportes({"baselines": izq, "global": der})


def test_un_reporte_con_claves_duplicadas_corta(tmp_path):
    """El cruce multiplicaría filas y el WAPE saldría ponderado al doble en esas series."""
    datos = _datos()
    izq = _correr(datos, tmp_path / "a", "ModeloA", 5.0)
    der = _correr(datos, tmp_path / "b", "ModeloB", 9.0)
    der = pd.concat([der, der.iloc[[0]]], ignore_index=True)

    with pytest.raises(ValueError, match="filas duplicadas"):
        cruzar_reportes({"baselines": izq, "global": der})


def test_un_reporte_que_mezcla_corridas_corta(tmp_path):
    datos = _datos()
    izq = _correr(datos, tmp_path / "a", "ModeloA", 5.0)
    der = _correr(datos, tmp_path / "b", "ModeloB", 9.0)
    der.loc[der.index[0], "id_corrida"] = "otra"

    with pytest.raises(ValueError, match="mezcla 2 corridas"):
        cruzar_reportes({"baselines": izq, "global": der})


def test_un_solo_reporte_no_es_un_cruce(tmp_path):
    izq = _correr(_datos(), tmp_path / "a", "ModeloA", 5.0)

    with pytest.raises(ValueError, match="al menos dos reportes"):
        cruzar_reportes({"baselines": izq})


def test_reporte_sin_id_de_corrida_corta(tmp_path):
    """Un DataFrame armado a mano (o leído de parquet suelto) no trae `id_corrida`, y sin
    él la guarda 1 no puede comprobar nada: mejor cortar que cruzar a ciegas."""
    datos = _datos()
    izq = _correr(datos, tmp_path / "a", "ModeloA", 5.0)
    der = _correr(datos, tmp_path / "b", "ModeloB", 9.0).drop(columns=["id_corrida"])

    with pytest.raises(ValueError, match="no tiene las columnas"):
        cruzar_reportes({"baselines": izq, "global": der})
