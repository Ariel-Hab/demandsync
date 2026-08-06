"""Tests de las métricas de intervalo (M2.4): `motor.backtesting.intervalos`.

La lección de método del 2026-07-27 vale acá entera: **"corre sin errores" ≠ "mide bien"**.
Una cobertura empírica es un promedio de booleanos, o sea el tipo de número que sale
plausible aunque el criterio esté mal — y este módulo tiene tres criterios que cambian el
resultado sin fallar nunca:

1. **el intervalo cerrado** — con `real == 0 == P10` siendo el caso más frecuente del
   dataset, abrir el borde cambia la cobertura de casi todas las filas intermitentes;
2. **qué se hace con las filas sin intervalo** — contarlas como no cubiertas castiga al
   modelo por no predecir, ignorarlas en silencio lo premia; salen en `cobertura`;
3. **contra qué se normaliza la amplitud**, que es lo que la hace comparable con el WAPE.

Por eso los fixtures son de valores elegidos a mano, con la respuesta calculable a mano: si
la cobertura de 10 filas tiene que dar 0,8, el test lo pide exacto y no "razonable".
"""

import numpy as np
import pandas as pd
import pytest

from motor.backtesting.intervalos import (
    COBERTURA_NOMINAL,
    cobertura_empirica,
    construir_tablas_de_intervalos,
    pinball,
    tasa_de_cruce,
)

CUANTILES = {0.1: "P10", 0.5: "P50", 0.9: "P90"}


def _cobertura(reporte: pd.DataFrame, columnas_grupo: list[str]) -> pd.DataFrame:
    """`cobertura_empirica` con los nombres cortos del fixture (el default apunta a las
    columnas que emite `predecir_global`)."""
    return cobertura_empirica(
        reporte, columnas_grupo, columna_inferior="P10", columna_superior="P90"
    )


def _reporte(real, p10, p50=None, p90=None, **extra) -> pd.DataFrame:
    """Reporte mínimo con la forma del que devuelve el arnés."""
    n = len(real)
    datos = {
        "id_producto": range(n),
        "anio_mes": pd.date_range("2025-01-01", periods=n, freq="MS"),
        "corte": pd.Timestamp("2024-12-01"),
        "horizonte": 1,
        "real": np.asarray(real, dtype=float),
        "P10": np.asarray(p10, dtype=float),
        "P90": np.asarray(p90 if p90 is not None else p10, dtype=float),
    }
    if p50 is not None:
        datos["P50"] = np.asarray(p50, dtype=float)
    return pd.DataFrame({**datos, **extra})


# --------------------------------------------------------------------------------------
# 1. Cobertura empírica — el número del gate
# --------------------------------------------------------------------------------------


def test_cobertura_empirica_cuenta_exactamente_las_filas_de_adentro():
    """8 de 10 adentro tiene que dar 0,80 y no "cerca de 0,8"."""
    real = [5, 5, 5, 5, 5, 5, 5, 5, 50, -50]
    reporte = _reporte(real, p10=[0] * 10, p90=[10] * 10)

    tabla = _cobertura(reporte, [])

    assert tabla["cobertura_empirica"].iloc[0] == pytest.approx(0.8)
    assert tabla["desvio_vs_nominal"].iloc[0] == pytest.approx(0.8 - COBERTURA_NOMINAL)
    assert tabla["n"].iloc[0] == 10
    assert tabla["cobertura"].iloc[0] == 1.0


def test_el_intervalo_es_cerrado_en_los_dos_bordes():
    """**La decisión que más mueve el número en este dataset.**

    Con 42% de series intermitentes y el panel densificado a ceros explícitos (ADR-010), la
    fila más frecuente es `real == 0` con `P10 == 0`: el modelo dijo "bien puede no venderse
    nada" y no se vendió nada. Eso es un acierto. Con el borde abierto (`>` en vez de `>=`)
    esta fila cuenta como fallo y la cobertura sale sistemáticamente pesimista sobre la mayor
    parte del dataset — sin que nada falle.

    El borde superior va por el mismo criterio, por simetría: un real que da justo el P90
    está dentro del 80% central, no afuera.
    """
    justo_en_el_borde = _reporte(real=[0.0, 10.0], p10=[0.0, 0.0], p90=[10.0, 10.0])

    tabla = _cobertura(justo_en_el_borde, [])

    assert tabla["cobertura_empirica"].iloc[0] == 1.0


def test_las_filas_sin_intervalo_no_cuentan_como_cubiertas_ni_como_falladas():
    """Salen de la cuenta y aparecen en `cobertura`, igual que en `metricas.py`.

    Las dos alternativas están mal en direcciones opuestas: contarlas como falladas castiga
    al modelo por no haber predicho las altas de catálogo (12.700 filas del extract real, que
    **ningún** método puede predecir), y descartarlas sin dejar rastro deja que un modelo que
    no predice donde es difícil muestre una calibración mejor de la que tiene.
    """
    reporte = _reporte(
        real=[5, 5, 5, 500],
        p10=[0, 0, 0, np.nan],
        p90=[10, 10, 10, np.nan],
    )

    tabla = _cobertura(reporte, [])

    assert tabla["cobertura_empirica"].iloc[0] == 1.0, "la fila sin intervalo no debe fallar"
    assert tabla["cobertura"].iloc[0] == pytest.approx(0.75)
    assert tabla["n"].iloc[0] == 4


