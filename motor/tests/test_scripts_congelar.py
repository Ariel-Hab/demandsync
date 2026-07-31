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


def test_no_explota_si_falta_la_tabla_o_la_columna():
    assert congelar._nota_de_cobertura(None) == []
    assert congelar._nota_de_cobertura({}) == []
    assert congelar._nota_de_cobertura({"por_horizonte": pd.DataFrame({"wape": [0.3]})}) == []


def test_una_cobertura_apenas_por_debajo_de_uno_igual_avisa():
    """0,9999 no es 1,0. El redondeo de la tabla la mostraría como 1.0000."""
    assert congelar._nota_de_cobertura(_por_horizonte([1.0, 1.0, 1.0, 0.99985])) != []
