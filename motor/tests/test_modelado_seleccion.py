"""Tests de la selección por serie (M1.7): `motor.modelado.seleccion`.

Tres focos: (1) el predictor combinado cumple el contrato `PredictorFn` y trae las 7
columnas de M1.5+M1.6 dentro del arnés real; (2) `elegir_mejor_por_serie` elige, por
producto, el candidato de menor MASE **promediado a través de los cortes** — no alcanza
con que gane en un corte suelto — y dos productos con ganadores distintos no se
confunden entre sí; (3) `armar_reporte_seleccionado` arma la predicción final tomando el
modelo ganador de cada fila sin mezclar productos, preserva `.attrs["corrida"]` a través
del merge (la trampa de `roadmap-motor.md` §12.2), y cae al fallback declarado cuando un
producto no tiene ganador (MASE indefinido en los 7, o ausente del cálculo).
"""

import pandas as pd
import pytest

from motor.backtesting.arnes import ejecutar_backtest
from motor.modelado.seleccion import (
    armar_reporte_seleccionado,
    elegir_mejor_por_serie,
    predecir_todos_los_candidatos,
    resumen_de_ganadores,
)

MODELOS_FALSOS = ["modelo_a", "modelo_b"]
FALLBACK_FALSO = "modelo_a"
"""Los tests usan nombres de modelo ficticios, así que tienen que declarar su propio
fallback: el default (`SeasonalNaive`) no está entre ellos y `elegir_mejor_por_serie`
corta —a propósito— si el fallback no es uno de los candidatos."""


@pytest.fixture
def historia_dos_productos():
    """Mismo fixture que M1.5/M1.6: un producto con historia larga, otro recién
    entrado — para probar que el predictor combinado hereda el `fallback_model` de
    `predecir_baselines` y no rompe la corrida."""
    meses_p1 = pd.date_range("2023-01-01", periods=30, freq="MS")
    p1 = pd.DataFrame(
        {"id_producto": 1, "anio_mes": meses_p1, "unidades": [float(i + 1) for i in range(30)]}
    )
    meses_p2 = pd.date_range("2025-05-01", periods=2, freq="MS")
    p2 = pd.DataFrame({"id_producto": 2, "anio_mes": meses_p2, "unidades": [3.0, 5.0]})
    return pd.concat([p1, p2], ignore_index=True)


def test_predecir_todos_los_candidatos_trae_las_siete_columnas(historia_dos_productos):
    reporte = ejecutar_backtest(
        historia_dos_productos, predecir_todos_los_candidatos, n_cortes=2, horizonte_max=3
    )

    columnas_esperadas = {
        "SeasonalNaive",
        "WindowAverage",
        "AutoETS",
        "AutoTheta",
        "AutoARIMA",
        "CrostonSBA",
        "TSB",
    }
    assert columnas_esperadas <= set(reporte.columns)
    assert set(reporte["id_producto"].unique()) <= {1, 2}


def _reporte_dos_productos_con_ganador_conocido() -> pd.DataFrame:
    """P1: `modelo_a` predice exacto en los dos cortes, `modelo_b` se equivoca mucho —
    gana `modelo_a`. P2: al revés — gana `modelo_b`. Dos cortes por producto para que
    el test exija promediar, no alcance con ganar en uno solo."""
    filas = [
        # id, corte, anio_mes, real, modelo_a, modelo_b
        (1, "2026-04-01", "2026-05-01", 13.0, 13.0, 20.0),
        (1, "2026-05-01", "2026-06-01", 14.0, 14.0, 5.0),
        (2, "2026-04-01", "2026-05-01", 13.0, 20.0, 13.0),
        (2, "2026-05-01", "2026-06-01", 14.0, 5.0, 14.0),
    ]
    columnas = ["id_producto", "corte", "anio_mes", "real", "modelo_a", "modelo_b"]
    df = pd.DataFrame(filas, columns=columnas)
    df["corte"] = pd.to_datetime(df["corte"])
    df["anio_mes"] = pd.to_datetime(df["anio_mes"])
    return df