def test_un_intervalo_absurdamente_ancho_cubre_todo_y_la_amplitud_lo_delata():
    """La guarda contra el modo de falla del gate: la cobertura sola se gana con `[0, ∞)`.

    ADR-015 convierte este intervalo en lo que el producto promete a h=6/h=12, así que un
    P10–P90 que cubre el 100% siendo diez veces más ancho que la demanda no es un éxito. La
    amplitud relativa —mismo denominador que el WAPE— es lo que lo hace visible en la misma
    tabla.
    """
    honesto = _reporte(real=[10] * 4, p10=[8] * 4, p90=[12] * 4)
    inutil = _reporte(real=[10] * 4, p10=[0] * 4, p90=[1000] * 4)

    tabla_honesto = _cobertura(honesto, [])
    tabla_inutil = _cobertura(inutil, [])

    assert tabla_honesto["cobertura_empirica"].iloc[0] == 1.0
    assert tabla_inutil["cobertura_empirica"].iloc[0] == 1.0
    assert tabla_honesto["amplitud_relativa"].iloc[0] == pytest.approx(0.4)
    assert tabla_inutil["amplitud_relativa"].iloc[0] == pytest.approx(100.0)


def test_la_amplitud_relativa_usa_el_mismo_denominador_que_el_wape():
    """`Σ(P90−P10) / Σ|real|`. Que sea el mismo denominador es lo que deja comparar el ancho
    del intervalo contra el error del punto sin traducir de escala."""
    reporte = _reporte(real=[10, 30], p10=[5, 10], p90=[15, 50])

    tabla = _cobertura(reporte, [])

    # (10 + 40) / (10 + 30)
    assert tabla["amplitud_relativa"].iloc[0] == pytest.approx(50 / 40)


def test_la_cobertura_se_desagrega_por_grupo():
    """Regla del gate de M1.2: ningún número global suelto. Un 0,80 global puede ser 0,95 a
    h=1 y 0,55 a h=12, que es justo la diferencia que ADR-015 vino a acotar."""
    reporte = pd.concat(
        [
            _reporte(real=[5, 5, 5, 5], p10=[0] * 4, p90=[10] * 4).assign(horizonte=1),
            _reporte(real=[5, 5, 50, 50], p10=[0] * 4, p90=[10] * 4).assign(horizonte=12),
        ],
        ignore_index=True,
    )

    tabla = _cobertura(reporte, ["horizonte"]).set_index("horizonte")

    assert tabla.loc[1, "cobertura_empirica"] == 1.0
    assert tabla.loc[12, "cobertura_empirica"] == pytest.approx(0.5)


def test_sin_columnas_de_cuantil_corta_en_vez_de_devolver_una_tabla_vacia():
    reporte = _reporte(real=[1], p10=[0], p90=[2]).drop(columns=["P90"])

    with pytest.raises(ValueError, match="cuantil"):
        _cobertura(reporte, [])


# --------------------------------------------------------------------------------------
# 2. Pinball — la pérdida propia del cuantil
# --------------------------------------------------------------------------------------


def test_pinball_es_asimetrica_en_la_direccion_correcta():
    """Con `q = 0,9`, quedarse corto tiene que costar 9 veces más que pasarse por lo mismo.

    Es lo que empuja al P90 hacia arriba durante el entrenamiento; si el signo estuviera
    invertido el modelo aprendería un P10 y nadie lo notaría en la cobertura, porque un
    intervalo invertido igual "cubre" cuando es ancho.
    """
    quedarse_corto = _reporte(real=[110], p10=[100], p90=[100])
    pasarse = _reporte(real=[90], p10=[100], p90=[100])

    corto = pinball(quedarse_corto, [], {0.9: "P90"})["pinball"].iloc[0]
    largo = pinball(pasarse, [], {0.9: "P90"})["pinball"].iloc[0]

    # 0,9 · 10 / 110  contra  0,1 · 10 / 90
    assert corto == pytest.approx(0.9 * 10 / 110)
    assert largo == pytest.approx(0.1 * 10 / 90)
    assert corto > largo


def test_la_pinball_del_p50_es_la_mitad_del_wape():
    """Propiedad que hace comparable el P50 contra el pronóstico puntual sin cambiar de
    métrica: para `q = 0,5` la pérdida es `|error| / 2`, así que normalizada por `Σ|real|`
    da exactamente `WAPE / 2`."""
    from motor.backtesting.metricas import wape

    reporte = _reporte(real=[10, 20, 30], p10=[8, 25, 30], p50=[8, 25, 30], p90=[8, 25, 30])

    perdida = pinball(reporte, [], {0.5: "P50"})["pinball"].iloc[0]
    error = wape(reporte, [], columna_pred="P50")["wape"].iloc[0]

    assert perdida == pytest.approx(error / 2)


