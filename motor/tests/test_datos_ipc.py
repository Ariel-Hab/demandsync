"""Tests del IPC del INDEC — el último peldaño del fallback de deflación (ADR-002).

El riesgo real acá no es que el código falle: es que el **archivo** sea el equivocado o
esté vencido. La API de datos.gob.ar publica muchas series parecidas —variación mensual,
variación interanual, IPC por región, otras bases— y cualquiera de ellas se carga sin
error y produce deflactores en silencio. Por eso la mayoría de estos tests interroga los
datos, no las funciones.
"""

import pandas as pd
import pytest

from motor.datos.ipc import IpcDesactualizado, cargar_ipc

# Ventana que el motor tiene que poder deflactar: la del extract real (§5.5), 96 meses.
PRIMER_MES_MOTOR = pd.Timestamp("2018-07-01")
ULTIMO_MES_MOTOR = pd.Timestamp("2026-06-01")


@pytest.fixture(scope="module")
def ipc() -> pd.DataFrame:
    return cargar_ipc()


def test_el_esquema_es_el_del_diccionario(ipc):
    assert list(ipc.columns) == ["anio_mes", "indice"]
    assert ipc["anio_mes"].dtype == "datetime64[ns]"
    assert ipc["indice"].dtype == "float64"


def test_la_serie_no_tiene_huecos_ni_nulos_ni_duplicados(ipc):
    assert not ipc.isna().any().any()
    assert not ipc["anio_mes"].duplicated().any()
    esperado = pd.date_range(ipc["anio_mes"].min(), ipc["anio_mes"].max(), freq="MS")
    assert list(ipc["anio_mes"]) == list(esperado)


def test_cubre_la_ventana_del_motor(ipc):
    assert ipc["anio_mes"].min() <= PRIMER_MES_MOTOR
    assert ipc["anio_mes"].max() >= ULTIMO_MES_MOTOR


def test_es_un_indice_de_nivel_y_no_una_serie_de_variaciones(ipc):
    """Distingue la serie correcta de sus vecinas en la misma API.

    Un índice de nivel es creciente y arranca en la base; una serie de variaciones
    mensuales oscila alrededor de 0-10 y no es monótona. Las dos se cargan igual de bien
    y la equivocada daría deflactores cercanos a 1 para toda la historia: la deflación
    parecería andar y no haría nada.
    """
    assert ipc["indice"].is_monotonic_increasing
    assert (ipc["indice"] > 0).all()
    assert ipc.loc[ipc["anio_mes"] == pd.Timestamp("2016-12-01"), "indice"].item() == 100.0


def test_la_inflacion_acumulada_de_la_ventana_es_del_orden_esperado(ipc):
    """~×79 entre 2018-07 y 2026-06. La banda es ancha a propósito: no valida el número
    fino (para eso está la procedencia), valida que la serie sea de la magnitud correcta.
    Una serie con otra base o de otro país cae afuera."""
    v = ipc.set_index("anio_mes")["indice"]
    assert 50 < v[ULTIMO_MES_MOTOR] / v[PRIMER_MES_MOTOR] < 120


def test_hasta_recorta_inclusive_y_no_toca_el_pasado(ipc):
    corte = pd.Timestamp("2022-03-01")
    recortada = cargar_ipc(hasta=corte)

    assert recortada["anio_mes"].max() == corte
    pd.testing.assert_frame_equal(recortada, ipc[ipc["anio_mes"] <= corte].reset_index(drop=True))


def test_hasta_normaliza_una_fecha_de_mitad_de_mes():
    """El arnés genera cortes a fin de mes; los hechos son mensuales al día 1."""
    assert cargar_ipc(hasta=pd.Timestamp("2022-03-28"))["anio_mes"].max() == pd.Timestamp(
        "2022-03-01"
    )


def test_pedir_un_mes_posterior_al_csv_falla_en_vez_de_devolver_el_ultimo(ipc):
    """La falla silenciosa que este error previene: quedarse con el último índice
    disponible subestima la inflación y **achica** los montos deflactados de todo el
    período faltante, sin ninguna señal de que pasó."""
    futuro = ipc["anio_mes"].max() + pd.DateOffset(months=1)
    with pytest.raises(IpcDesactualizado, match="subestimaría la inflación"):
        cargar_ipc(hasta=futuro)


def test_el_ultimo_mes_del_csv_todavia_se_puede_pedir(ipc):
    ultimo = ipc["anio_mes"].max()
    assert cargar_ipc(hasta=ultimo)["anio_mes"].max() == ultimo
