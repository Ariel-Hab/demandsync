"""Tests de la identificación de corridas y del reporte tabular (M1.0 (g)).

El gate de M1.1 pide "corridas identificadas" y el de M1.2 "reporte tabular; ningún
número global suelto sin desagregar". Lo que se prueba acá es exactamente eso: que la
corrida sea reproducible y sensible a los cambios, y que el reporte desagregue por
todos los cortes exigidos o **avise** cuando le falta uno.
"""

import pandas as pd
import pytest

from motor.backtesting.arnes import ejecutar_backtest
from motor.backtesting.corrida import Corrida
from motor.backtesting.reporte import a_markdown, construir_reporte

FECHA_FIJA = "2026-07-27"


N_CORTES = 14
"""Con `n_cortes=N`, el corte más viejo queda a N meses del final de los datos, así
que el horizonte máximo *medible* es N. Para que h=12 exista en el reporte hacen falta
más de 12 cortes — con 6 cortes el reporte llegaría hasta h=6 y no a los 1/3/6/12 que
exige el gate. Vale como recordatorio para configurar corridas reales."""


@pytest.fixture
def datos():
    """Dos productos, 36 meses densos."""
    meses = pd.date_range("2023-01-01", periods=36, freq="MS")
    filas = [
        {"id_producto": p, "anio_mes": m, "unidades": float(10 * p + i)}
        for p in (1, 2)
        for i, m in enumerate(meses)
    ]
    return pd.DataFrame(filas)


def _predictor(historia, corte, horizonte_max):
    ultimo = (
        historia.sort_values("anio_mes")
        .groupby("id_producto", as_index=False)
        .tail(1)[["id_producto", "unidades"]]
        .rename(columns={"unidades": "pred"})
    )
    fechas = pd.date_range(corte + pd.DateOffset(months=1), periods=horizonte_max, freq="MS")
    return ultimo.merge(pd.DataFrame({"anio_mes": fechas}), how="cross")


def _correr(datos, **kwargs):
    return ejecutar_backtest(
        datos, _predictor, n_cortes=N_CORTES, horizonte_max=12, fecha_ejecucion=FECHA_FIJA, **kwargs
    )


# ---------------------------------------------------------------------------------
# Corrida — trazabilidad
# ---------------------------------------------------------------------------------


def test_el_reporte_queda_identificado(datos):
    reporte = _correr(datos)

    corrida = reporte.attrs["corrida"]
    assert isinstance(corrida, Corrida)
    assert corrida.fecha_ejecucion == FECHA_FIJA
    assert corrida.n_cortes == N_CORTES
    assert corrida.densificado is True
    # la columna es el vínculo durable: `.attrs` se pierde en varias operaciones
    assert (reporte["id_corrida"] == corrida.id).all()


def test_la_columna_id_corrida_sobrevive_un_merge(datos):
    """`.attrs` no sobrevive a un merge; la columna sí. Por eso existen las dos."""
    reporte = _correr(datos)
    catalogo = pd.DataFrame({"id_producto": [1, 2], "categoria": ["vacunas", "antibioticos"]})

    cruzado = reporte.merge(catalogo, on="id_producto", how="left")

    assert "id_corrida" in cruzado.columns
    assert cruzado["id_corrida"].nunique() == 1


def test_misma_configuracion_y_mismos_datos_dan_el_mismo_id(datos):
    """Reproducible: el id es hash de configuración + huella de datos, no un secuencial
    ni un timestamp. Dos corridas equivalentes tienen que ser comparables."""
    a = _correr(datos).attrs["corrida"]
    b = _correr(datos).attrs["corrida"]

    assert a.id == b.id


def test_la_fecha_de_ejecucion_no_cambia_el_id(datos):
    a = _correr(datos).attrs["corrida"]
    b = ejecutar_backtest(
        datos, _predictor, n_cortes=N_CORTES, horizonte_max=12, fecha_ejecucion="2027-01-01"
    ).attrs["corrida"]

    assert a.id == b.id
    assert a.fecha_ejecucion != b.fecha_ejecucion


@pytest.mark.parametrize(
    ("que_cambia", "kwargs"),
    [("horizonte", {"horizonte_max": 6}), ("cortes", {"n_cortes": N_CORTES - 1})],
)
def test_cambiar_la_configuracion_cambia_el_id(datos, que_cambia, kwargs):
    base = _correr(datos).attrs["corrida"]
    config = {"n_cortes": N_CORTES, "horizonte_max": 12, **kwargs}
    otra = ejecutar_backtest(
        datos, _predictor, fecha_ejecucion=FECHA_FIJA, **config
    ).attrs["corrida"]

    assert base.id != otra.id, f"cambiar {que_cambia} tiene que cambiar el id de la corrida"


