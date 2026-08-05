"""Tests de la selección prospectiva y la cascada por disponibilidad (M1.9, ADR-016).

Tres focos, uno por decisión de la unidad:

1. **Observabilidad** — en el corte `t` la selección solo puede mirar el error cuyo mes
   objetivo ya ocurrió (`anio_mes <= t`). El gate de la unidad
   (`test_la_seleccion_no_mira_el_futuro`, marcado `innegociable`) es la idea de la red de
   M1.3 aplicada a la *elección del modelo*: perturbar el futuro no puede mover los
   ganadores del pasado. Es el hueco que M1.3 no cubre — ahí cada predicción individual ya
   era limpia, lo que usaba el futuro era decidir cuál mirar.
2. **Arranque** — el primer corte no tiene nada observado y cae entero al fallback, con el
   orden completo detrás para que la cascada tenga a dónde bajar.
3. **Cascada** — si el ganador no predijo esa celda se usa el siguiente disponible; si no
   predijo **ninguno**, la celda queda en `NaN` y no se inventa.

Los fixtures usan modelos ficticios y `estacionalidad=1` para no necesitar 13 meses de
historia por serie, igual que `test_modelado_seleccion.py`.
"""

import numpy as np
import pandas as pd
import pytest

from motor.modelado.seleccion import (
    armar_reporte_con_cascada,
    elegir_mejor_por_corte,
    elegir_mejor_por_serie,
    estabilidad_de_la_seleccion,
    resumen_de_cascada,
)

MODELOS_FALSOS = ["modelo_a", "modelo_b"]
FALLBACK_FALSO = "modelo_a"

COLUMNAS = ["id_producto", "corte", "anio_mes", "real", "modelo_a", "modelo_b"]


def _reporte(filas: list[tuple]) -> pd.DataFrame:
    df = pd.DataFrame(filas, columns=COLUMNAS)
    df["corte"] = pd.to_datetime(df["corte"])
    df["anio_mes"] = pd.to_datetime(df["anio_mes"])
    return df


def _train(ids: list[int], meses: int = 7) -> pd.DataFrame:
    """Historia con escala MASE no nula (estacionalidad=1): sin eso el MASE queda
    indefinido, todo cae al fallback y cualquier test de selección pasa por el motivo
    equivocado."""
    fechas = pd.date_range("2025-09-01", periods=meses, freq="MS")
    valores = [10.0, 12.0, 9.0, 11.0, 10.0, 12.0, 9.0][:meses]
    return pd.concat(
        [pd.DataFrame({"id_producto": i, "anio_mes": fechas, "unidades": valores}) for i in ids],
        ignore_index=True,
    )


def _ganador(ranking: pd.DataFrame, corte: str) -> str:
    fila = ranking[(ranking["corte"] == pd.Timestamp(corte)) & (ranking["rango"] == 0)]
    return fila["modelo"].iloc[0]


# --------------------------------------------------------------------------------------
# 1. Observabilidad
# --------------------------------------------------------------------------------------


