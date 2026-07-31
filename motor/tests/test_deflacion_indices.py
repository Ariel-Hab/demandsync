"""Tests del índice de nivel (M2.1) — la maquinaria de números índice de ADR-002.

El test que justifica todo el diseño es `test_el_indice_no_se_mueve_cuando_cambia_el_mix`:
si esa propiedad no se cumple, promediar precios sería más simple y daría lo mismo.
"""

import numpy as np
import pandas as pd
import pytest

from motor.datos.diccionario import ESQUEMAS
from motor.deflacion.indices import (
    COLUMNAS_INDICE,
    LIMITE_RELATIVO,
    clampear,
    factor_entre,
    indice_de_nivel,
)
from motor.deflacion.precios import relativos_apareados

MES = {n: pd.Timestamp(f"2024-{n:02d}-01") for n in range(1, 13)}


def _relativos(filas) -> pd.DataFrame:
    """`filas` = (id_nivel, mes:int, relativo, peso)."""
    d = pd.DataFrame(filas, columns=["id_nivel", "anio_mes", "relativo", "peso"])
    return d.assign(anio_mes=d["anio_mes"].map(MES))


def _serie(indice: pd.DataFrame, id_nivel="X") -> pd.Series:
    return indice[indice["id_nivel"] == id_nivel].set_index("anio_mes")["indice"]


def _variacion_medida(pares, **kw) -> float:
    """Variación que el índice le atribuye al mes 3, dados sus `(relativo, peso)`.

    Antepone un mes 2 neutro **porque el índice se normaliza a 1,0 en el primer mes de la
    cadena**: medir sobre el primer mes devolvería 1,0 siempre, y cualquier aserción
    contra 1,0 pasaría sin probar nada. Por el mismo motivo los casos de abajo esperan
    valores distintos de 1.
    """
    neutro = [("X", 2, 1.0, 1.0)] * max(len(pares), 3)
    r = _relativos(neutro + [("X", 3, rel, peso) for rel, peso in pares])
    s = _serie(indice_de_nivel(r, "categoria", **kw))
    return s[MES[3]] / s[MES[2]]


class TestMediaGeometrica:
    def test_es_geometrica_y_no_aritmetica(self):
        """sqrt(2,25 · 1) = 1,5, contra 1,625 de la media aritmética: 12,5% de inflación
        inventada de la nada. Los relativos se eligen dentro de `[1/3, 3]` para que lo que
        se mida sea la media y no el clamp, que está activo por defecto."""
        medida = _variacion_medida([(2.25, 1.0), (1.0, 1.0)], muestra_minima=2)

        assert medida == pytest.approx(1.5)
        assert medida != pytest.approx(1.625), "1,625 es la respuesta aritmética"

    def test_pondera_por_peso(self):
        """Tres partes de 2,0 y una de 0,5: exp((3·ln2 + ln0,5)/4) = sqrt(2)."""
        assert _variacion_medida([(2.0, 3.0), (0.5, 1.0)], muestra_minima=2) == pytest.approx(
            np.sqrt(2)
        )

    @pytest.mark.parametrize("pesos", [(0.0, 0.0), (-5.0, 2.0), (np.nan, 1.0)])
    def test_pesos_invalidos_caen_a_uniforme_en_vez_de_propagar_nan(self, pesos):
        """Un mes de neto negativo por devoluciones (§5.5 #5) puede dar peso ≤ 0.
        Uniforme es peor que ponderar, pero un NaN acá se propaga a todo el encadenado."""
        medida = _variacion_medida([(2.25, pesos[0]), (1.0, pesos[1])], muestra_minima=2)

        assert medida == pytest.approx(1.5)


