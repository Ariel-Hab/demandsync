"""Tests de `motor.backtesting.comparacion` (M2.5).

Los fixtures son chicos y con el resultado calculado a mano: un test que solo comprueba
que la función "corre" no distingue un WAPE por serie de un WAPE global mal agrupado
(lección de método del 2026-07-27).
"""

import numpy as np
import pandas as pd
import pytest

from motor.backtesting.comparacion import (
    cabeza_a_cabeza,
    cabeza_a_cabeza_desagregado,
    distribucion_de_mejora,
    wape_por_serie,
)


def _reporte() -> pd.DataFrame:
    """Dos productos × dos horizontes, con error elegido para que el WAPE dé redondo.

    P1: real 10 y 20. `bueno` clava; `malo` se va 5 en cada uno.
    P2: real 100 y 200. `bueno` se va 10 en cada uno; `malo` clava.

    WAPE por serie y horizonte (h=1): P1/bueno = 0/10 = 0 · P1/malo = 5/10 = 0,5
                                      P2/bueno = 10/100 = 0,1 · P2/malo = 0
    """
    return pd.DataFrame(
        {
            "id_producto": ["P1", "P1", "P2", "P2"],
            "anio_mes": pd.to_datetime(["2024-02-01", "2024-03-01"] * 2),
            "corte": pd.to_datetime(["2024-01-01"] * 4),
            "horizonte": [1, 2, 1, 2],
            "real": [10.0, 20.0, 100.0, 200.0],
            "bueno": [10.0, 20.0, 110.0, 210.0],
            "malo": [15.0, 25.0, 100.0, 200.0],
            "categoria": ["A", "A", "B", "B"],
        }
    )


# --- wape_por_serie -----------------------------------------------------------------


def test_wape_por_serie_da_el_numero_calculado_a_mano():
    tabla = wape_por_serie(_reporte(), ["bueno", "malo"])

    def w(producto: str, h: int, modelo: str) -> float:
        fila = tabla[
            (tabla["id_producto"] == producto)
            & (tabla["horizonte"] == h)
            & (tabla["modelo"] == modelo)
        ]
        return float(fila["wape"].iloc[0])

    assert w("P1", 1, "bueno") == pytest.approx(0.0)
    assert w("P1", 1, "malo") == pytest.approx(0.5)
    assert w("P2", 1, "bueno") == pytest.approx(0.1)
    assert w("P2", 1, "malo") == pytest.approx(0.0)


def test_wape_por_serie_no_promedia_las_series_entre_si():
    """La trampa: agrupar mal daría el WAPE global (que pondera por magnitud y lo domina
    P2) repetido en las dos filas, y el test de arriba solo, con series simétricas, no lo
    distinguiría."""
    tabla = wape_por_serie(_reporte(), ["bueno"])
    de_h1 = tabla[tabla["horizonte"] == 1].set_index("id_producto")["wape"]

    assert de_h1["P1"] != de_h1["P2"]
    global_ponderado = (0 + 10) / (10 + 100)
    assert de_h1["P1"] != pytest.approx(global_ponderado)


def test_no_predecir_nada_da_wape_cero_y_solo_la_cobertura_lo_delata():
    """El caso que define cómo se comparan dos modelos, y es contraintuitivo.

    En `metricas.wape` una predicción nula aporta 0 al numerador, así que una serie que el
    modelo **no predijo** sale con WAPE 0,0 — perfecto. Es la convención documentada del
    módulo, no un defecto; pero significa que cualquier comparación que use "WAPE
    definido" como criterio de comparabilidad corona ganador al que no predijo. Por eso
    `distribucion_de_mejora` filtra por `cobertura`.
    """
    reporte = _reporte()
    reporte.loc[reporte["id_producto"] == "P2", "bueno"] = np.nan

    tabla = wape_por_serie(reporte, ["bueno"])
    p2 = tabla[(tabla["id_producto"] == "P2") & (tabla["horizonte"] == 1)].iloc[0]

    assert p2["cobertura"] == 0.0
    assert p2["wape"] == 0.0