def test_un_horizonte_que_todavia_no_se_observo_no_puede_decidir():
    """El corazón de la decisión 1, y lo que separa "prospectivo" de "casi prospectivo".

    `modelo_a` acierta a h=1 y erra feo a h=2; `modelo_b` al revés. Al seleccionar en
    2026-02 lo único que ya se observó del corte 2026-01 es su h=1 (mes objetivo 2026-02).
    El h=2 apunta a 2026-03: en 2026-02 **nadie sabe todavía** que `modelo_b` iba a
    acertarlo.

    Los números están elegidos para que las dos lecturas den distinto: con solo h=1 gana
    `modelo_a` (error 0 vs 20); mirando el corte 2026-01 entero gana `modelo_b`
    (error medio 10 vs 45). Si este test pasa con las dos, no está probando nada.

    Y el fallback es `modelo_b` **a propósito**, aunque acá no se use: si fuera
    `modelo_a`, apretar el filtro de más (`< corte` en vez de `<= corte`) dejaría la
    selección sin nada observado, caería al fallback y el test seguiría verde por el
    motivo equivocado.
    """
    reporte = _reporte(
        [
            (1, "2026-01-01", "2026-02-01", 10.0, 10.0, 30.0),
            (1, "2026-01-01", "2026-03-01", 10.0, 100.0, 10.0),
            (1, "2026-02-01", "2026-03-01", 10.0, 10.0, 30.0),
            (1, "2026-02-01", "2026-04-01", 10.0, 100.0, 10.0),
        ]
    )

    ranking = elegir_mejor_por_corte(
        reporte,
        _train([1], meses=5),
        modelos=MODELOS_FALSOS,
        estacionalidad=1,
        modelo_fallback="modelo_b",
    )

    assert _ganador(ranking, "2026-02-01") == "modelo_a"
    # el orden completo, no solo el ganador: es lo que consume la cascada
    en_2026_02 = ranking[ranking["corte"] == pd.Timestamp("2026-02-01")]
    assert list(en_2026_02.sort_values("rango")["modelo"]) == ["modelo_a", "modelo_b"]


def _reporte_dos_productos_tres_cortes() -> pd.DataFrame:
    """P1: gana `modelo_a` en todas las filas. P2: gana `modelo_b`. Reales todos en 10,0
    para que perturbarlos después mueva el ganador de forma inequívoca."""
    filas = []
    for corte, objetivos in [
        ("2026-01-01", ["2026-02-01", "2026-03-01"]),
        ("2026-02-01", ["2026-03-01", "2026-04-01"]),
        ("2026-03-01", ["2026-04-01", "2026-05-01"]),
    ]:
        for objetivo in objetivos:
            filas.append((1, corte, objetivo, 10.0, 10.0, 30.0))
            filas.append((2, corte, objetivo, 10.0, 30.0, 10.0))
    return _reporte(filas)


@pytest.mark.innegociable
def test_la_seleccion_no_mira_el_futuro():
    """**El gate de M1.9.** Perturbar los reales posteriores al corte `T` no puede mover
    los ganadores de los cortes `<= T`.

    Es la red de M1.3 corrida un nivel: allá el peligro era que un predictor viera el
    futuro *de los datos*; acá que lo vea la *elección de qué predictor mirar*. Con la
    selección retrospectiva de M1.7 este test falla, y esa es exactamente la diferencia
    que M1.9 introduce.

    La segunda mitad —que el corte posterior a `T` **sí** cambie— no es decoración: sin
    ella el test pasaría también si la perturbación no hubiera perturbado nada, que es
    cómo dos fixtures de M2.2 pasaron en verde sin probar nada.
    """
    corte_limite = pd.Timestamp("2026-02-01")
    reporte = _reporte_dos_productos_tres_cortes()
    train = _train([1, 2])

    def rankear(rep: pd.DataFrame, tr: pd.DataFrame) -> pd.DataFrame:
        return elegir_mejor_por_corte(
            rep, tr, modelos=MODELOS_FALSOS, estacionalidad=1, modelo_fallback=FALLBACK_FALSO
        )

    original = rankear(reporte, train)

    futuro_perturbado = reporte.copy()
    posterior = futuro_perturbado["anio_mes"] > corte_limite
    futuro_perturbado.loc[posterior, "real"] = 30.0
    train_perturbado = train.copy()
    train_perturbado.loc[train_perturbado["anio_mes"] > corte_limite, "unidades"] = 300.0

    perturbado = rankear(futuro_perturbado, train_perturbado)

    def hasta_el_corte(r: pd.DataFrame) -> pd.DataFrame:
        return (
            r[r["corte"] <= corte_limite]
            .sort_values(["id_producto", "corte", "rango"])
            .reset_index(drop=True)
        )

    pd.testing.assert_frame_equal(hasta_el_corte(original), hasta_el_corte(perturbado))

    # y la perturbación tiene que haber servido de algo
    assert _ganador(original, "2026-03-01") == "modelo_a"
    assert _ganador(perturbado, "2026-03-01") == "modelo_b"


