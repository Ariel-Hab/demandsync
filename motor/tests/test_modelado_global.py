"""Tests del modelo global LightGBM (M2.3): `motor.modelado.modelo_global`.

Tres focos:

1. **El contrato `PredictorFn`** — corre dentro del arnés, devuelve las columnas que el
   arnés espera y no inventa demanda negativa.
2. **La alineación del `X_df`**, que es LA decisión de diseño del módulo. `mlforecast`
   indexa las exógenas futuras **por posición** (`core.py::_get_features_for_next_step`),
   así que un `X_df` desordenado le da a un producto el precio de otro **sin fallar**, y un
   `X_df` que arranque en `corte+1` desalinea entrenamiento y predicción por un mes. Las dos
   cosas se manifiestan como un modelo un poco peor, nunca como un error.
3. **Los casos degenerados** donde el motor ya se quemó antes: series de 1 mes (M1.5 gotcha
   3), productos sin catálogo (`SIN CATEGORIA`, 221 reales), series en cero.
"""

import numpy as np
import pandas as pd
import pytest

from motor.backtesting.arnes import ejecutar_backtest
from motor.backtesting.leakage import verificar_sin_leakage
from motor.features.especificacion import (
    VENTANAS_DISPERSION,
    VENTANAS_MEDIA_MOVIL,
    armar_lag_transforms,
)
from motor.modelado.modelo_global import (
    CUANTILES_ESTANDAR,
    NOMBRE_MODELO,
    _armar_entrenamiento,
    _armar_x_df,
    cobertura_esperada,
    nombre_de_cuantil,
    predecir_global,
)

HIPER_TEST = {
    "n_estimators": 15,
    "num_leaves": 7,
    "min_child_samples": 5,
    "verbose": -1,
    "n_jobs": 1,
    "random_state": 0,
    "deterministic": True,
    "force_row_wise": True,
}
"""LightGBM chico y **determinístico**: `verificar_sin_leakage` compara dos corridas por
igualdad exacta, así que sin fijar hilos y semilla el test sería flaky y se leería como
leakage."""


def _historia(n_productos: int = 6, n_meses: int = 40, semilla: int = 7) -> pd.DataFrame:
    """Panel denso con estacionalidad, tendencia y precios que suben — lo mínimo para que
    haya algo que aprender y para que la deflación tenga de dónde sacar un índice."""
    rng = np.random.default_rng(semilla)
    meses = pd.date_range("2021-01-01", periods=n_meses, freq="MS")
    filas = [
        (
            p,
            m,
            max(0.0, 20 + 5 * p + 4 * np.sin(i / 6) + rng.normal(0, 2)),
            100.0 * (p + 1) * (1 + 0.03 * i),
        )
        for p in range(n_productos)
        for i, m in enumerate(meses)
    ]
    historia = pd.DataFrame(filas, columns=["id_producto", "anio_mes", "unidades", "precio_prom"])
    historia["revenue"] = historia["unidades"] * historia["precio_prom"]
    return historia


def _catalogo(n_productos: int = 6) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id_producto": range(n_productos),
            "categoria": ["CAT_A" if p % 2 else "CAT_B" for p in range(n_productos)],
            "laboratorio": [f"LAB{p % 3}" for p in range(n_productos)],
        }
    )


def _predecir(historia, corte, h=6, **kwargs):
    return predecir_global(
        historia, corte, h, {"catalogo": _catalogo()}, hiperparametros=HIPER_TEST, **kwargs
    )


# --------------------------------------------------------------------------------------
# 1. Contrato
# --------------------------------------------------------------------------------------


def test_devuelve_el_horizonte_completo_por_serie():
    historia = _historia()
    corte = historia["anio_mes"].max()

    pred = _predecir(historia, corte, h=6)

    assert set(pred.columns) == {"id_producto", "anio_mes", NOMBRE_MODELO}
    assert pred.groupby("id_producto").size().eq(6).all()
    assert pred["anio_mes"].min() == corte + pd.DateOffset(months=1)
    assert pred["anio_mes"].max() == corte + pd.DateOffset(months=6)


