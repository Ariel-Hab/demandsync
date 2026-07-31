"""Tests de la puerta de entrada de la deflación (M2.1).

Todo lo que pase de acá entra a una media geométrica encadenada, donde un solo valor
absurdo no se promedia: se arrastra. Por eso los casos degenerados de §5.5 #6 se prueban
uno por uno y no "en general".
"""

import numpy as np
import pandas as pd
import pytest

from motor.deflacion.precios import (
    es_utilizable,
    relativos_apareados,
    ultimo_precio_utilizable,
)


def _hechos(filas) -> pd.DataFrame:
    """`filas` = (id_producto, 'AAAA-MM', precio_prom, revenue)."""
    columnas = ["id_producto", "anio_mes", "precio_prom", "revenue"]
    return pd.DataFrame(filas, columns=columnas).assign(
        anio_mes=lambda d: pd.to_datetime(d["anio_mes"], format="%Y-%m")
    )


class TestEsUtilizable:
    @pytest.mark.parametrize(
        "precio, esperado, motivo",
        [
            (100.0, True, "precio normal"),
            (0.01, True, "basura pero positivo: lo filtra el clamp, no esta puerta"),
            (np.nan, False, "unidades == 0, 4.848 filas reales"),
            (0.0, False, "cero es ausencia de precio, no precio gratis (ADR-010 §4)"),
            (-250.0, False, "signos cruzados por nota de credito, 22 filas reales (§5.5 #6)"),
            (np.inf, False, "division por cero si alguna vez entra sin la guarda del extract"),
            (-np.inf, False, "idem, del lado negativo"),
        ],
    )
    def test_clasifica_cada_estado(self, precio, esperado, motivo):
        assert es_utilizable(pd.Series([precio])).item() is esperado, motivo

    def test_un_precio_negativo_no_llega_al_indice(self):
        """El caso que motiva la guarda: 22 filas reales, pero un ancla negativa
        propagada por la cascada contamina toda una categoría."""
        hechos = _hechos(
            [
                (1, "2024-01", 100.0, 1000.0),
                (1, "2024-02", -250.0, -500.0),
                (1, "2024-03", 110.0, 1100.0),
            ]
        )
        assert relativos_apareados(hechos).empty


class TestRelativosApareados:
    def test_calcula_el_relativo_y_el_peso(self):
        hechos = _hechos([(1, "2024-01", 100.0, 1000.0), (1, "2024-02", 130.0, 2000.0)])

        r = relativos_apareados(hechos)

        assert len(r) == 1
        assert r["relativo"].item() == pytest.approx(1.3)
        assert r["peso"].item() == pytest.approx(1500.0), "revenue promedio de los dos meses"
        assert r["anio_mes"].item() == pd.Timestamp("2024-02"), "el par se fecha en el mes final"

    def test_un_hueco_de_calendario_no_produce_relativo(self):
        """Un intermitente que reaparece a los 3 meses no tuvo un cambio *mensual* de
        precio. Repartir el salto inventaría información que nadie observó."""
        hechos = _hechos([(1, "2024-01", 100.0, 1000.0), (1, "2024-04", 200.0, 1000.0)])

        assert relativos_apareados(hechos).empty

    def test_un_mes_no_utilizable_corta_los_pares_de_los_dos_lados(self):
        """El caso que se escapa fácil: al descartar el mes del medio, enero y marzo
        quedan pegados en la tabla y un `shift(1)` ingenuo los aparearía como si fueran
        consecutivos, fabricando un relativo de 3 meses disfrazado de mensual."""
        hechos = _hechos(
            [
                (1, "2024-01", 100.0, 1000.0),
                (1, "2024-02", np.nan, 0.0),
                (1, "2024-03", 300.0, 1000.0),
            ]
        )

        assert relativos_apareados(hechos).empty

    def test_no_aparea_a_traves_del_borde_entre_productos(self):
        """Dos productos distintos, meses consecutivos: si el `shift` no respeta el
        `groupby`, sale un relativo que mezcla los precios de los dos."""
        hechos = _hechos([(1, "2024-01", 100.0, 1000.0), (2, "2024-02", 500.0, 1000.0)])

        assert relativos_apareados(hechos).empty

    def test_encadena_varios_meses_del_mismo_producto(self):
        hechos = _hechos(
            [
                (1, "2024-01", 100.0, 1000.0),
                (1, "2024-02", 110.0, 1000.0),
                (1, "2024-03", 121.0, 1000.0),
            ]
        )

        r = relativos_apareados(hechos).sort_values("anio_mes")

        assert list(r["relativo"].round(6)) == [1.1, 1.1]

    def test_no_depende_del_orden_de_las_filas_de_entrada(self):
        filas = [
            (2, "2024-02", 55.0, 500.0),
            (1, "2024-01", 100.0, 1000.0),
            (2, "2024-01", 50.0, 500.0),
            (1, "2024-02", 110.0, 1000.0),
        ]
        ordenado = relativos_apareados(_hechos(filas)).sort_values(["id_producto", "anio_mes"])
        revuelto = relativos_apareados(_hechos(filas[::-1])).sort_values(
            ["id_producto", "anio_mes"]
        )

        pd.testing.assert_frame_equal(
            ordenado.reset_index(drop=True), revuelto.reset_index(drop=True)
        )


class TestUltimoPrecioUtilizable:
    def test_toma_el_ultimo_utilizable_y_no_el_ultimo_mes(self):
        """El producto vendió en marzo pero con neto cero: su último precio observado
        sigue siendo el de febrero. Tomar marzo daría un ancla nula."""
        hechos = _hechos(
            [
                (1, "2024-01", 100.0, 1000.0),
                (1, "2024-02", 120.0, 1200.0),
                (1, "2024-03", np.nan, 0.0),
            ]
        )

        ultimo = ultimo_precio_utilizable(hechos)

        assert ultimo["precio_prom"].item() == 120.0
        assert ultimo["anio_mes"].item() == pd.Timestamp("2024-02")

    def test_omite_al_producto_que_nunca_tuvo_precio_utilizable(self):
        """No hay desde dónde trasladar: su deflactor tiene que quedar nulo a propósito,
        y eso se decide arriba. Acá simplemente no aparece."""
        hechos = _hechos([(1, "2024-01", 100.0, 1000.0), (2, "2024-01", np.nan, 0.0)])

        assert list(ultimo_precio_utilizable(hechos)["id_producto"]) == [1]