def test_un_modelo_inexistente_corta():
    with pytest.raises(ValueError, match="no tiene columnas para los modelos"):
        wape_por_serie(_reporte(), ["bueno", "fantasma"])


def test_sin_modelos_corta():
    with pytest.raises(ValueError, match="al menos un modelo"):
        wape_por_serie(_reporte(), [])


# --- distribucion_de_mejora ---------------------------------------------------------


def test_la_mejora_tiene_el_signo_a_favor_del_retador():
    """`mejora = campeon - retador`: positivo significa que el retador erró menos."""
    por_serie = wape_por_serie(_reporte(), ["bueno", "malo"])

    tabla = distribucion_de_mejora(por_serie, campeon="malo", retador="bueno", horizontes=(1,))
    fila = tabla.iloc[0]

    # P1: malo 0,5 - bueno 0 = +0,5 (gana el retador). P2: 0 - 0,1 = -0,1 (pierde).
    assert fila["series"] == 2
    assert fila["gana_retador"] == 1
    assert fila["%_gana_retador"] == pytest.approx(50.0)
    assert fila["mejora_mediana"] == pytest.approx(0.2)


def test_la_serie_que_el_campeon_no_predijo_no_cuenta_como_derrota_suya():
    """Sin el filtro por cobertura, P2 entraría con `wape(malo) = 0` —el WAPE que da no
    predecir— y el retador aparecería perdiendo 0,1 contra un rival que no jugó."""
    reporte = _reporte()
    reporte.loc[reporte["id_producto"] == "P2", "malo"] = np.nan
    por_serie = wape_por_serie(reporte, ["bueno", "malo"])

    tabla = distribucion_de_mejora(por_serie, campeon="malo", retador="bueno", horizontes=(1,))
    fila = tabla.iloc[0]

    assert fila["series"] == 1
    assert fila["no_comparable"] == 1
    assert fila["mejora_mediana"] == pytest.approx(0.5)


def test_cobertura_parcial_distinta_tampoco_es_comparable():
    """Dos WAPE que promedian sobre distinto conjunto de cortes no se restan: la
    diferencia mezclaría precisión con cobertura."""
    reporte = pd.concat([_reporte(), _reporte()], ignore_index=True)
    reporte.loc[1::4, "corte"] = pd.Timestamp("2023-12-01")  # dos cortes por serie
    reporte.loc[reporte.index[0], "malo"] = np.nan  # el campeón cubre 1 de 2 en P1/h=1

    por_serie = wape_por_serie(reporte, ["bueno", "malo"])
    tabla = distribucion_de_mejora(por_serie, campeon="malo", retador="bueno", horizontes=(1,))

    assert int(tabla["no_comparable"].sum()) == 1


def test_abre_por_cuadrante_cuando_se_le_pasa_la_clasificacion():
    """El agregado puede calibrar mientras un cuadrante falla — el hallazgo de M2.4."""
    por_serie = wape_por_serie(_reporte(), ["bueno", "malo"])
    clasificacion = pd.DataFrame(
        {"id_producto": ["P1", "P2"], "cuadrante": ["suave", "erratica"]}
    )

    tabla = distribucion_de_mejora(
        por_serie, campeon="malo", retador="bueno", horizontes=(1,), clasificacion=clasificacion
    )

    assert set(tabla["cuadrante"]) == {"suave", "erratica"}
    suave = tabla[tabla["cuadrante"] == "suave"].iloc[0]
    erratica = tabla[tabla["cuadrante"] == "erratica"].iloc[0]
    assert suave["mejora_mediana"] == pytest.approx(0.5)
    assert erratica["mejora_mediana"] == pytest.approx(-0.1)


def test_una_serie_sin_cuadrante_no_desaparece():
    """Un merge que pierde filas haría que el reparto no sume el total, y la resta no
    salta a la vista en una tabla por cuadrante."""
    por_serie = wape_por_serie(_reporte(), ["bueno", "malo"])
    clasificacion = pd.DataFrame({"id_producto": ["P1"], "cuadrante": ["suave"]})

    tabla = distribucion_de_mejora(
        por_serie, campeon="malo", retador="bueno", horizontes=(1,), clasificacion=clasificacion
    )

    assert "sin_clasificar" in set(tabla["cuadrante"])
    assert tabla["series"].sum() == 2


