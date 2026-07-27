"""Suite de defectos de M1.0 — los 9 defectos del relevamiento 2026-07-27, como tests.

**Por qué existe este archivo.** El relevamiento encontró 9 defectos de medición en
`motor.backtesting` (ver `src/motor/backtesting/README.md` §Defectos conocidos y
`roadmap-motor.md` §5.1). Se descubrieron con scripts descartables en la terminal,
así que la evidencia vivía en prosa: nadie podía verificar un fix y nada protegía
contra regresión — `pytest` daba 21/21 verde sobre un módulo roto. Este archivo
convierte cada defecto en una prueba ejecutable, **antes** de arreglar el código.

**Cómo se usaron.** Cada test afirma el comportamiento CORRECTO, así que al escribirlos
todos fallaban y fueron marcados `xfail(strict=True)`. Ese `strict` es lo que hizo el
trabajo: cuando un fix hacía pasar un test, pytest lo reportaba como FALLO
(`XPASS(strict)`) y obligaba a sacar el marcador en la misma unidad de trabajo. Dos
hallazgos que salieron solos de ese mecanismo:

- **ADR-010 arregló más de lo previsto:** los tests de los defectos 2, 7-orden y 8
  empezaron a pasar sin tocarlos — eran la misma causa raíz que el defecto 1.
- **Un test estaba mal especificado:** el del defecto 1 seguía fallando después del
  fix, porque al pasar los cortes al calendario el mes de demanda cero que usaba cayó
  fuera de la ventana de evaluación. Sin el marcador estricto habría quedado un
  defecto "arreglado" con un test que no lo probaba.

**Estado: los 9 defectos están cerrados** (2026-07-27) y estos tests quedan como
suite de regresión. No agregar marcadores nuevos acá: si aparece un defecto nuevo, va
con su propio test y su propio ciclo rojo→verde.

**Independencia del diseño.** Donde la corrección implicaba una decisión abierta (cómo
densificar el calendario), el test afirma la *propiedad* y no un número que dependa de
esa decisión. Los meses de demanda cero que se usan acá caen siempre **entre** la
primera y la última venta del producto, así que cualquier esquema razonable de
densificación los incluye.
"""

import numpy as np
import pandas as pd
import pytest

from motor.backtesting.arnes import ejecutar_backtest
from motor.backtesting.cortes import generar_cortes
from motor.backtesting.metricas import mase, sesgo, wape

# --------------------------------------------------------------------------------------
# Defecto 1 — los meses de demanda cero no se miden (30,6% de los pares producto-mes)
# --------------------------------------------------------------------------------------


def _datos_con_hueco() -> pd.DataFrame:
    """Un producto que vende Ene/Feb/Mar/May/Jun/Ago. **Abril y julio vendieron cero**
    (no tienen fila).

    Los dos huecos caen entre la primera y la última venta, así que no son casos de
    "producto que todavía no existía": es demanda cero legítima y tiene que medirse.

    Julio está elegido a propósito: con `n_cortes=2` sobre este calendario (Ene..Ago)
    los cortes son Jun y Jul, así que **julio cae en la ventana de evaluación del
    corte de junio, en horizonte 1**. Abril, en cambio, queda antes del primer corte
    y no se evalúa nunca — por eso el test mira julio y no abril.
    """
    return pd.DataFrame(
        {
            "id_producto": [1] * 6,
            "anio_mes": pd.to_datetime(
                [
                    "2025-01-01",
                    "2025-02-01",
                    "2025-03-01",
                    "2025-05-01",
                    "2025-06-01",
                    "2025-08-01",
                ]
            ),
            "unidades": [10.0, 20.0, 30.0, 50.0, 60.0, 80.0],
        }
    )


def _predictor_constante(valor: float, columna: str = "pred"):
    def predictor(historia, corte, horizonte_max):
        fechas = pd.date_range(corte + pd.DateOffset(months=1), periods=horizonte_max, freq="MS")
        ids = historia["id_producto"].unique()
        return pd.DataFrame(
            [{"id_producto": i, "anio_mes": f, columna: valor} for i in ids for f in fechas]
        )

    return predictor


