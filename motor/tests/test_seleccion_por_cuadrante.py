"""Tests de la selección por `(cuadrante, corte)` (M3.1a, `roadmap-motor.md` §7.1).

Cinco focos, uno por decisión de la unidad:

1. **Observabilidad** — la regla de ADR-016 tiene que seguir valiendo cuando el ranking se
   aprende por grupo. El gate (`test_la_seleccion_por_cuadrante_no_mira_el_futuro`,
   `innegociable`) es el de M1.9 corrido un nivel más: agrupar no puede ser una puerta
   trasera por donde entre el futuro.
2. **Que agrupe de verdad** — el ranking es idéntico dentro de un cuadrante y puede diferir
   entre cuadrantes. Los dos lados hacen falta: sin el primero esto sería la selección por
   serie con pasos de más, sin el segundo sería un único ranking global.
3. **El cuadrante se toma al corte**, no al final del backtest (§12.2).
4. **`sin_actividad` es un grupo más** y aprende su propio ranking, no cae al fallback.
5. **El formato de salida es el de `elegir_mejor_por_corte`**, que es lo que permite que
   `armar_reporte_con_cascada` no se entere de cuál de las dos lo produjo.

Los fixtures usan modelos ficticios y `estacionalidad=1` para no necesitar 13 meses de
historia por serie, igual que `test_modelado_seleccion_prospectiva.py`.

**Cómo están armados los errores, porque es lo que hace que los tests prueben algo.** En el
cuadrante `suave` las dos series tienen ganadores *opuestos* entre sí (P1 lo gana `modelo_a`
por mucho, P2 lo gana `modelo_b` por poco), así que la selección **por serie** les daría
rankings distintos y la **por cuadrante** les da el mismo. Un fixture donde las dos series
del grupo ya coincidieran pasaría en verde con cualquiera de las dos implementaciones — es
el modo de falla de los dos fixtures de M2.2 que la mutación cazó.
"""

import numpy as np
import pandas as pd
import pytest

from motor.clasificacion import SIN_ACTIVIDAD, clasificar_por_corte
from motor.modelado.seleccion import (
    armar_reporte_con_cascada,
    elegir_mejor_por_corte,
    elegir_mejor_por_cuadrante,
    ganadores_de_cuadrante,
)

MODELOS_FALSOS = ["modelo_a", "modelo_b"]
FALLBACK_FALSO = "modelo_a"

COLUMNAS = ["id_producto", "corte", "anio_mes", "real", "modelo_a", "modelo_b"]

CORTES = ["2026-01-01", "2026-02-01", "2026-03-01"]
OBJETIVOS = {
    "2026-01-01": ["2026-02-01", "2026-03-01"],
    "2026-02-01": ["2026-03-01", "2026-04-01"],
    "2026-03-01": ["2026-04-01", "2026-05-01"],
}

# (pred_a, pred_b) contra un real de 10. El primero de cada par es el error de `modelo_a`.
PATRON = {
    1: (10.0, 40.0),  # suave  — la gana `modelo_a` por 30
    2: (22.0, 10.0),  # suave  — la gana `modelo_b` por 12  → el grupo lo gana `modelo_a`
    3: (40.0, 10.0),  # lumpy  — la gana `modelo_b`
    4: (40.0, 10.0),  # lumpy  — idem
    5: (40.0, 10.0),  # sin_actividad — la gana `modelo_b`, o sea NO el fallback
}

CUADRANTE_DE_SERIE = {1: "suave", 2: "suave", 3: "lumpy", 4: "lumpy", 5: SIN_ACTIVIDAD}


def _reporte(patron: dict[int, tuple[float, float]] | None = None) -> pd.DataFrame:
    filas = []
    for corte in CORTES:
        for objetivo in OBJETIVOS[corte]:
            for serie, (pred_a, pred_b) in (patron or PATRON).items():
                filas.append((serie, corte, objetivo, 10.0, pred_a, pred_b))
    df = pd.DataFrame(filas, columns=COLUMNAS)
    df["corte"] = pd.to_datetime(df["corte"])
    df["anio_mes"] = pd.to_datetime(df["anio_mes"])
    return df