def test_un_modelo_ausente_del_insumo_corta():
    por_serie = wape_por_serie(_reporte(), ["bueno"])

    with pytest.raises(ValueError, match="no tiene filas del modelo 'malo'"):
        distribucion_de_mejora(por_serie, campeon="malo", retador="bueno")


# --- cabeza_a_cabeza ----------------------------------------------------------------


def test_cabeza_a_cabeza_agrega_a_los_tres_niveles():
    tabla = cabeza_a_cabeza(_reporte(), {"piso": "malo", "global": "bueno"}, horizontes=(1, 2))

    assert set(tabla["nivel"]) == {"producto", "categoria", "total"}
    assert set(tabla["contendiente"]) == {"piso", "global"}

    # A nivel total y h=1: real 110, `bueno` 120 -> 10/110; `malo` 115 -> 5/110.
    total_h1 = tabla[(tabla["nivel"] == "total") & (tabla["horizonte"] == 1)].set_index(
        "contendiente"
    )["wape"]
    assert total_h1["global"] == pytest.approx(10 / 110)
    assert total_h1["piso"] == pytest.approx(5 / 110)


def test_el_nivel_producto_no_es_el_total():
    """Agregar antes o después de tomar el valor absoluto da números distintos: a nivel
    total los errores de signo opuesto se cancelan. Si esta tabla los confundiera, el
    veredicto del gate de M2 se leería del número equivocado.

    Necesita un fixture propio **con errores de signo opuesto**: en `_reporte()` el error
    de P1 es cero, así que no hay nada que cancelar y los dos niveles dan igual — un
    fixture que confirma en vez de probar (la lección de M2.2).
    """
    reporte = pd.DataFrame(
        {
            "id_producto": ["P1", "P2"],
            "anio_mes": pd.to_datetime(["2024-02-01"] * 2),
            "corte": pd.to_datetime(["2024-01-01"] * 2),
            "horizonte": [1, 1],
            "real": [100.0, 100.0],
            "pred": [90.0, 110.0],  # -10 y +10: a nivel total se cancelan exacto
        }
    )

    tabla = cabeza_a_cabeza(reporte, {"global": "pred"}, horizontes=(1,))
    por_nivel = tabla.set_index("nivel")["wape"]

    assert por_nivel["producto"] == pytest.approx(20 / 200)
    assert por_nivel["total"] == pytest.approx(0.0)


def test_el_sesgo_va_en_la_misma_tabla_y_conserva_el_signo():
    """El gate de M2 exige ganar en WAPE **y** quedar dentro del ±5% de sesgo: leerlos de
    dos tablas distintas invita a declarar cumplido lo primero y olvidar lo segundo.

    Hace falta **un contendiente que sub-pronostique**: con los dos sesgos positivos,
    publicar el sesgo en valor absoluto pasaría el test sin que nada lo note. Y el signo es
    la mitad del dato — sub-pronosticar y sobre-pronosticar son errores distintos para
    quien compra, que es de lo que discuten ADR-015 y ADR-016.
    """
    reporte = _reporte()
    reporte["corto"] = reporte["real"] * 0.8  # sub-pronóstico sistemático del 20%

    tabla = cabeza_a_cabeza(reporte, {"largo": "bueno", "corto": "corto"}, horizontes=(1,))
    total = tabla[tabla["nivel"] == "total"].set_index("contendiente")["sesgo"]

    # h=1: real 110. `bueno` predice 120 (+10/110); `corto` predice 88 (-22/110).
    assert total["largo"] == pytest.approx(10 / 110)
    assert total["corto"] == pytest.approx(-0.2)


def test_la_cobertura_viaja_con_cada_contendiente():
    """Sin esto, dos WAPE con coberturas distintas se leerían como comparables."""
    reporte = _reporte()
    reporte.loc[reporte["id_producto"] == "P2", "bueno"] = np.nan

    tabla = cabeza_a_cabeza(reporte, {"piso": "malo", "global": "bueno"}, horizontes=(1,))
    coberturas = tabla[tabla["nivel"] == "producto"].set_index("contendiente")["cobertura"]

    assert coberturas["piso"] == 1.0
    assert coberturas["global"] == 0.5