def test_defecto_1_el_mes_de_demanda_cero_aparece_en_el_reporte():
    """Regresión de ADR-010 (defecto 1, arreglado 2026-07-27)."""
    reporte = ejecutar_backtest(
        _datos_con_hueco(), _predictor_constante(100.0), n_cortes=2, horizonte_max=3
    )

    julio = reporte[reporte["anio_mes"] == "2025-07-01"]
    assert not julio.empty, "julio (demanda cero) no se está midiendo"
    assert (julio["real"] == 0.0).all()


def test_defecto_1_sobre_pronostico_sobre_demanda_cero_se_paga():
    """Regresión de ADR-010: un predictor que dispara 100 unidades donde la demanda
    real fue cero tiene que pagarlo. Es el error dominante en un portafolio
    intermitente, y con la tabla dispersa era gratis.

    Con el calendario denso, el horizonte 1 incluye julio (real 0, pred 100) además de
    agosto (real 80, pred 100) → WAPE = 120/80 = 1,5. Sin densificar, julio no existe
    y solo queda el error de agosto → WAPE = 20/80 = 0,25. Seis veces menos.
    """
    datos, predictor = _datos_con_hueco(), _predictor_constante(100.0)
    denso = ejecutar_backtest(datos, predictor, n_cortes=2, horizonte_max=3)
    disperso = ejecutar_backtest(
        datos, predictor, n_cortes=2, horizonte_max=3, densificar_calendario=False
    )

    wape_denso = wape(denso, ["horizonte"]).set_index("horizonte")["wape"][1]
    wape_disperso = wape(disperso, ["horizonte"]).set_index("horizonte")["wape"][1]

    assert wape_denso == pytest.approx(1.5)
    assert wape_disperso == pytest.approx(0.25)
    assert wape_denso > wape_disperso


# --------------------------------------------------------------------------------------
# Defecto 2 — la escala de MASE es un shift de 12 FILAS, no de 12 meses de calendario
# --------------------------------------------------------------------------------------


def test_defecto_2_la_escala_de_mase_usa_el_calendario():
    """Serie que vende un mes de por medio: Ene=10, Mar=20, May=30 (Feb y Abr = cero).

    Escala correcta (naive de un paso sobre calendario denso Ene..May = [10,0,20,0,30]):
        media(|0-10|, |20-0|, |0-20|, |30-0|) = media(10,20,20,30) = 20
    Escala que calcula hoy (shift de 1 FILA sobre [10,20,30]):
        media(|20-10|, |30-20|) = 10
    Con |real-pred| = |30-10| = 20 → MASE correcto 1,0 · MASE actual 2,0 (2x).
    Sobre el dataset sintético este sesgo afecta al 68,8% de las series (hasta 9,6x).
    """
    train_df = pd.DataFrame(
        {
            "id_producto": ["P1"] * 3,
            "anio_mes": pd.to_datetime(["2026-01-01", "2026-03-01", "2026-05-01"]),
            "unidades": [10.0, 20.0, 30.0],
        }
    )
    df = pd.DataFrame(
        {
            "id_producto": ["P1"],
            "anio_mes": [pd.Timestamp("2026-06-01")],
            "corte": [pd.Timestamp("2026-05-01")],
            "real": [30.0],
            "pred": [10.0],
        }
    )

    resultado = mase(df, modelos=["pred"], train_df=train_df, estacionalidad=1)

    assert resultado["pred"].iloc[0] == pytest.approx(1.0)


# --------------------------------------------------------------------------------------
# Defecto 3 — "WAPE por nivel de agregación" (ADR-008) no agrega por nivel
# --------------------------------------------------------------------------------------