def test_no_predice_demanda_negativa():
    """El target son unidades (ADR-007) y una demanda negativa no existe.

    **Cuándo importa el clip, que no es lo que uno supondría.** Un ensamble de árboles
    predice promedios ponderados de targets observados, así que **no puede** salirse del
    rango de entrenamiento: con toda la historia en positivo, el clip es código muerto y una
    serie "en descenso" no alcanza para ejercitarlo — la primera versión de este test lo
    intentaba así y la mutación lo destapó.

    Lo que sí lo ejercita son los **meses de neto negativo**, que son un caso real: una nota
    de crédito grande puede dejar el mes en negativo (T0.4 los siembra en el sintético, y
    §5.5 #6 los encontró en el extract). Ahí el modelo sí puede devolver negativo y el clip
    es lo que evita publicar una demanda imposible.
    """
    historia = _historia(n_productos=6, n_meses=30)
    devoluciones = historia["id_producto"] == 0
    historia.loc[devoluciones, "unidades"] = np.linspace(30, -60, int(devoluciones.sum()))
    corte = historia["anio_mes"].max()

    pred = predecir_global(
        historia, corte, 12, {"catalogo": _catalogo()}, hiperparametros=HIPER_TEST
    )

    assert (pred[NOMBRE_MODELO] >= 0).all()


def test_corre_dentro_del_arnes():
    """El gate de M2.3: que sea un `PredictorFn` de verdad, no una función suelta que
    parece uno. Se corre por el mismo camino que los baselines, con el catálogo entrando
    por `tablas_auxiliares` (el arnés lo pasa entero: no tiene columna de fecha)."""
    historia = _historia(n_productos=6, n_meses=30)

    reporte = ejecutar_backtest(
        historia,
        lambda h, c, hm, aux: predecir_global(h, c, hm, aux, hiperparametros=HIPER_TEST),
        n_cortes=2,
        horizonte_max=3,
        tablas_auxiliares={"catalogo": _catalogo()},
    )

    assert NOMBRE_MODELO in reporte.columns
    # las mismas columnas clave que el reporte de baselines: es lo que lo hace mergeable
    assert {"id_producto", "anio_mes", "corte", "horizonte", "real"} <= set(reporte.columns)
    assert reporte[NOMBRE_MODELO].notna().any()


@pytest.mark.innegociable
def test_predecir_global_no_mira_el_futuro():
    """La red de M1.3 sobre el predictor entero.

    M2.2 ya cubrió `construir_features`, pero acá hay superficie nueva y es la más peligrosa
    del módulo: el `X_df` es literalmente una tabla de **fechas futuras**, o sea el lugar
    natural donde se colaría un valor real de `corte+h`. Si eso pasara, el WAPE mejoraría y
    nada avisaría.
    """
    historia = _historia(n_productos=5, n_meses=36)
    cortes = [pd.Timestamp("2023-01-01"), pd.Timestamp("2023-06-01")]

    verificar_sin_leakage(
        lambda datos, corte: _predecir(datos, corte, h=3).sort_values(
            ["id_producto", "anio_mes"]
        )[NOMBRE_MODELO],
        historia,
        cortes,
    )


# --------------------------------------------------------------------------------------
# 2. Alineación del X_df — la decisión de diseño
# --------------------------------------------------------------------------------------