def _train(ids: list[int], meses: int = 7) -> pd.DataFrame:
    """Historia con escala MASE no nula (estacionalidad=1). Sin esto el MASE queda
    indefinido, todo cae al fallback y los tests pasarían por el motivo equivocado."""
    fechas = pd.date_range("2025-09-01", periods=meses, freq="MS")
    valores = [10.0, 12.0, 9.0, 11.0, 10.0, 12.0, 9.0][:meses]
    return pd.concat(
        [pd.DataFrame({"id_producto": i, "anio_mes": fechas, "unidades": valores}) for i in ids],
        ignore_index=True,
    )


def _cuadrantes(por_corte: dict[str, dict[int, str]]) -> pd.DataFrame:
    """La tabla larga que produce `clasificar_por_corte`, armada a mano para fijar el
    cuadrante de cada serie en cada corte sin depender del clasificador."""
    filas = [
        {"corte": pd.Timestamp(corte), "id_producto": serie, "cuadrante": cuadrante}
        for corte, mapa in por_corte.items()
        for serie, cuadrante in mapa.items()
    ]
    return pd.DataFrame(filas)


def _cuadrantes_fijos() -> pd.DataFrame:
    return _cuadrantes({corte: CUADRANTE_DE_SERIE for corte in CORTES})


def _rankear(reporte: pd.DataFrame, train: pd.DataFrame, cuadrantes: pd.DataFrame):
    return elegir_mejor_por_cuadrante(
        reporte,
        train,
        modelos=MODELOS_FALSOS,
        estacionalidad=1,
        cuadrantes=cuadrantes,
        modelo_fallback=FALLBACK_FALSO,
    )


def _orden(ranking: pd.DataFrame, serie: int, corte: str) -> list[str]:
    """El ranking completo de una serie en un corte, de mejor a peor."""
    fila = ranking[
        (ranking["id_producto"] == serie) & (ranking["corte"] == pd.Timestamp(corte))
    ]
    return fila.sort_values("rango")["modelo"].tolist()


# --------------------------------------------------------------------------------------
# 1. Observabilidad — el gate de la unidad
# --------------------------------------------------------------------------------------


@pytest.mark.innegociable
def test_la_seleccion_por_cuadrante_no_mira_el_futuro():
    """**El gate de M3.1a.** Perturbar los reales posteriores al corte `T` no puede mover
    los rankings de los cortes `<= T`.

    Es el mismo gate que M1.9 (`test_la_seleccion_no_mira_el_futuro`) sobre la selección
    agrupada: promediar el MASE de todo un cuadrante toca más filas que promediar el de una
    serie, así que la regla `anio_mes <= corte` tiene más superficie por donde fallar.

    La segunda mitad —que el corte posterior a `T` **sí** se mueva— no es decoración: sin
    ella el test pasaría también si la perturbación no hubiera perturbado nada.
    """
    corte_limite = pd.Timestamp("2026-02-01")
    reporte = _reporte()
    train = _train([1, 2, 3, 4, 5])
    cuadrantes = _cuadrantes_fijos()

    original = _rankear(reporte, train, cuadrantes)

    perturbado_df = reporte.copy()
    posterior = perturbado_df["anio_mes"] > corte_limite
    # Se da vuelta el ganador del futuro: donde `modelo_a` acertaba ahora yerra.
    perturbado_df.loc[posterior, "modelo_a"] = 10.0
    perturbado_df.loc[posterior, "modelo_b"] = 200.0
    train_perturbado = train.copy()
    train_perturbado.loc[train_perturbado["anio_mes"] > corte_limite, "unidades"] = 300.0

    perturbado = _rankear(perturbado_df, train_perturbado, cuadrantes)

    def hasta_el_corte(r: pd.DataFrame) -> pd.DataFrame:
        return (
            r[r["corte"] <= corte_limite]
            .sort_values(["id_producto", "corte", "rango"])
            .reset_index(drop=True)
        )

    pd.testing.assert_frame_equal(hasta_el_corte(original), hasta_el_corte(perturbado))

    # y la perturbación tiene que haber servido de algo en el corte siguiente
    assert _orden(original, 3, "2026-03-01") == ["modelo_b", "modelo_a"]
    assert _orden(perturbado, 3, "2026-03-01") == ["modelo_a", "modelo_b"]


# --------------------------------------------------------------------------------------
# 2. Que agrupe de verdad — los dos lados
# --------------------------------------------------------------------------------------