def test_la_prospectiva_y_la_retrospectiva_no_son_la_misma_funcion():
    """Guarda contra el modo de falla más aburrido: que las dos rutas terminen dando
    siempre lo mismo y ninguno de los tests de arriba pruebe nada.

    P1 arranca ganándolo `modelo_b` y termina ganándolo `modelo_a`. Mirando todos los
    cortes a la vez gana `modelo_a`; en 2026-02, con lo único observado hasta ahí, gana
    `modelo_b`."""
    reporte = _reporte(
        [
            (1, "2026-01-01", "2026-02-01", 10.0, 40.0, 10.0),
            (1, "2026-02-01", "2026-03-01", 10.0, 10.0, 60.0),
            (1, "2026-03-01", "2026-04-01", 10.0, 10.0, 60.0),
        ]
    )
    train = _train([1])

    retrospectivo = elegir_mejor_por_serie(
        reporte, train, modelos=MODELOS_FALSOS, estacionalidad=1, modelo_fallback=FALLBACK_FALSO
    )
    prospectivo = elegir_mejor_por_corte(
        reporte, train, modelos=MODELOS_FALSOS, estacionalidad=1, modelo_fallback=FALLBACK_FALSO
    )

    assert retrospectivo["modelo_ganador"].iloc[0] == "modelo_a"
    assert _ganador(prospectivo, "2026-02-01") == "modelo_b"


# --------------------------------------------------------------------------------------
# 2. Arranque
# --------------------------------------------------------------------------------------


def test_el_primer_corte_cae_entero_al_fallback():
    """Decisión 2: no se exige mínimo de evidencia, pero en el primer corte no hay
    ninguna — todos sus objetivos son posteriores a él. Cae al fallback con el resto
    detrás; sin ese orden completo la cascada no tendría a dónde bajar."""
    reporte = _reporte_dos_productos_tres_cortes()

    ranking = elegir_mejor_por_corte(
        reporte,
        _train([1, 2]),
        modelos=MODELOS_FALSOS,
        estacionalidad=1,
        modelo_fallback="modelo_b",
    )

    primero = ranking[ranking["corte"] == pd.Timestamp("2026-01-01")]
    assert set(primero.loc[primero["rango"] == 0, "modelo"]) == {"modelo_b"}
    assert set(primero.loc[primero["rango"] == 1, "modelo"]) == {"modelo_a"}
    # y las dos series están: ninguna se queda sin ranking
    assert set(primero["id_producto"]) == {1, 2}


def test_una_serie_sin_error_observable_no_se_queda_sin_ranking():
    """P2 entra al catálogo tarde: en 2026-02 no tiene ni una fila observada. Tiene que
    salir igual con ranking completo, porque `armar_reporte_con_cascada` indexa por
    `(serie, corte)` y una serie ausente rompería la garantía de M1.0 de que ninguna
    celda del reporte se borra."""
    reporte = _reporte(
        [
            (1, "2026-01-01", "2026-02-01", 10.0, 10.0, 30.0),
            (1, "2026-02-01", "2026-03-01", 10.0, 10.0, 30.0),
            (2, "2026-02-01", "2026-03-01", 10.0, 10.0, 30.0),
        ]
    )

    ranking = elegir_mejor_por_corte(
        reporte,
        _train([1, 2], meses=5),
        modelos=MODELOS_FALSOS,
        estacionalidad=1,
        modelo_fallback=FALLBACK_FALSO,
    )

    en_2026_02 = ranking[ranking["corte"] == pd.Timestamp("2026-02-01")]
    p2 = en_2026_02[en_2026_02["id_producto"] == 2]
    assert list(p2.sort_values("rango")["modelo"]) == ["modelo_a", "modelo_b"]