def test_el_x_df_lleva_el_precio_del_corte_y_no_el_del_mes_siguiente():
    """En entrenamiento la fila del origen `t` lleva las features de `t` y el target en
    `t+h` (`max_horizon`). Entonces en predicción el modelo tiene que recibir las del
    **corte**, no las de `corte+1`.

    Es un desfasaje de un mes que no falla nunca: solo entrena una relación y aplica otra.

    **El fixture necesita 6 productos, no 3**, y no es un detalle: la cascada de deflación
    exige `MUESTRA_MINIMA=3` productos por nivel para calcular un índice, así que con 3
    productos repartidos en 2 categorías ningún nivel llega y `precio_rel_nivel` sale todo
    `NaN`. Con la primera versión de este test comparaba `NaN` contra `NaN` — el mismo modo
    de falla que la mutación destapó en M2.2. De ahí la guarda de abajo.
    """
    historia = _historia(n_productos=6, n_meses=30)
    corte = historia["anio_mes"].max()
    # **Un salto de precio en el último mes, o el test no distingue nada:** con precios que
    # crecen suave, `precio_rel_nivel` casi no cambia de un mes al otro y `allclose` da
    # verdadero contra el valor del mes anterior. Así sobrevivía la mutación del desfasaje.
    #
    # Y el salto va en **un solo producto**, no en todos: si se mueven todos, se mueve con
    # ellos el índice de su categoría y `precio_rel_nivel` queda igual — que es exactamente
    # para lo que la feature existe (filtra la inflación, deja el movimiento relativo). Con
    # el salto uniforme este test también fallaba, y por el motivo correcto.
    salta = (historia["id_producto"] == 0) & (historia["anio_mes"] == corte)
    historia.loc[salta, "precio_prom"] *= 3.0
    historia["revenue"] = historia["unidades"] * historia["precio_prom"]
    entrenamiento, dinamicas = _armar_entrenamiento(
        historia, corte, _catalogo(), True, "id_producto", "anio_mes", "unidades"
    )

    x_df = _armar_x_df(entrenamiento, corte, 6, dinamicas, "id_producto", "anio_mes")

    assert x_df["precio_rel_nivel"].notna().all(), "el fixture no está ejercitando nada"
    en_el_corte = entrenamiento[entrenamiento["anio_mes"] == corte].set_index("id_producto")
    previo = entrenamiento[entrenamiento["anio_mes"] == corte - pd.DateOffset(months=1)]
    previo = previo.set_index("id_producto")["precio_rel_nivel"]
    assert not np.isclose(
        en_el_corte.loc[0, "precio_rel_nivel"], previo.loc[0]
    ), "el producto 0 tiene el mismo precio relativo en los dos meses: el test no distingue"
    for id_producto, grupo in x_df.groupby("id_producto"):
        esperado = en_el_corte.loc[id_producto, "precio_rel_nivel"]
        assert np.allclose(grupo["precio_rel_nivel"], esperado)
        # y constante en todo el horizonte: el precio futuro no se conoce, no se proyecta
        assert grupo["precio_rel_nivel"].nunique() == 1