def test_el_ranking_es_identico_dentro_del_cuadrante():
    """Las dos series de `suave` tienen ganadores opuestos **por serie** y aun así comparten
    ranking, porque lo que decide es el MASE promedio del cuadrante.

    Es el lado que distingue esta función de `elegir_mejor_por_corte`: ahí P2 elegiría
    `modelo_b` (es el que le gana a *ella*), acá se lleva el `modelo_a` que gana el grupo.
    """
    ranking = _rankear(_reporte(), _train([1, 2, 3, 4, 5]), _cuadrantes_fijos())

    for corte in ("2026-02-01", "2026-03-01"):
        assert _orden(ranking, 1, corte) == _orden(ranking, 2, corte)
        assert _orden(ranking, 1, corte) == ["modelo_a", "modelo_b"]

    # y la selección por serie, sobre el mismo reporte, las separa
    por_serie = elegir_mejor_por_corte(
        _reporte(),
        _train([1, 2, 3, 4, 5]),
        modelos=MODELOS_FALSOS,
        estacionalidad=1,
        modelo_fallback=FALLBACK_FALSO,
    )
    assert _orden(por_serie, 1, "2026-03-01") == ["modelo_a", "modelo_b"]
    assert _orden(por_serie, 2, "2026-03-01") == ["modelo_b", "modelo_a"]


def test_cuadrantes_distintos_pueden_tener_rankings_distintos():
    """El otro lado: si el promedio fuera global habría un solo ranking para todo el
    catálogo. `suave` se lo lleva `modelo_a` y `lumpy` `modelo_b`, en el mismo corte."""
    ranking = _rankear(_reporte(), _train([1, 2, 3, 4, 5]), _cuadrantes_fijos())

    assert _orden(ranking, 1, "2026-03-01") == ["modelo_a", "modelo_b"]
    assert _orden(ranking, 3, "2026-03-01") == ["modelo_b", "modelo_a"]


def test_el_primer_corte_no_tiene_nada_observado_y_cae_al_fallback():
    """Arranque: en el corte más viejo ningún objetivo ocurrió todavía, así que no hay MASE
    con qué rankear ningún grupo y todos caen al orden fijo del fallback — incluido `lumpy`,
    que en los cortes siguientes elige lo contrario."""
    ranking = _rankear(_reporte(), _train([1, 2, 3, 4, 5]), _cuadrantes_fijos())

    for serie in (1, 3, 5):
        assert _orden(ranking, serie, "2026-01-01") == [FALLBACK_FALSO, "modelo_b"]


# --------------------------------------------------------------------------------------
# 3. El cuadrante se toma al corte
# --------------------------------------------------------------------------------------


def test_el_cuadrante_se_toma_al_corte_y_no_al_final():
    """P1 es `suave` en 2026-02 y `lumpy` en 2026-03. Su ranking tiene que seguir al
    cuadrante **de cada corte**.

    Si la implementación clasificara una sola vez (con el último mes de los datos, que es el
    default de `clasificar_series`), P1 sería `lumpy` también en 2026-02 y se llevaría el
    ranking del grupo equivocado — mirando información posterior al corte. Es la trampa de
    §12.2 aplicada al ranking.
    """
    cambia = _cuadrantes(
        {
            "2026-01-01": {**CUADRANTE_DE_SERIE, 1: "suave"},
            "2026-02-01": {**CUADRANTE_DE_SERIE, 1: "suave"},
            "2026-03-01": {**CUADRANTE_DE_SERIE, 1: "lumpy"},
        }
    )
    ranking = _rankear(_reporte(), _train([1, 2, 3, 4, 5]), cambia)

    assert _orden(ranking, 1, "2026-02-01") == ["modelo_a", "modelo_b"]  # con `suave`
    assert _orden(ranking, 1, "2026-03-01") == ["modelo_b", "modelo_a"]  # con `lumpy`


# --------------------------------------------------------------------------------------
# 4. `sin_actividad` es un grupo más
# --------------------------------------------------------------------------------------