# --------------------------------------------------------------------------------------
# 3. Cascada por disponibilidad
# --------------------------------------------------------------------------------------


def _ranking_fijo(pares: list[tuple], orden: list[str]) -> pd.DataFrame:
    filas = [
        (id_producto, pd.Timestamp(corte), modelo, rango)
        for id_producto, corte in pares
        for rango, modelo in enumerate(orden)
    ]
    return pd.DataFrame(filas, columns=["id_producto", "corte", "modelo", "rango"])


def test_la_cascada_baja_al_siguiente_cuando_el_ganador_no_predijo():
    """El caso de las 5.655 filas de §5.6.1: el ganador no cubre el horizonte y otros
    candidatos sí. Antes la celda quedaba vacía; ahora la llena el segundo del ranking."""
    reporte = _reporte(
        [
            (1, "2026-02-01", "2026-03-01", 10.0, 11.0, 50.0),
            (1, "2026-02-01", "2026-04-01", 10.0, np.nan, 50.0),
        ]
    )
    ranking = _ranking_fijo([(1, "2026-02-01")], ["modelo_a", "modelo_b"])

    resultado = armar_reporte_con_cascada(
        reporte, ranking, modelos=MODELOS_FALSOS, modelo_fallback=FALLBACK_FALSO
    )

    assert list(resultado["pred"]) == [11.0, 50.0]
    assert list(resultado["modelo_usado"]) == ["modelo_a", "modelo_b"]
    assert list(resultado["rango_usado"]) == [0.0, 1.0]


def test_el_resumen_de_cascada_separa_las_tres_procedencias():
    """Las tres filas que hacen legible el piso prospectivo: lo que puso el ganador, lo
    que puso la cascada, y lo que no pudo poner nadie."""
    reporte = _reporte(
        [
            (1, "2026-02-01", "2026-03-01", 10.0, 11.0, 50.0),
            (1, "2026-02-01", "2026-04-01", 10.0, np.nan, 50.0),
            (1, "2026-02-01", "2026-05-01", 10.0, np.nan, np.nan),
        ]
    )
    ranking = _ranking_fijo([(1, "2026-02-01")], ["modelo_a", "modelo_b"])

    resultado = armar_reporte_con_cascada(
        reporte, ranking, modelos=MODELOS_FALSOS, modelo_fallback=FALLBACK_FALSO
    )
    resumen = resumen_de_cascada(resultado).set_index("origen")

    assert resumen.loc["ganador del corte", "filas"] == 1
    assert resumen.loc["cascada", "filas"] == 1
    assert resumen.loc["sin predicción (ningún candidato)", "filas"] == 1


def test_si_ningun_candidato_predijo_la_celda_queda_vacia():
    """La otra mitad de la brecha de cobertura: altas de catálogo, donde no hay historia
    que ningún baseline pueda usar. **No se inventa un número.** Distinguir esto del caso
    de arriba es lo que le permite a M2.5 comparar a igual cobertura."""
    reporte = _reporte(
        [
            (1, "2026-02-01", "2026-03-01", 10.0, 11.0, 50.0),
            (1, "2026-02-01", "2026-04-01", 10.0, np.nan, np.nan),
        ]
    )
    ranking = _ranking_fijo([(1, "2026-02-01")], ["modelo_a", "modelo_b"])

    resultado = armar_reporte_con_cascada(
        reporte, ranking, modelos=MODELOS_FALSOS, modelo_fallback=FALLBACK_FALSO
    )

    assert resultado["pred"].iloc[0] == 11.0
    assert pd.isna(resultado["pred"].iloc[1])
    assert resultado["modelo_usado"].iloc[1] is None