def test_pinball_devuelve_una_fila_por_cuantil():
    reporte = _reporte(real=[10, 20], p10=[5, 5], p50=[10, 15], p90=[30, 40])

    tabla = pinball(reporte, [], CUANTILES)

    assert list(tabla["cuantil"]) == [0.1, 0.5, 0.9]
    assert tabla["pinball"].notna().all()


# --------------------------------------------------------------------------------------
# 3. Cruce de cuantiles
# --------------------------------------------------------------------------------------


def test_detecta_cuantiles_cruzados():
    """Los tres modelos se ajustan por separado y nada les impone monotonía, así que el P10
    de una fila puede quedar por encima de su P90. No es un bug del motor: es la consecuencia
    de estimar cada cuantil independiente, y hay que saber cuán seguido pasa antes de decidir
    si se reordena."""
    reporte = _reporte(
        real=[10, 10, 10, 10],
        p10=[1, 1, 9, 1],
        p50=[5, 5, 5, 5],  # la tercera fila cruza: P10=9 > P50=5
        p90=[20, 20, 20, 20],
    )

    tabla = tasa_de_cruce(reporte, [], CUANTILES)

    assert tabla["tasa_de_cruce"].iloc[0] == pytest.approx(0.25)


def test_las_filas_sin_los_tres_cuantiles_salen_del_denominador():
    """Una fila sin predicción no está cruzada: está vacía, y tampoco es una fila que **pudo**
    cruzarse. Dejarla en el denominador diluye la tasa justo donde el modelo no predijo —es el
    error de denominador de §5.6.1, en otra métrica.

    **El fixture necesita una fila cruzada Y una vacía**, o el test no distingue nada: con
    cero cruces, `0/1` y `0/2` dan lo mismo y la guarda del denominador puede borrarse sin que
    nada falle. Así sobrevivía la mutación.
    """
    reporte = _reporte(
        real=[10, 10, 10],
        p10=[9, 1, np.nan],  # la primera cruza (P10=9 > P50=5), la tercera está vacía
        p50=[5, 5, np.nan],
        p90=[20, 20, np.nan],
    )

    tabla = tasa_de_cruce(reporte, [], CUANTILES)

    assert tabla["tasa_de_cruce"].iloc[0] == pytest.approx(0.5), "1 cruce sobre 2 completas"
    assert tabla["cobertura"].iloc[0] == pytest.approx(2 / 3)
    assert tabla["n"].iloc[0] == 3


# --------------------------------------------------------------------------------------
# 4. El juego de tablas del reporte
# --------------------------------------------------------------------------------------


def test_construir_tablas_arma_el_intervalo_con_el_menor_y_el_mayor_cuantil():
    """Pasar `{0.1, 0.5, 0.9}` mide el P10–P90; el P50 entra solo en la pinball. Si tomara
    dos cualesquiera, la cobertura nominal dejaría de ser 80% y el gate mediría otra cosa."""
    reporte = pd.concat(
        [
            _reporte(
                real=[5, 5, 5, 500], p10=[0] * 4, p50=[4] * 4, p90=[10] * 4
            ).assign(horizonte=h)
            for h in (1, 12)
        ],
        ignore_index=True,
    )

    tablas = construir_tablas_de_intervalos(reporte, CUANTILES, horizontes=(1, 12))

    assert set(tablas) == {"intervalos_por_horizonte", "pinball_por_horizonte"}
    por_horizonte = tablas["intervalos_por_horizonte"].set_index("horizonte")
    assert por_horizonte.loc[1, "cobertura_empirica"] == pytest.approx(0.75)
    assert "tasa_de_cruce" in por_horizonte.columns


def test_agrega_los_cortes_por_cuadrante_y_categoria_cuando_estan():
    """Los dos desagregados que exige el gate de M1.2 y la regla 3 de `backtests/README.md`.
    Sin la columna, la tabla simplemente no aparece — no se inventa un corte vacío."""
    reporte = _reporte(
        real=[5, 5, 5, 5],
        p10=[0] * 4,
        p50=[4] * 4,
        p90=[10] * 4,
        cuadrante=["suave", "suave", "lumpy", "lumpy"],
        categoria=["CLINICO"] * 4,
    )

    tablas = construir_tablas_de_intervalos(reporte, CUANTILES, horizontes=(1,))

    assert "intervalos_por_cuadrante" in tablas
    assert "intervalos_por_categoria" in tablas
    assert set(tablas["intervalos_por_cuadrante"]["cuadrante"]) == {"suave", "lumpy"}


def test_un_solo_cuantil_no_es_un_intervalo():
    reporte = _reporte(real=[5], p10=[0], p90=[10])

    with pytest.raises(ValueError, match="dos cuantiles"):
        construir_tablas_de_intervalos(reporte, {0.5: "P10"})