@pytest.fixture
def df_dos_productos_que_se_cancelan():
    """Dos productos de la misma categoría, errores de igual magnitud y signo opuesto.

    Grano producto: WAPE = (50+50)/200 = 0,50
    Nivel categoría (agregando antes): real 200, pred 200 → WAPE = 0,00
    Son cantidades distintas; el nivel agregado se beneficia de la cancelación. En el
    sintético la diferencia real es de 3 a 4 veces.
    """
    return pd.DataFrame(
        {
            "id_producto": [1, 2],
            "categoria": ["vacunas", "vacunas"],
            "anio_mes": [pd.Timestamp("2026-01-01")] * 2,
            "corte": [pd.Timestamp("2025-12-01")] * 2,
            "horizonte": [1, 1],
            "real": [100.0, 100.0],
            "pred": [150.0, 50.0],
        }
    )


def test_defecto_3_wape_del_nivel_categoria(df_dos_productos_que_se_cancelan):
    resultado = wape(
        df_dos_productos_que_se_cancelan, ["horizonte"], columnas_nivel=["categoria"]
    )
    assert resultado["wape"].iloc[0] == pytest.approx(0.0)


def test_defecto_3_sesgo_a_nivel_total_es_computable(df_dos_productos_que_se_cancelan):
    """`plan-diseno.md` §Definición de listo, punto 4: "sesgo global dentro de ±5% a
    nivel total". Hoy esa métrica de gate no se puede calcular."""
    resultado = sesgo(df_dos_productos_que_se_cancelan, ["horizonte"], columnas_nivel=[])
    assert resultado["sesgo"].iloc[0] == pytest.approx(0.0)


def test_defecto_3_wape_sin_cortes_devuelve_un_numero_global(df_dos_productos_que_se_cancelan):
    resultado = wape(df_dos_productos_que_se_cancelan, [])
    assert len(resultado) == 1


# --------------------------------------------------------------------------------------
# Defecto 4 — omitir predicciones mejora el score y no deja rastro
# --------------------------------------------------------------------------------------


def test_defecto_4_la_serie_no_predicha_sigue_visible_en_el_reporte():
    """Con dos productos y un predictor que solo cubre el 1, el producto 2 tiene que
    seguir apareciendo (con predicción nula), no desaparecer. Si desaparece, omitir
    las series difíciles mejora el WAPE: medido sobre el sintético, omitir el 60% más
    errático lleva el WAPE de 0,528 a 0,276 sin dejar rastro en la tabla."""
    datos = pd.DataFrame(
        {
            "id_producto": [1] * 5 + [2] * 5,
            "anio_mes": list(pd.date_range("2025-01-01", periods=5, freq="MS")) * 2,
            "unidades": [10.0, 20.0, 30.0, 40.0, 50.0, 1.0, 2.0, 3.0, 4.0, 5.0],
        }
    )

    def predictor_parcial(historia, corte, horizonte_max):
        fechas = pd.date_range(corte + pd.DateOffset(months=1), periods=horizonte_max, freq="MS")
        return pd.DataFrame([{"id_producto": 1, "anio_mes": f, "pred": 99.0} for f in fechas])

    reporte = ejecutar_backtest(datos, predictor_parcial, n_cortes=2, horizonte_max=2)

    assert 2 in set(reporte["id_producto"]), "la serie omitida desapareció del reporte"


def test_defecto_4_las_metricas_informan_cuantas_filas_agregaron():
    """Sin `n`, dos tablas de error con cobertura muy distinta son indistinguibles —
    inaceptable en la tabla que se congela como piso (M1.7/M1.8)."""
    df = pd.DataFrame({"horizonte": [1, 1, 2], "real": [10.0, 10.0, 10.0], "pred": [9.0] * 3})
    assert "n" in wape(df, ["horizonte"]).columns


# --------------------------------------------------------------------------------------
# Defecto 5 — sin validación de grano: fan-out silencioso
# --------------------------------------------------------------------------------------