def test_sin_actividad_aprende_su_ranking_y_no_cae_al_fallback():
    """P5 está etiquetada `sin_actividad` y su error favorece a `modelo_b`, que es
    **distinto** del fallback. Si se la tratara como caso especial saldría `modelo_a`
    primero y el test lo detecta.

    Se decidió así (§7.1) porque mandarla al fallback sería reintroducir una regla fija por
    cuadrante, que es exactamente el enrutamiento por teoría que M1.7 midió peor que dejar
    competir con el dato.
    """
    ranking = _rankear(_reporte(), _train([1, 2, 3, 4, 5]), _cuadrantes_fijos())

    assert _orden(ranking, 5, "2026-03-01") == ["modelo_b", "modelo_a"]
    assert _orden(ranking, 5, "2026-03-01")[0] != FALLBACK_FALSO


def test_las_series_sin_fila_en_la_clasificacion_caen_a_sin_actividad():
    """Una serie que el clasificador no devolvió (no tiene ninguna fila en la ventana) no
    puede quedar sin ranking: la garantía de M1.0 es que ninguna celda del reporte se borra."""
    incompleta = _cuadrantes(
        {corte: {s: c for s, c in CUADRANTE_DE_SERIE.items() if s != 4} for corte in CORTES}
    )
    ranking = _rankear(_reporte(), _train([1, 2, 3, 4, 5]), incompleta)

    assert _orden(ranking, 4, "2026-03-01") == _orden(ranking, 5, "2026-03-01")
    assert len(_orden(ranking, 4, "2026-03-01")) == len(MODELOS_FALSOS)


def test_corta_si_la_clasificacion_no_cubre_todos_los_cortes():
    """Un corte faltante daría un ranking construido sobre un único grupo `sin_actividad`,
    con números plausibles y sin aviso. Mejor cortar."""
    sin_el_ultimo = _cuadrantes(
        {corte: CUADRANTE_DE_SERIE for corte in ("2026-01-01", "2026-02-01")}
    )
    with pytest.raises(ValueError, match="no cubre"):
        _rankear(_reporte(), _train([1, 2, 3, 4, 5]), sin_el_ultimo)


# --------------------------------------------------------------------------------------
# 5. Compatibilidad de formato — es lo que hace barata la unidad
# --------------------------------------------------------------------------------------


def test_el_formato_es_el_mismo_que_el_de_la_seleccion_por_serie():
    """Mismas columnas, mismos dtypes y el orden completo (un rango por modelo y por par
    `(serie, corte)`). Es la premisa de §7.1: si esto se cumple, la cascada y las
    comparaciones no se enteran de cuál de las dos produjo el ranking."""
    train = _train([1, 2, 3, 4, 5])
    por_cuadrante = _rankear(_reporte(), train, _cuadrantes_fijos())
    por_serie = elegir_mejor_por_corte(
        _reporte(), train, modelos=MODELOS_FALSOS, estacionalidad=1,
        modelo_fallback=FALLBACK_FALSO,
    )

    assert list(por_cuadrante.columns) == list(por_serie.columns)
    assert por_cuadrante.dtypes.to_dict() == por_serie.dtypes.to_dict()
    assert len(por_cuadrante) == len(por_serie)

    conteo = por_cuadrante.groupby(["id_producto", "corte"], observed=True).size()
    assert (conteo == len(MODELOS_FALSOS)).all()
    rangos = por_cuadrante.groupby(["id_producto", "corte"], observed=True)["rango"]
    assert (rangos.nunique() == len(MODELOS_FALSOS)).all()


def test_la_cascada_consume_el_ranking_por_cuadrante_sin_cambios():
    """`armar_reporte_con_cascada` toma este ranking tal cual y baja al siguiente candidato
    cuando el elegido no predijo esa celda.

    La cascada sigue siendo **por serie** aunque el ranking sea por cuadrante: acá P1 y P2
    comparten ranking (`modelo_a` primero) pero solo a P1 le falta la predicción de
    `modelo_a`, así que solo P1 baja a `modelo_b`.
    """
    reporte = _reporte()
    hueco = (reporte["id_producto"] == 1) & (reporte["corte"] == pd.Timestamp("2026-03-01"))
    reporte.loc[hueco, "modelo_a"] = np.nan

    ranking = _rankear(reporte, _train([1, 2, 3, 4, 5]), _cuadrantes_fijos())
    con_cascada = armar_reporte_con_cascada(
        reporte, ranking, modelos=MODELOS_FALSOS, modelo_fallback=FALLBACK_FALSO
    )

    del_corte = con_cascada[con_cascada["corte"] == pd.Timestamp("2026-03-01")]
    de_p1 = del_corte[del_corte["id_producto"] == 1]
    de_p2 = del_corte[del_corte["id_producto"] == 2]

    assert (de_p1["modelo_usado"] == "modelo_b").all()
    assert (de_p1["rango_usado"] == 1).all()
    assert (de_p2["modelo_usado"] == "modelo_a").all()
    assert (de_p2["rango_usado"] == 0).all()
    assert de_p1["pred"].notna().all()