def test_la_cascada_no_borra_ninguna_celda():
    """Garantía de M1.0: el reporte que entra y el que sale tienen las mismas filas. Si
    las celdas sin predicción desaparecieran, omitir series difíciles mejoraría el score
    sin dejar rastro."""
    reporte = _reporte_dos_productos_tres_cortes()
    reporte.loc[::2, "modelo_a"] = np.nan
    pares = [(i, c) for i in (1, 2) for c in ("2026-01-01", "2026-02-01", "2026-03-01")]
    ranking = _ranking_fijo(pares, ["modelo_a", "modelo_b"])

    resultado = armar_reporte_con_cascada(
        reporte, ranking, modelos=MODELOS_FALSOS, modelo_fallback=FALLBACK_FALSO
    )

    assert len(resultado) == len(reporte)
    assert resultado["pred"].notna().all()


def test_un_par_sin_ranking_cae_al_orden_fijo_en_vez_de_romper():
    """P2 no está en el ranking. No puede quedar sin `pred` ni tirar excepción: usa el
    orden fijo que arranca por el fallback, misma regla que las series sin MASE."""
    reporte = _reporte(
        [
            (1, "2026-02-01", "2026-03-01", 10.0, 11.0, 50.0),
            (2, "2026-02-01", "2026-03-01", 10.0, 11.0, 50.0),
        ]
    )
    ranking = _ranking_fijo([(1, "2026-02-01")], ["modelo_a", "modelo_b"])

    resultado = armar_reporte_con_cascada(
        reporte, ranking, modelos=MODELOS_FALSOS, modelo_fallback="modelo_b"
    )

    assert resultado.loc[resultado["id_producto"] == 2, "modelo_usado"].iloc[0] == "modelo_b"


def test_la_cascada_preserva_la_corrida():
    """`.attrs` de pandas se pierde en varias operaciones y sin la corrida la tabla no es
    congelable (roadmap-motor.md §12.2)."""
    reporte = _reporte([(1, "2026-02-01", "2026-03-01", 10.0, 11.0, 50.0)])
    reporte.attrs["corrida"] = "id-de-prueba"
    ranking = _ranking_fijo([(1, "2026-02-01")], ["modelo_a", "modelo_b"])

    resultado = armar_reporte_con_cascada(
        reporte, ranking, modelos=MODELOS_FALSOS, modelo_fallback=FALLBACK_FALSO
    )

    assert resultado.attrs["corrida"] == "id-de-prueba"


def test_un_ranking_con_modelos_ajenos_corta_con_mensaje_claro():
    reporte = _reporte([(1, "2026-02-01", "2026-03-01", 10.0, 11.0, 50.0)])
    ranking = _ranking_fijo([(1, "2026-02-01")], ["modelo_a", "inventado"])

    with pytest.raises(ValueError, match="nombra modelos"):
        armar_reporte_con_cascada(
            reporte, ranking, modelos=MODELOS_FALSOS, modelo_fallback=FALLBACK_FALSO
        )


# --------------------------------------------------------------------------------------
# Lectura del resultado
# --------------------------------------------------------------------------------------


def test_estabilidad_cuenta_los_cambios_de_ganador_por_serie():
    """El número que dice cuánto compraba el hindsight: si el ganador prospectivo casi
    nunca cambia, el piso retrospectivo no estaba haciendo gran diferencia."""
    ranking = pd.concat(
        [
            _ranking_fijo([(1, "2026-01-01")], ["modelo_a", "modelo_b"]),
            _ranking_fijo([(1, "2026-02-01")], ["modelo_a", "modelo_b"]),
            _ranking_fijo([(1, "2026-03-01")], ["modelo_a", "modelo_b"]),
            _ranking_fijo([(2, "2026-01-01")], ["modelo_a", "modelo_b"]),
            _ranking_fijo([(2, "2026-02-01")], ["modelo_b", "modelo_a"]),
            _ranking_fijo([(2, "2026-03-01")], ["modelo_a", "modelo_b"]),
        ],
        ignore_index=True,
    )

    tabla = estabilidad_de_la_seleccion(ranking).set_index("cambios")

    assert tabla.loc[0, "n_series"] == 1  # P1 nunca cambia
    assert tabla.loc[2, "n_series"] == 1  # P2 cambia dos veces