def test_defecto_5_predictor_con_filas_duplicadas_es_rechazado():
    datos = pd.DataFrame(
        {
            "id_producto": [1] * 5,
            "anio_mes": pd.date_range("2025-01-01", periods=5, freq="MS"),
            "unidades": [10.0, 20.0, 30.0, 40.0, 50.0],
        }
    )

    def predictor_duplicado(historia, corte, horizonte_max):
        fechas = pd.date_range(corte + pd.DateOffset(months=1), periods=horizonte_max, freq="MS")
        base = pd.DataFrame({"id_producto": 1, "anio_mes": fechas, "pred": 99.0})
        return pd.concat([base, base], ignore_index=True)

    with pytest.raises(ValueError, match="duplicad"):
        ejecutar_backtest(datos, predictor_duplicado, n_cortes=2, horizonte_max=2)


def test_defecto_5_datos_de_grano_mas_fino_que_columnas_id_son_rechazados():
    """Pasar `hecho_venta_mensual_cliente_producto` con el `columnas_id` por defecto
    (`["id_producto"]`) multiplica filas en el merge: hasta 50 reales contra una sola
    predicción, sin ninguna excepción."""
    datos = pd.DataFrame(
        {
            "id_cliente": [1, 2] * 5,
            "id_producto": [1] * 10,
            "anio_mes": sorted(list(pd.date_range("2025-01-01", periods=5, freq="MS")) * 2),
            "unidades": [10.0] * 10,
        }
    )

    with pytest.raises(ValueError, match="grano|duplicad|únic"):
        ejecutar_backtest(datos, _predictor_constante(9.0), n_cortes=2, horizonte_max=2)


# --------------------------------------------------------------------------------------
# Defecto 6 — groupby(dropna=True) descarta en silencio las filas con NaN de grupo
# --------------------------------------------------------------------------------------


def test_defecto_6_grupo_nan_no_se_descarta_en_silencio():
    """91% de las unidades reales y el peor error del set desaparecen del reporte.
    Disparador vivo: el corte por cuadrante de M1.4 (`sin_actividad`) y los productos
    ausentes del catálogo tras el merge."""
    df = pd.DataFrame(
        {
            "categoria": ["vacunas", "vacunas", np.nan, np.nan],
            "real": [10.0, 10.0, 100.0, 100.0],
            "pred": [11.0, 11.0, 900.0, 900.0],
        }
    )

    with pytest.raises(ValueError, match="NaN|nulo"):
        wape(df, ["categoria"])


# --------------------------------------------------------------------------------------
# Defecto 7 — mase() depende del orden de train_df y devuelve inf con escala 0
# --------------------------------------------------------------------------------------


def test_defecto_7_mase_es_invariante_al_orden_de_train_df():
    """`utilsforecast` documenta "train_df must be sorted by time" y el wrapper no
    ordena ni valida. Hoy anda de casualidad porque el parquet sale ordenado: **M4.2
    (swap a PostgreSQL, sin `ORDER BY` garantizado) lo rompería en silencio**, en el
    mismo swap que el roadmap declara "sin cambios en modelos"."""
    train_ordenado = pd.DataFrame(
        {
            "id_producto": ["P1"] * 6,
            "anio_mes": pd.date_range("2026-01-01", periods=6, freq="MS"),
            "unidades": [10.0, 12.0, 9.0, 11.0, 13.0, 8.0],
        }
    )
    train_desordenado = train_ordenado.sample(frac=1.0, random_state=7)
    df = pd.DataFrame(
        {
            "id_producto": ["P1"],
            "anio_mes": [pd.Timestamp("2026-07-01")],
            "corte": [pd.Timestamp("2026-06-01")],
            "real": [10.0],
            "pred": [12.0],
        }
    )

    a = mase(df, modelos=["pred"], train_df=train_ordenado, estacionalidad=1)["pred"].iloc[0]
    b = mase(df, modelos=["pred"], train_df=train_desordenado, estacionalidad=1)["pred"].iloc[0]

    assert a == pytest.approx(b)


