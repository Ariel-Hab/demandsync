"""Tests del script que congela la tabla de baselines (M1.7/M1.8).

Lo que se testea acá es la parte que decide **qué advertencias lleva la tabla**, no la
orquestación. Una tabla congelada sin su advertencia es peor que no tenerla: se lee como
un piso limpio.
"""

import importlib.util
from pathlib import Path

import pandas as pd

RAIZ_REPO = Path(__file__).resolve().parents[2]
_RUTA = RAIZ_REPO / "motor" / "scripts" / "congelar_baselines_sintetico.py"
_spec = importlib.util.spec_from_file_location("congelar", _RUTA)
congelar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(congelar)


def _por_horizonte(coberturas):
    return {
        "por_horizonte": pd.DataFrame(
            {"horizonte": [1, 3, 6, 12], "wape": [0.3] * 4, "cobertura": coberturas}
        )
    }


def test_con_cobertura_completa_no_agrega_advertencia():
    assert congelar._nota_de_cobertura(_por_horizonte([1.0, 1.0, 1.0, 1.0])) == []


def test_avisa_cuando_la_cobertura_baja_de_uno():
    """Lo que pasó en M1.8: 0,88 a h=12 por altas de catálogo sin historia.

    Sin esta nota el número queda en una columna al medio de la tabla y la tabla se lee
    como un piso limpio, cuando su WAPE está mejorado por omitir series.
    """
    lineas = congelar._nota_de_cobertura(_por_horizonte([0.9918, 0.9636, 0.9249, 0.8794]))

    texto = "\n".join(lineas)
    assert "0.8794" in texto
    assert "h=12" in texto
    assert "omiten series" in texto


def test_la_nota_no_afirma_que_ningun_candidato_predijo():
    """La redacción vieja decía "sin predicción de ningún candidato" y eso hizo perder el
    gate una vez.

    En la corrida del 2026-07-31 el diagnóstico contó solo las filas donde **ninguno** de
    los 7 candidatos predijo (13.889) y concluyó "100% explicado por altas de catálogo",
    cuando la columna `cobertura` cuenta las que le faltan al **modelo seleccionado**
    (20.174). El 31% restante son series jóvenes donde el ganador retrospectivo no llegaba
    al horizonte y otros 5-6 candidatos sí predijeron. La nota no puede afirmar una causa
    que el script no puede saber. Ver `roadmap-motor.md` §5.6.1.
    """
    texto = "\n".join(congelar._nota_de_cobertura(_por_horizonte([0.99, 0.96, 0.92, 0.88])))

    # La frase exacta que afirmaba la causa falsa. No alcanza con buscar "ningún
    # candidato": la redacción nueva lo menciona justamente para desmentirlo.
    assert "sin predicción de ningún candidato" not in texto
    assert "modelo seleccionado" in texto
    # Y tiene que advertir activamente contra ese error de conteo, no solo evitarlo.
    assert "falso 100%" in texto


def test_no_explota_si_falta_la_tabla_o_la_columna():
    assert congelar._nota_de_cobertura(None) == []
    assert congelar._nota_de_cobertura({}) == []
    assert congelar._nota_de_cobertura({"por_horizonte": pd.DataFrame({"wape": [0.3]})}) == []


def test_una_cobertura_apenas_por_debajo_de_uno_igual_avisa():
    """0,9999 no es 1,0. El redondeo de la tabla la mostraría como 1.0000."""
    assert congelar._nota_de_cobertura(_por_horizonte([1.0, 1.0, 1.0, 0.99985])) != []


def test_la_tabla_prospectiva_no_lleva_la_advertencia_de_hindsight():
    """Una tabla prospectiva con el aviso de "este piso es optimista por hindsight"
    afirma algo **falso sobre sí misma**, que es el mismo modo de falla que hizo perder
    el diagnóstico de cobertura en la corrida del 2026-07-31: la plantilla instala una
    causa que el resultado no tiene. Los dos textos tienen que ser mutuamente excluyentes.
    """
    retrospectiva = "\n".join(congelar._nota_del_criterio(prospectiva=False))
    prospectiva = "\n".join(congelar._nota_del_criterio(prospectiva=True))

    assert "retrospectiva, así que este piso es optimista" in retrospectiva
    assert "optimista" not in prospectiva
    assert "ya observado" in prospectiva
    # y la retrospectiva tiene que decir que dejó de ser el piso, no solo advertir
    assert "no es el piso de M2.5" in retrospectiva


def test_la_nota_de_cobertura_prospectiva_si_puede_nombrar_la_causa():
    """Al revés que en la retrospectiva: con cascada, las filas que quedan sin cubrir son
    por construcción las que ningún candidato pudo predecir, así que afirmarlo no es
    inventar una causa. Lo que **no** puede hacer es repetir la advertencia de la otra,
    que dice justo lo contrario."""
    texto = "\n".join(
        congelar._nota_de_cobertura(_por_horizonte([0.99, 0.96, 0.92, 0.88]), prospectiva=True)
    )

    assert "ningún** candidato pudo predecir" in texto
    assert "falso 100%" not in texto
    assert "origen_de_la_prediccion" in texto