def test_cambiar_los_datos_cambia_el_id(datos):
    """Una tabla de error congelada contra otro dataset no es la misma referencia."""
    base = _correr(datos).attrs["corrida"]
    otros = datos.assign(unidades=datos["unidades"] * 2)

    assert base.id != _correr(otros).attrs["corrida"].id


# ---------------------------------------------------------------------------------
# Reporte tabular
# ---------------------------------------------------------------------------------


def test_el_reporte_desagrega_por_los_horizontes_exigidos(datos):
    tablas = construir_reporte(_correr(datos), columna_pred="pred")

    assert list(tablas["por_horizonte"]["horizonte"]) == [1, 3, 6, 12]
    assert set(tablas["por_horizonte"].columns) == {"horizonte", "wape", "sesgo", "n", "cobertura"}


def test_el_reporte_incluye_los_tres_niveles_de_agregacion(datos):
    catalogo = pd.DataFrame({"id_producto": [1, 2], "categoria": ["vacunas", "antibioticos"]})
    reporte = _correr(datos).merge(catalogo, on="id_producto", how="left")

    tablas = construir_reporte(reporte, columna_pred="pred")

    assert set(tablas["por_nivel_y_horizonte"]["nivel"]) == {"producto", "categoria", "total"}
    assert "por_categoria" in tablas


def test_sin_categoria_el_reporte_no_inventa_el_nivel(datos):
    tablas = construir_reporte(_correr(datos), columna_pred="pred")

    assert set(tablas["por_nivel_y_horizonte"]["nivel"]) == {"producto", "total"}
    assert "por_categoria" not in tablas


def test_el_markdown_avisa_que_falta_el_corte_por_cuadrante(datos):
    """Sin la columna `cuadrante` el reporte tiene que decirlo: un faltante silencioso se
    lee como cumplido. La columna la produce `motor.clasificacion` (M1.4), pero no todo
    reporte la trae — por ejemplo uno armado a mano para inspeccionar algo puntual."""
    md = a_markdown(construir_reporte(_correr(datos), columna_pred="pred"), titulo="Prueba")

    assert "cuadrante" in md
    assert "M1.4" in md


def test_con_la_columna_cuadrante_el_reporte_la_desagrega(datos):
    """El caso que cierra el gate de M1.2. Es la desagregación que más importa: sobre el
    sintético, el WAPE va de 0,51 en las series suaves a 1,63 en las lumpy, y un número
    global de 0,80 esconde esa diferencia de 3x."""
    from motor.clasificacion import clasificar_series, etiquetar

    reporte = etiquetar(_correr(datos), clasificar_series(datos))

    tablas = construir_reporte(reporte, columna_pred="pred")
    md = a_markdown(tablas, titulo="Prueba")

    assert "por_cuadrante" in tablas
    assert set(tablas["por_cuadrante"].columns) == {
        "cuadrante", "horizonte", "wape", "sesgo", "n", "cobertura"
    }
    assert "M1.4" not in md, "no debería avisar de un faltante que ya está cubierto"


def test_el_markdown_avisa_si_se_perdio_la_trazabilidad(datos):
    reporte = _correr(datos)
    reporte.attrs.clear()  # simula un reporte que pasó por operaciones que descartan attrs

    md = a_markdown(construir_reporte(reporte, columna_pred="pred"), titulo="Prueba")

    assert "sin identificador de corrida" in md
    assert "No es " in md  # no congelable como referencia


def test_el_markdown_lleva_la_corrida_y_las_tablas(datos):
    md = a_markdown(
        construir_reporte(_correr(datos), columna_pred="pred"), titulo="Piso de baselines"
    )

    assert md.startswith("# Piso de baselines")
    assert "## Corrida" in md
    assert "## Por nivel de agregación y horizonte" in md
    assert "sin identificador de corrida" not in md


def test_mase_entra_al_reporte_solo_si_se_pasa_la_historia(datos):
    reporte = _correr(datos)

    assert "mase_por_horizonte" not in construir_reporte(reporte, columna_pred="pred")

    con_mase = construir_reporte(reporte, columna_pred="pred", train_df=datos)
    assert list(con_mase["mase_por_horizonte"]["horizonte"]) == [1, 3, 6, 12]


def test_error_claro_si_no_hay_filas_en_los_horizontes_pedidos(datos):
    reporte = _correr(datos)

    with pytest.raises(ValueError, match="no tiene ninguna fila en los horizontes"):
        construir_reporte(reporte, columna_pred="pred", horizontes=(99,))