def _train_df_dos_productos_misma_escala() -> pd.DataFrame:
    """Misma escala MASE (estacionalidad=1) para P1 y P2 — `mean(|12-10|,|9-12|,|11-9|)
    = 7/3` — para que la diferencia de ganador venga solo de las predicciones, no de la
    escala de cada serie."""
    meses = pd.date_range("2026-01-01", periods=4, freq="MS")
    p1 = pd.DataFrame({"id_producto": 1, "anio_mes": meses, "unidades": [10.0, 12.0, 9.0, 11.0]})
    p2 = pd.DataFrame({"id_producto": 2, "anio_mes": meses, "unidades": [10.0, 12.0, 9.0, 11.0]})
    return pd.concat([p1, p2], ignore_index=True)


def test_elegir_mejor_por_serie_promedia_a_traves_de_los_cortes():
    reporte = _reporte_dos_productos_con_ganador_conocido()
    train_df = _train_df_dos_productos_misma_escala()

    ganadores = elegir_mejor_por_serie(
        reporte,
        train_df,
        modelos=MODELOS_FALSOS,
        estacionalidad=1,
        modelo_fallback=FALLBACK_FALSO,
    )

    ganadores = ganadores.set_index("id_producto")["modelo_ganador"]
    assert ganadores.loc[1] == "modelo_a"
    assert ganadores.loc[2] == "modelo_b"


def test_elegir_mejor_por_serie_cae_al_fallback_con_escala_cero():
    """P3: historia de train constante → escala MASE (estacionalidad=1) es 0 → MASE
    indefinido (NaN) para los dos candidatos, sea cual sea la predicción. Sin fallback
    esa serie quedaría sin ganador."""
    reporte = _reporte_dos_productos_con_ganador_conocido()
    p3 = pd.DataFrame(
        [(3, "2026-04-01", "2026-05-01", 13.0, 999.0, 1.0)],
        columns=["id_producto", "corte", "anio_mes", "real", "modelo_a", "modelo_b"],
    )
    p3["corte"] = pd.to_datetime(p3["corte"])
    p3["anio_mes"] = pd.to_datetime(p3["anio_mes"])
    reporte = pd.concat([reporte, p3], ignore_index=True)

    train_df = _train_df_dos_productos_misma_escala()
    meses = pd.date_range("2026-01-01", periods=4, freq="MS")
    train_p3 = pd.DataFrame({"id_producto": 3, "anio_mes": meses, "unidades": 10.0})
    train_df = pd.concat([train_df, train_p3], ignore_index=True)

    ganadores = elegir_mejor_por_serie(
        reporte, train_df, modelos=MODELOS_FALSOS, estacionalidad=1, modelo_fallback="modelo_a"
    )

    assert ganadores.set_index("id_producto").loc[3, "modelo_ganador"] == "modelo_a"


def test_armar_reporte_seleccionado_no_mezcla_productos():
    reporte = _reporte_dos_productos_con_ganador_conocido()
    ganadores = pd.DataFrame({"id_producto": [1, 2], "modelo_ganador": ["modelo_a", "modelo_b"]})

    resultado = armar_reporte_seleccionado(
        reporte, ganadores, modelos=MODELOS_FALSOS, modelo_fallback=FALLBACK_FALSO
    )

    p1 = resultado[resultado["id_producto"] == 1]
    p2 = resultado[resultado["id_producto"] == 2]
    assert (p1["pred"] == p1["modelo_a"]).all()
    assert (p2["pred"] == p2["modelo_b"]).all()


def test_el_fallback_se_guarda_completo_sea_cual_sea_su_largo():
    """El fallback tiene que llegar **entero** al resultado, no recortado.

    Contexto, porque el nombre de este test promete menos de lo que parece: la
    implementación anterior armaba el ganador con `np.array(modelos)[indice]` y le
    asignaba el fallback encima. Los arrays de strings de numpy son de ancho fijo, así
    que un fallback más largo que el candidato más largo se truncaba en silencio
    (`np.array(["TSB"])` guarda "Sea" si le asignás "SeasonalNaive"). **Ese caso hoy es
    inalcanzable**: `_validar_fallback` exige que el fallback sea uno de `modelos`, y
    entonces el array siempre tiene ancho suficiente — lo cubre
    `test_fallback_ajeno_a_los_candidatos_corta_con_mensaje_claro`.

    Lo que este test sí fija es que la ruta del fallback devuelve el nombre completo con
    candidatos de largos distintos, que es la propiedad que le importa al llamador."""
    corto, largo = "TSB", "SeasonalNaive"
    reporte = pd.DataFrame(
        {
            "id_producto": [1],
            "corte": [pd.Timestamp("2026-04-01")],
            "anio_mes": [pd.Timestamp("2026-05-01")],
            "real": [13.0],
            corto: [999.0],
            largo: [1.0],
        }
    )
    # train constante -> escala MASE 0 -> ningún candidato medible -> todos al fallback
    train_df = pd.DataFrame(
        {
            "id_producto": 1,
            "anio_mes": pd.date_range("2026-01-01", periods=4, freq="MS"),
            "unidades": 10.0,
        }
    )

    ganadores = elegir_mejor_por_serie(
        reporte,
        train_df,
        modelos=[corto, largo],
        estacionalidad=1,
        modelo_fallback=largo,
    )

    assert ganadores["modelo_ganador"].iloc[0] == largo