class TestEncadenado:
    def test_la_base_es_el_primer_mes_y_vale_uno(self):
        r = _relativos([("X", 2, 1.1, 1.0), ("X", 2, 1.1, 1.0)])

        assert _serie(indice_de_nivel(r, "categoria", muestra_minima=2)).iloc[0] == 1.0

    def test_el_cociente_entre_dos_meses_es_el_producto_de_las_variaciones(self):
        r = _relativos(
            [("X", m, v, 1.0) for m, v in [(2, 1.1), (3, 1.2), (4, 1.5)] for _ in range(2)]
        )

        s = _serie(indice_de_nivel(r, "categoria", muestra_minima=2))

        assert s[MES[4]] / s[MES[2]] == pytest.approx(1.2 * 1.5)

    def test_agregar_meses_futuros_no_cambia_el_indice_de_los_meses_previos(self):
        """Anti-leakage por construcción: si la base fuera el último mes, todo el pasado
        se recalcularía con cada corte y el backtest daría sospechosamente bien (M1.3)."""
        base = [("X", m, v, 1.0) for m, v in [(2, 1.1), (3, 1.2)] for _ in range(2)]
        futuro = base + [("X", 4, 9.9, 1.0), ("X", 4, 9.9, 1.0)]

        corto = _serie(indice_de_nivel(_relativos(base), "categoria", muestra_minima=2))
        largo = _serie(indice_de_nivel(_relativos(futuro), "categoria", muestra_minima=2))

        pd.testing.assert_series_equal(corto, largo[corto.index])

    def test_los_niveles_no_se_contaminan_entre_si(self):
        r = _relativos([("X", 2, 2.0, 1.0), ("X", 2, 2.0, 1.0), ("Y", 2, 0.5, 1.0)])

        indice = indice_de_nivel(r, "categoria", muestra_minima=1)

        assert _serie(indice, "X").iloc[0] == 1.0
        assert _serie(indice, "Y").iloc[0] == 1.0
        assert set(indice["id_nivel"]) == {"X", "Y"}


class TestMuestraMinima:
    def test_un_mes_con_poca_muestra_no_produce_indice(self):
        """Un 'índice' de un solo producto es el ruido de ese producto."""
        r = _relativos([("X", 2, 5.0, 1.0)])

        assert indice_de_nivel(r, "categoria", muestra_minima=3).empty

    def test_la_cadena_saltea_el_mes_flaco_en_vez_de_cortarse(self):
        """El mes 3 tiene un solo par y encima un relativo disparatado. No se mide, pero
        los meses 2 y 4 siguen siendo comparables entre sí."""
        r = _relativos(
            [("X", 2, 1.1, 1.0)] * 3 + [("X", 3, 5.0, 1.0)] + [("X", 4, 1.2, 1.0)] * 3
        )

        s = _serie(indice_de_nivel(r, "categoria", muestra_minima=3))

        assert list(s.index) == [MES[2], MES[4]]
        assert s[MES[4]] / s[MES[2]] == pytest.approx(1.2)


class TestClamp:
    def test_recorta_de_los_dos_lados(self):
        r = clampear(pd.Series([1e-4, 0.5, 1.0, 2.0, 1e4]), limite=3.0)

        assert list(r) == [1 / 3, 0.5, 1.0, 2.0, 3.0]

    def test_un_limite_que_no_acota_es_un_error(self):
        with pytest.raises(ValueError, match="tiene que ser > 1"):
            clampear(pd.Series([1.0]), limite=1.0)

    def test_cp_inf_05_un_precio_basura_no_dispara_el_indice_de_la_categoria(self):
        """CP-INF-05. Veinte productos que suben 10% y uno que se desploma a 0,01.

        Se calcula **con y sin** clamp en el mismo test: así la aserción no puede quedar
        verde por casualidad, y queda demostrado qué compra exactamente el clamp.
        """
        pares = [(1.1, 1.0)] * 20 + [(1e-4, 1.0)]

        con = _variacion_medida(pares, muestra_minima=3, limite=LIMITE_RELATIVO)
        sin = _variacion_medida(pares, muestra_minima=3, limite=1e9)

        assert con == pytest.approx(1.039, abs=0.01), "cerca del 1,1 verdadero"
        assert sin < 0.8, "sin clamp, un solo producto hunde la categoria un 30%"

    def test_el_clamp_recorta_el_par_pero_no_lo_saca_de_la_muestra(self):
        """Descartar al producto lo sacaría de la muestra de ese mes, y el nivel pasaría a
        medir un conjunto distinto cada mes — el mismo problema de mix que el índice
        viene a resolver. Con 3 pares y muestra mínima 3, descartar uno daría vacío."""
        r = _relativos([("X", 2, 1.1, 1.0), ("X", 2, 1.1, 1.0), ("X", 2, 1e-4, 1.0)])

        assert not indice_de_nivel(r, "categoria", muestra_minima=3).empty