def test_el_x_df_esta_ordenado_por_serie_y_mes():
    """`mlforecast` toma las exógenas futuras **por posición**, no por join
    (`_get_features_for_next_step`: `rows = arange(_h, len(X_df), h)`).

    Un `X_df` desordenado le entrega a un producto el precio de otro **sin ninguna
    excepción**: el modelo entrena bien y predice con la feature cruzada. De ahí que el
    orden sea parte del contrato y no una prolijidad.
    """
    historia = _historia(n_productos=6, n_meses=30)
    corte = historia["anio_mes"].max()
    entrenamiento, dinamicas = _armar_entrenamiento(
        historia, corte, _catalogo(), True, "id_producto", "anio_mes", "unidades"
    )

    x_df = _armar_x_df(entrenamiento, corte, 5, dinamicas, "id_producto", "anio_mes")

    assert x_df["precio_rel_nivel"].notna().all(), "el fixture no está ejercitando nada"
    esperado = x_df.sort_values(["id_producto", "anio_mes"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(x_df, esperado)
    # y un bloque completo y del mismo tamaño por serie, que es lo que asume el `arange`
    assert x_df.groupby("id_producto").size().eq(5).all()


def test_sin_features_de_precio_no_se_arma_x_df():
    """La ablación tiene que ser real: con `usar_precio=False` no entra ninguna columna de
    precio dinámica, y entonces no hay exógenas futuras que pasar."""
    historia = _historia(n_productos=6, n_meses=30)
    corte = historia["anio_mes"].max()

    entrenamiento, dinamicas = _armar_entrenamiento(
        historia, corte, _catalogo(), False, "id_producto", "anio_mes", "unidades"
    )

    assert dinamicas == []
    assert _armar_x_df(entrenamiento, corte, 6, dinamicas, "id_producto", "anio_mes") is None
    assert not any(c.startswith("precio_rel") or c.startswith("var_") for c in entrenamiento)


def test_la_ablacion_de_precio_cambia_la_prediccion():
    """Guarda contra el modo de falla más aburrido: que el interruptor no haga nada y la
    ablación de M2.3 mida dos veces lo mismo."""
    historia = _historia(n_productos=6, n_meses=40)
    corte = historia["anio_mes"].max()

    con = _predecir(historia, corte, h=6, usar_precio=True)
    sin = _predecir(historia, corte, h=6, usar_precio=False)

    assert not np.allclose(con[NOMBRE_MODELO], sin[NOMBRE_MODELO])


# --------------------------------------------------------------------------------------
# 3. Casos degenerados
# --------------------------------------------------------------------------------------


def test_una_serie_de_un_mes_no_tira_abajo_la_corrida():
    """El caso que hacía explotar a `AutoETS`/`AutoTheta` en M1.5: un producto recién
    entrado al catálogo en un corte temprano. Acá no puede recibir predicción —no tiene
    lags— pero **no puede impedir que el resto la reciba**."""
    historia = _historia(n_productos=4, n_meses=30)
    corte = historia["anio_mes"].max()
    nuevo = pd.DataFrame(
        {
            "id_producto": [99],
            "anio_mes": [corte],
            "unidades": [5.0],
            "precio_prom": [500.0],
            "revenue": [2500.0],
        }
    )
    historia = pd.concat([historia, nuevo], ignore_index=True)

    pred = predecir_global(
        historia, corte, 6, {"catalogo": _catalogo(4)}, hiperparametros=HIPER_TEST
    )

    assert pred["id_producto"].nunique() >= 4
    assert pred[NOMBRE_MODELO].notna().any()


def test_sin_catalogo_corre_igual_con_las_features_en_nulo():
    """El esquema de M2.2 es estable sin catálogo (columnas presentes, en `NaN`), así que
    el modelo tiene que correr — peor, pero correr. Es el caso de los 221 productos
    `SIN CATEGORIA` llevado al extremo."""
    historia = _historia(n_productos=4, n_meses=30)
    corte = historia["anio_mes"].max()

    pred = predecir_global(historia, corte, 6, None, hiperparametros=HIPER_TEST)

    assert len(pred) == 4 * 6
    assert pred[NOMBRE_MODELO].notna().all()


def test_una_serie_toda_en_cero_no_rompe():
    """Con 42% de series intermitentes, una serie sin ninguna venta en la ventana visible
    es un caso real, no un borde inventado (ADR-010 la densifica a ceros explícitos)."""
    historia = _historia(n_productos=4, n_meses=30)
    historia.loc[historia["id_producto"] == 1, "unidades"] = 0.0
    corte = historia["anio_mes"].max()

    pred = predecir_global(
        historia, corte, 6, {"catalogo": _catalogo(4)}, hiperparametros=HIPER_TEST
    )

    de_la_serie = pred[pred["id_producto"] == 1][NOMBRE_MODELO]
    assert de_la_serie.notna().all()
    assert (de_la_serie >= 0).all()


def test_un_producto_sin_ancla_no_tira_abajo_la_corrida():
    """El caso que hizo abortar la primera corrida de ablaciones, y que ningún fixture
    anterior tocaba porque todos tenían precio siempre.

    `mlforecast` valida que una `static_feature` no cambie en el tiempo comparando el valor
    del primer mes contra el del último. La comparación es `!=`, y **`NaN != NaN` es
    `True`**, así que un producto **sin ancla** —`NaN` en todas sus filas, o sea que
    justamente no cambia— aborta las 18 corridas con "its values change over time". Alcanza
    con uno. Medido sobre el sintético: 1 o 2 productos por corte.

    Por eso `precio_ancla` viaja por `X_df` y no por `static_features`, aunque
    conceptualmente sea estática.
    """
    historia = _historia(n_productos=6, n_meses=30)
    # un producto que solo tiene meses de neto cero cerca del corte: sin precio observado
    # en la ventana del ancla, la cascada no tiene de dónde sacarlo
    sin_precio = historia["id_producto"] == 2
    historia.loc[sin_precio, "precio_prom"] = np.nan
    historia.loc[sin_precio, "revenue"] = np.nan
    corte = historia["anio_mes"].max()

    pred = predecir_global(
        historia, corte, 6, {"catalogo": _catalogo()}, hiperparametros=HIPER_TEST
    )

    assert pred["id_producto"].nunique() == 6
    assert pred[NOMBRE_MODELO].notna().all()


# --------------------------------------------------------------------------------------
# 4. Cuantiles (M2.4)
# --------------------------------------------------------------------------------------


def test_los_cuantiles_no_mueven_el_pronostico_puntual():
    """**Condición de la unidad, no una prolijidad.** `GlobalLGBM` es el pronóstico puntual
    que M2.3 midió contra el piso (WAPE 0,2953 a h=1) y con el que M2.5 va a comparar. Si
    agregar los cuantiles lo moviera aunque sea un poco, ese número dejaría de ser el medido
    y habría que re-correr M2.3 — sin que nada avisara.

    `MLForecast` ajusta cada modelo por separado sobre la misma matriz de features, así que
    la igualdad tiene que ser **exacta**, no aproximada. Se pide con hiperparámetros
    determinísticos por la misma razón que el test de leakage.
    """
    historia = _historia(n_productos=6, n_meses=40)
    corte = historia["anio_mes"].max()

    solo_punto = _predecir(historia, corte, h=6)
    con_cuantiles = _predecir(historia, corte, h=6, cuantiles=CUANTILES_ESTANDAR)

    pd.testing.assert_series_equal(
        solo_punto[NOMBRE_MODELO], con_cuantiles[NOMBRE_MODELO], check_exact=True
    )


def test_devuelve_una_columna_por_cuantil_y_ninguna_negativa():
    historia = _historia(n_productos=6, n_meses=40)
    corte = historia["anio_mes"].max()

    pred = _predecir(historia, corte, h=6, cuantiles=CUANTILES_ESTANDAR)

    esperadas = {nombre_de_cuantil(q) for q in CUANTILES_ESTANDAR}
    assert esperadas <= set(pred.columns)
    assert set(pred.columns) == {"id_producto", "anio_mes", NOMBRE_MODELO} | esperadas
    for columna in esperadas:
        assert (pred[columna] >= 0).all(), f"{columna} predice demanda negativa"


def test_el_p90_queda_por_encima_del_p10_en_una_serie_con_ruido():
    """No es una identidad —los tres modelos se ajustan independientes y **pueden**
    cruzarse, por eso existe `tasa_de_cruce`— pero sobre una serie con varianza real el
    orden tiene que darse. Si no se diera, el `alpha` estaría mal cableado y el intervalo
    saldría invertido: seguiría "cubriendo" en las tablas y no significaría nada.
    """
    historia = _historia(n_productos=6, n_meses=48)
    corte = historia["anio_mes"].max()

    pred = _predecir(historia, corte, h=6, cuantiles=CUANTILES_ESTANDAR)

    p10, p90 = pred[nombre_de_cuantil(0.1)], pred[nombre_de_cuantil(0.9)]
    assert (p90 >= p10).all()
    assert (p90 > p10).any(), "el intervalo es de ancho cero: no hay nada que calibrar"


def test_un_cuantil_fuera_de_rango_corta():
    """`alpha` fuera de (0,1) no es un cuantil. LightGBM lo acepta y entrena cualquier cosa,
    así que la guarda va acá."""
    historia = _historia(n_productos=4, n_meses=30)
    corte = historia["anio_mes"].max()

    with pytest.raises(ValueError, match="cuantil"):
        _predecir(historia, corte, h=3, cuantiles=(0.1, 1.5))


@pytest.mark.innegociable
def test_los_cuantiles_tampoco_miran_el_futuro():
    """La red de M1.3 sobre las columnas nuevas.

    Superficie nueva es superficie sin cubrir: el `X_df` de M2.3 ya está fijado, pero nada
    garantiza que los modelos de cuantil reciban el mismo trato si alguien toca
    `_armar_modelos`. Un P90 que viera el futuro daría una cobertura empírica espectacular —
    justo el número del gate de esta unidad.
    """
    historia = _historia(n_productos=5, n_meses=36)
    cortes = [pd.Timestamp("2023-01-01"), pd.Timestamp("2023-06-01")]

    verificar_sin_leakage(
        lambda datos, corte: _predecir(
            datos, corte, h=3, cuantiles=CUANTILES_ESTANDAR
        ).sort_values(["id_producto", "anio_mes"])[nombre_de_cuantil(0.9)],
        historia,
        cortes,
    )


def test_cobertura_esperada_avisa_cuando_las_series_son_cortas():
    """Es la cota superior de cobertura del global: `mlforecast` descarta en silencio
    (`dropna=True`) las filas sin lags completos, así que una serie más corta que el lag
    más largo no entrena ni recibe predicción. Sin este número, una corrida con cobertura
    baja no se sabe si es del modelo o del catálogo."""
    largas = _historia(n_productos=4, n_meses=30)
    cortas = _historia(n_productos=4, n_meses=5, semilla=3)
    cortas["id_producto"] += 100

    assert cobertura_esperada(largas) == 1.0
    assert cobertura_esperada(cortas) == 0.0
    assert cobertura_esperada(pd.concat([largas, cortas], ignore_index=True)) == 0.5


# --------------------------------------------------------------------------------------
# 6. Features de dispersión (M3.0)
# --------------------------------------------------------------------------------------


def test_apagado_no_cambia_nada_del_modelo_de_M2():
    """**La garantía que protege las tablas congeladas.** El `id` de corrida es hash de
    configuración + datos y **no incluye las features**, así que si el default de
    `usar_dispersion` moviera el pronóstico, las tablas de M2 darían otros números bajo el
    mismo `id` y nada lo detectaría. Igualdad exacta, no aproximada.
    """
    historia, corte = _historia(), pd.Timestamp("2023-06-01")

    sin_flag = _predecir(historia, corte, h=6)
    apagado = _predecir(historia, corte, h=6, usar_dispersion=False)

    pd.testing.assert_frame_equal(sin_flag, apagado, check_exact=True)


def test_encendido_si_cambia_el_pronostico():
    """El complemento del anterior: si encender el interruptor **no** cambiara nada, el test
    de arriba pasaría por una razón equivocada (que la feature no llega al modelo) y M3.0
    mediría un efecto nulo creyendo haber medido el efecto de la dispersión."""
    historia, corte = _historia(), pd.Timestamp("2023-06-01")

    apagado = _predecir(historia, corte, h=6, usar_dispersion=False)
    encendido = _predecir(historia, corte, h=6, usar_dispersion=True)

    assert not np.allclose(
        apagado[NOMBRE_MODELO].to_numpy(), encendido[NOMBRE_MODELO].to_numpy()
    )


def test_la_dispersion_agrega_desvio_y_cv_en_las_tres_ventanas():
    apagadas = armar_lag_transforms(usar_dispersion=False)[1]
    encendidas = armar_lag_transforms(usar_dispersion=True)[1]

    assert len(apagadas) == len(VENTANAS_MEDIA_MOVIL)
    # media + desvío + CV por ventana
    assert len(encendidas) == len(VENTANAS_MEDIA_MOVIL) + 2 * len(VENTANAS_DISPERSION)
    nombres = [type(t).__name__ for t in encendidas]
    assert nombres.count("RollingStd") == len(VENTANAS_DISPERSION)
    assert nombres.count("Combine") == len(VENTANAS_DISPERSION)


def test_cada_llamada_devuelve_instancias_nuevas():
    """Los objetos de `mlforecast` llevan estado al transformar. Compartir una instancia
    entre dos `MLForecast` no falla: devuelve otro número."""
    primera = armar_lag_transforms(usar_dispersion=True)[1]
    segunda = armar_lag_transforms(usar_dispersion=True)[1]

    assert all(a is not b for a, b in zip(primera, segunda, strict=True))


def test_el_cv_da_nulo_y_no_infinito_cuando_la_ventana_esta_dormida():
    """Una serie intermitente tiene ventanas de media cero, y `0/0` tiene que dar `NaN`:
    LightGBM le da rama propia al nulo, mientras que un `inf` envenena los cortes del árbol.
    """
    from mlforecast import MLForecast

    dormida = pd.DataFrame(
        {
            "id_producto": ["P0"] * 24,
            "anio_mes": pd.date_range("2023-01-01", periods=24, freq="MS"),
            "unidades": [0.0, 0.0, 0.0, 5.0, 0.0, 0.0, 0.0, 0.0, 12.0, 0.0, 0.0, 0.0] * 2,
        }
    )
    fcst = MLForecast(
        models=[], freq="MS", lags=[1], lag_transforms=armar_lag_transforms(True)
    )
    preparado = fcst.preprocess(
        dormida, id_col="id_producto", time_col="anio_mes", target_col="unidades", dropna=False
    )

    columnas_cv = [c for c in preparado.columns if "truediv" in c]
    assert columnas_cv, "no se generó ninguna columna de CV"
    for columna in columnas_cv:
        assert not np.isinf(preparado[columna]).any()
        assert preparado[columna].isna().any()