def test_fallback_ajeno_a_los_candidatos_corta_con_mensaje_claro():
    ganadores = pd.DataFrame({"id_producto": [1], "modelo_ganador": ["modelo_a"]})
    reporte = _reporte_dos_productos_con_ganador_conocido()

    with pytest.raises(ValueError, match="no está entre los modelos"):
        armar_reporte_seleccionado(
            reporte, ganadores, modelos=MODELOS_FALSOS, modelo_fallback="inventado"
        )


def test_ganador_desconocido_corta_en_vez_de_indexar_mal():
    """Si `ganadores` nombra un modelo que no es columna del reporte, antes reventaba con
    un IndexError opaco de numpy; ahora dice qué pasó."""
    reporte = _reporte_dos_productos_con_ganador_conocido()
    ganadores = pd.DataFrame({"id_producto": [1, 2], "modelo_ganador": ["modelo_a", "otro"]})

    with pytest.raises(ValueError, match="nombra modelos"):
        armar_reporte_seleccionado(
            reporte, ganadores, modelos=MODELOS_FALSOS, modelo_fallback=FALLBACK_FALSO
        )


def test_resumen_de_ganadores_cuenta_series_por_cuadrante():
    ganadores = pd.DataFrame(
        {
            "id_producto": [1, 2, 3, 4],
            "modelo_ganador": ["AutoETS", "AutoETS", "CrostonSBA", "AutoETS"],
        }
    )
    clasificacion = pd.DataFrame(
        {
            "id_producto": [1, 2, 3, 4],
            "cuadrante": ["suave", "suave", "lumpy", "lumpy"],
        }
    )

    resumen = resumen_de_ganadores(ganadores, clasificacion).set_index("modelo_ganador")

    assert resumen.loc["AutoETS", "total"] == 3
    assert resumen.loc["AutoETS", "suave"] == 2
    assert resumen.loc["AutoETS", "lumpy"] == 1
    assert resumen.loc["CrostonSBA", "total"] == 1
    # el orden importa: la tabla del markdown se lee de arriba hacia abajo
    assert resumen.index[0] == "AutoETS"


def test_resumen_de_ganadores_marca_series_sin_clasificar():
    """Una serie que no está en `clasificacion` no puede desaparecer del resumen: el
    total tiene que seguir cuadrando con la cantidad de series que tienen ganador."""
    ganadores = pd.DataFrame({"id_producto": [1, 2], "modelo_ganador": ["TSB", "TSB"]})
    clasificacion = pd.DataFrame({"id_producto": [1], "cuadrante": ["lumpy"]})

    resumen = resumen_de_ganadores(ganadores, clasificacion)

    assert resumen["total"].sum() == len(ganadores)
    assert "sin_clasificar" in resumen.columns


def test_armar_reporte_seleccionado_preserva_la_corrida_y_usa_fallback():
    """P2 no aparece en `ganadores` (ej. quedó afuera del cálculo de MASE) — tiene que
    caer al fallback, no desaparecer ni tirar una excepción. Y `.attrs["corrida"]` tiene
    que sobrevivir al merge interno (pandas lo descarta — roadmap-motor.md §12.2)."""
    reporte = _reporte_dos_productos_con_ganador_conocido()
    reporte.attrs["corrida"] = "id-de-prueba"
    ganadores = pd.DataFrame({"id_producto": [1], "modelo_ganador": ["modelo_a"]})

    resultado = armar_reporte_seleccionado(
        reporte, ganadores, modelos=MODELOS_FALSOS, modelo_fallback="modelo_b"
    )

    assert resultado.attrs["corrida"] == "id-de-prueba"
    p2 = resultado[resultado["id_producto"] == 2]
    assert (p2["pred"] == p2["modelo_b"]).all()