class TestMixDeProductos:
    def test_el_indice_no_se_mueve_cuando_cambia_el_mix(self):
        """**El test que justifica el diseño entero.**

        Una categoría con una jeringa de $20 y una vacuna de $20.000. Ningún precio
        cambia nunca. En el mes 2 entra otra jeringa de $20.

        El índice tiene que quedarse clavado en 1,0. El promedio de precios de la
        categoría, en cambio, se desploma un 33% sin que haya bajado ningún precio: eso
        es lo que se estaría usando para deflactar al 25,4% de productos sin ancla propia.
        """
        hechos = pd.DataFrame(
            [
                (1, MES[1], 20.0, 200.0),
                (1, MES[2], 20.0, 200.0),
                (1, MES[3], 20.0, 200.0),
                (2, MES[1], 20_000.0, 20_000.0),
                (2, MES[2], 20_000.0, 20_000.0),
                (2, MES[3], 20_000.0, 20_000.0),
                (3, MES[2], 20.0, 200.0),
                (3, MES[3], 20.0, 200.0),
            ],
            columns=["id_producto", "anio_mes", "precio_prom", "revenue"],
        )

        r = relativos_apareados(hechos).assign(id_nivel="X")
        s = _serie(indice_de_nivel(r, "categoria", muestra_minima=2))

        assert list(s.round(10)) == [1.0, 1.0], "ningun precio cambio: el indice no se mueve"

        promedio = hechos.groupby("anio_mes")["precio_prom"].mean()
        caida = 1 - promedio[MES[2]] / promedio[MES[1]]
        assert caida > 0.30, "el promedio de precios inventa una caida del 33%"


class TestContrato:
    def test_respeta_el_esquema_c2_del_diccionario(self):
        r = _relativos([("X", 2, 1.1, 1.0)] * 3)

        indice = indice_de_nivel(r, "categoria")

        assert tuple(indice.columns) == COLUMNAS_INDICE
        for columna, tipo in ESQUEMAS["indice_precio_nivel"].items():
            assert indice[columna].dtype == tipo, columna

    def test_sin_relativos_devuelve_vacio_con_las_columnas_puestas(self):
        vacio = indice_de_nivel(_relativos([]).iloc[:0], "categoria")

        assert vacio.empty
        assert tuple(vacio.columns) == COLUMNAS_INDICE


class TestFactorEntre:
    def test_es_el_cociente_del_indice(self):
        s = pd.Series([1.0, 1.5, 3.0], index=[MES[1], MES[2], MES[3]])

        assert factor_entre(s, MES[1], MES[3]) == pytest.approx(3.0)
        assert factor_entre(s, MES[3], MES[1]) == pytest.approx(1 / 3)

    @pytest.mark.parametrize("desde, hasta", [(MES[9], MES[2]), (MES[1], MES[9])])
    def test_si_falta_un_mes_devuelve_nan_para_que_la_cascada_baje_un_peldano(
        self, desde, hasta
    ):
        s = pd.Series([1.0, 1.5], index=[MES[1], MES[2]])

        assert np.isnan(factor_entre(s, desde, hasta))