def test_sin_cuadrantes_los_calcula_con_hasta_igual_al_corte():
    """El camino por defecto: si no se le pasa `cuadrantes`, los calcula con
    `clasificar_por_corte`. Se verifica que el resultado sea el mismo que pasándoselos."""
    reporte = _reporte()
    train = _train([1, 2, 3, 4, 5])
    cortes = sorted(reporte["corte"].unique())

    calculados = clasificar_por_corte(train, cortes, columnas_id=["id_producto"])
    esperado = _rankear(reporte, train, calculados)
    obtenido = elegir_mejor_por_cuadrante(
        reporte, train, modelos=MODELOS_FALSOS, estacionalidad=1,
        modelo_fallback=FALLBACK_FALSO,
    )

    pd.testing.assert_frame_equal(esperado, obtenido)


def test_ganadores_de_cuadrante_colapsa_el_ranking_difundido():
    """La tabla interpretable: `corte` × cuadrante → modelo ganador.

    Se verifica contra los mismos ganadores que ya asertan los tests de arriba, para que no
    sea una segunda definición de "quién ganó" que pueda separarse de la primera.
    """
    ranking = _rankear(_reporte(), _train([1, 2, 3, 4, 5]), _cuadrantes_fijos())
    tabla = ganadores_de_cuadrante(ranking, _cuadrantes_fijos())

    assert list(tabla.columns) == ["corte", "lumpy", SIN_ACTIVIDAD, "suave"]
    assert len(tabla) == len(CORTES)

    del_corte = tabla[tabla["corte"] == pd.Timestamp("2026-03-01")].iloc[0]
    assert del_corte["suave"] == "modelo_a"
    assert del_corte["lumpy"] == "modelo_b"
    assert del_corte[SIN_ACTIVIDAD] == "modelo_b"

    arranque = tabla[tabla["corte"] == pd.Timestamp("2026-01-01")].iloc[0]
    assert arranque["suave"] == FALLBACK_FALSO
    assert arranque["lumpy"] == FALLBACK_FALSO


def test_ganadores_de_cuadrante_corta_si_un_grupo_tiene_dos_ganadores():
    """La guarda de consistencia: si el ranking no se difundió por grupo, la tabla estaría
    reportando una decisión que nunca se tomó. Se simula con un ranking por serie, donde P1
    y P2 —las dos `suave`— eligen modelos distintos."""
    por_serie = elegir_mejor_por_corte(
        _reporte(), _train([1, 2, 3, 4, 5]), modelos=MODELOS_FALSOS, estacionalidad=1,
        modelo_fallback=FALLBACK_FALSO,
    )
    with pytest.raises(ValueError, match="más de un ganador"):
        ganadores_de_cuadrante(por_serie, _cuadrantes_fijos())


def test_clasificar_por_corte_usa_una_ventana_distinta_en_cada_corte():
    """La razón de ser del cacheo: cada corte tiene su propia clasificación, y una serie que
    deja de vender cambia de cuadrante entre un corte y el siguiente.

    Sin esto el cacheo sería una tabla repetida N veces y el test 3 pasaría por accidente.
    """
    fechas = pd.date_range("2025-01-01", periods=18, freq="MS")
    # Vende todos los meses hasta 2025-12 y después nada: en 2025-12 es suave, más tarde no.
    unidades = [10.0] * 12 + [0.0] * 6
    datos = pd.DataFrame({"id_producto": 1, "anio_mes": fechas, "unidades": unidades})

    tabla = clasificar_por_corte(datos, [pd.Timestamp("2025-12-01"), pd.Timestamp("2026-06-01")])

    assert len(tabla) == 2
    temprano = tabla[tabla["corte"] == pd.Timestamp("2025-12-01")]["cuadrante"].iloc[0]
    tardio = tabla[tabla["corte"] == pd.Timestamp("2026-06-01")]["cuadrante"].iloc[0]
    assert temprano == "suave"
    assert temprano != tardio