def test_defecto_7_mase_con_escala_cero_no_devuelve_infinito():
    """`wape`/`sesgo` sí protegen el denominador cero; `mase` no. Un solo `inf`
    arruina cualquier promedio de la tabla de referencia."""
    train_df = pd.DataFrame(
        {
            "id_producto": ["P1"] * 6,
            "anio_mes": pd.date_range("2026-01-01", periods=6, freq="MS"),
            "unidades": [7.0] * 6,
        }
    )
    df = pd.DataFrame(
        {
            "id_producto": ["P1"],
            "anio_mes": [pd.Timestamp("2026-07-01")],
            "corte": [pd.Timestamp("2026-06-01")],
            "real": [7.0],
            "pred": [9.0],
        }
    )

    resultado = mase(df, modelos=["pred"], train_df=train_df, estacionalidad=1)["pred"].iloc[0]

    assert not np.isinf(resultado), "escala 0 tiene que dar NaN, no inf"


# --------------------------------------------------------------------------------------
# Defecto 8 — generar_cortes usa los meses observados, no el calendario
# --------------------------------------------------------------------------------------


def test_defecto_8_los_cortes_son_meses_de_calendario_consecutivos():
    """Serie de 24 meses de calendario con venta en solo 8 (una cada 3 meses). Los
    "cortes mensuales" tienen que ser consecutivos en el calendario. Hoy, por serie
    individual —lo que exige M1.7— crashea en 19 de 2.300 productos del sintético, y
    en el peor caso los 18 "cortes mensuales" abarcan 90 meses de calendario."""
    fechas_con_venta = pd.date_range("2025-01-01", periods=8, freq="3MS")
    cortes = generar_cortes(pd.Series(fechas_con_venta), n_cortes=6)

    saltos = {
        (b.year - a.year) * 12 + (b.month - a.month)
        for a, b in zip(cortes, cortes[1:], strict=False)
    }
    assert saltos == {1}, f"los cortes no son consecutivos: saltos de {sorted(saltos)} meses"


# --------------------------------------------------------------------------------------
# Defecto 9 — el anti-leakage cubre solo `datos`, no las tablas auxiliares
# --------------------------------------------------------------------------------------


def test_defecto_9_las_tablas_auxiliares_se_recortan_al_corte():
    """`cliente_feature` es una foto única del último mes (`fecha_calculo` = 2026-06 en
    todas las filas). M2.2 la usa como feature: un predictor en el corte 2024-12
    estaría viendo el futuro y el arnés —que es el guardián— no puede impedirlo."""
    datos = pd.DataFrame(
        {
            "id_producto": [1] * 5,
            "anio_mes": pd.date_range("2025-01-01", periods=5, freq="MS"),
            "unidades": [10.0, 20.0, 30.0, 40.0, 50.0],
        }
    )
    auxiliar = pd.DataFrame(
        {
            "id_producto": [1, 1],
            "fecha_calculo": pd.to_datetime(["2025-01-01", "2025-05-01"]),
            "volumen_anual": [100.0, 999.0],
        }
    )
    vistos = []  # (corte, fecha_calculo más nueva que vio el predictor en ese corte)

    def predictor_con_auxiliar(historia, corte, horizonte_max, auxiliares):
        vistos.append((corte, auxiliares["cliente_feature"]["fecha_calculo"].max()))
        return _predictor_constante(9.0)(historia, corte, horizonte_max)

    ejecutar_backtest(
        datos,
        predictor_con_auxiliar,
        n_cortes=2,
        horizonte_max=2,
        tablas_auxiliares={"cliente_feature": auxiliar},
        columna_fecha_auxiliares="fecha_calculo",
    )

    assert vistos, "el predictor nunca recibió las tablas auxiliares"
    for corte, fecha_mas_nueva in vistos:
        assert fecha_mas_nueva <= corte, (
            f"en el corte {corte.date()} el predictor vio auxiliares de {fecha_mas_nueva.date()}"
        )