def test_sin_categoria_en_el_reporte_la_tabla_sale_con_dos_niveles():
    """La ausencia no puede romper: el sintético de smoke a veces no trae catálogo."""
    tabla = cabeza_a_cabeza(
        _reporte().drop(columns=["categoria"]), {"global": "bueno"}, horizontes=(1,)
    )

    assert set(tabla["nivel"]) == {"producto", "total"}


def test_un_contendiente_inexistente_corta():
    with pytest.raises(ValueError, match="no tiene columnas para los contendientes"):
        cabeza_a_cabeza(_reporte(), {"global": "fantasma"})


def test_sin_contendientes_corta():
    with pytest.raises(ValueError, match="al menos un contendiente"):
        cabeza_a_cabeza(_reporte(), {})


# --- cabeza_a_cabeza_desagregado ----------------------------------------------------


def _reporte_con_cuadrante() -> pd.DataFrame:
    """Un cuadrante chico donde el modelo yerra mucho, y uno grande donde yerra poco.

    `grande`: real 1000, pred 900 -> wape 0,1 · `chico`: real 10, pred 40 -> wape 3,0.
    El peso de `chico` es 10/1010 = 0,99%: un error de 3,0 ahí casi no mueve el agregado.
    """
    return pd.DataFrame(
        {
            "id_producto": ["P1", "P2"],
            "anio_mes": pd.to_datetime(["2024-02-01"] * 2),
            "corte": pd.to_datetime(["2024-01-01"] * 2),
            "horizonte": [1, 1],
            "real": [1000.0, 10.0],
            "pred": [900.0, 40.0],
            "cuadrante": ["suave", "lumpy"],
        }
    )


def test_el_desagregado_por_cuadrante_da_el_wape_de_cada_uno():
    tabla = cabeza_a_cabeza_desagregado(
        _reporte_con_cuadrante(), {"global": "pred"}, horizontes=(1,)
    )
    por_cuadrante = tabla.set_index("cuadrante")

    assert por_cuadrante.loc["suave", "wape"] == pytest.approx(0.1)
    assert por_cuadrante.loc["lumpy", "wape"] == pytest.approx(3.0)


def test_el_peso_dice_cuanto_pesa_cada_cuadrante_en_el_agregado():
    """Es la columna que evita leer la tabla al revés: sin ella, un WAPE de 3,0 en `lumpy`
    parece contradecir un agregado bueno, y en realidad no lo contradice — lo carga al 1%."""
    tabla = cabeza_a_cabeza_desagregado(
        _reporte_con_cuadrante(), {"global": "pred"}, horizontes=(1,)
    )
    peso = tabla.set_index("cuadrante")["peso_%"]

    assert peso["suave"] == pytest.approx(1000 / 1010 * 100)
    assert peso["lumpy"] == pytest.approx(10 / 1010 * 100)
    assert peso.sum() == pytest.approx(100.0)


def test_el_peso_se_normaliza_dentro_de_cada_horizonte():
    """Normalizar sobre toda la tabla haría que los pesos de un horizonte sumaran menos de
    100 y que dos horizontes con distinta cantidad de filas no se pudieran comparar."""
    base = _reporte_con_cuadrante()
    otro = base.copy()
    otro["horizonte"] = 6
    otro["real"] = [50.0, 50.0]

    tabla = cabeza_a_cabeza_desagregado(
        pd.concat([base, otro], ignore_index=True), {"global": "pred"}, horizontes=(1, 6)
    )

    for h in (1, 6):
        assert tabla[tabla["horizonte"] == h]["peso_%"].sum() == pytest.approx(100.0)
    del_6 = tabla[tabla["horizonte"] == 6].set_index("cuadrante")["peso_%"]
    assert del_6["suave"] == pytest.approx(50.0)


def test_el_desagregado_corta_si_falta_la_columna():
    with pytest.raises(ValueError, match="no tiene la columna 'cuadrante'"):
        cabeza_a_cabeza_desagregado(_reporte(), {"global": "bueno"})
