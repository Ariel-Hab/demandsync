"""Tests del transformador de deflación (M2.1) — los casos CP-INF-01..05 de ADR-002.

CP-INF-05 (clamp) vive en `test_deflacion_indices.py`, que es donde está el clamp.
CP-INF-04 (RFM sobre montos deflactados) es M3.3 y no se prueba acá.

El IPC se inyecta sintético en casi todos los casos: si los tests dependieran del CSV
real, actualizarlo los rompería y el número esperado dejaría de ser calculable a mano.
"""

import numpy as np
import pandas as pd
import pytest

from motor.datos.diccionario import ESQUEMAS
from motor.deflacion import TransformadorDeflacion

COLUMNAS_HECHOS = ["id_producto", "anio_mes", "unidades", "revenue", "precio_prom"]


def _meses(desde: str, n: int) -> pd.DatetimeIndex:
    return pd.date_range(desde, periods=n, freq="MS")


def _serie(id_producto, meses, precio_inicial, crecimiento=1.0, unidades=10.0):
    """Un producto que vende `unidades` todos los meses a un precio que crece geométrico."""
    return [
        (id_producto, m, unidades, unidades * precio_inicial * crecimiento**i,
         precio_inicial * crecimiento**i)
        for i, m in enumerate(meses)
    ]


def _hechos(*bloques) -> pd.DataFrame:
    return pd.DataFrame([f for b in bloques for f in b], columns=COLUMNAS_HECHOS)


def _ipc(meses, crecimiento=1.10) -> pd.DataFrame:
    return pd.DataFrame(
        {"anio_mes": meses, "indice": [100 * crecimiento**i for i in range(len(meses))]}
    )


def _catalogo(asignacion: dict[int, tuple[str, str]]) -> pd.DataFrame:
    return pd.DataFrame(
        [(p, c, lab) for p, (c, lab) in asignacion.items()],
        columns=["id_producto", "categoria", "laboratorio"],
    )


class TestCpInf01:
    """Dos ventas idénticas separadas por años se normalizan a valores comparables."""

    def test_la_misma_venta_en_2019_y_en_2025_vale_lo_mismo_deflactada(self):
        meses = _meses("2019-01-01", 84)  # hasta 2025-12
        hechos = _hechos(_serie(1, meses, precio_inicial=100.0, crecimiento=1.05))

        ajustado = (
            TransformadorDeflacion(ipc=_ipc(meses))
            .ajustar(hechos, meses[-1])
            .transformar(hechos)
        )

        real = ajustado.set_index("anio_mes")["revenue_real"]
        nominal = ajustado.set_index("anio_mes")["revenue"]

        assert real[pd.Timestamp("2019-06-01")] == pytest.approx(
            real[pd.Timestamp("2025-06-01")]
        )
        assert nominal[pd.Timestamp("2025-06-01")] / nominal[pd.Timestamp("2019-06-01")] > 20, (
            "sin deflactar, la venta de 2025 parece 20 veces mas grande"
        )


class TestCpInf02:
    """La deflación preserva el descuento individual. Es el corazón de ADR-002."""

    @pytest.fixture
    def escenario(self):
        """Un producto, dos clientes: A paga 100 por unidad y B paga 80 (20% menos).

        El promedio ponderado del producto es 90, así que B está 11,1% por debajo del
        promedio. Los dos cocientes tienen que sobrevivir a la deflación.
        """
        meses = _meses("2024-01-01", 12)
        producto = [
            (1, m, 20.0, 1800.0 * 1.1**i, 90.0 * 1.1**i) for i, m in enumerate(meses)
        ]
        clientes = pd.DataFrame(
            [
                (c, 1, m, 10.0, 10 * precio * 1.1**i)
                for i, m in enumerate(meses)
                for c, precio in [(1, 100.0), (2, 80.0)]
            ],
            columns=["id_cliente", "id_producto", "anio_mes", "unidades", "revenue"],
        )
        return pd.DataFrame(producto, columns=COLUMNAS_HECHOS), clientes, meses

    def test_cp_inf_02_el_descuento_sobrevive(self, escenario):
        producto, clientes, meses = escenario

        salida = (
            TransformadorDeflacion(ipc=_ipc(meses))
            .ajustar(producto, meses[-1])
            .transformar(clientes)
        )

        primero = salida[salida["anio_mes"] == meses[0]].set_index("id_cliente")["revenue_real"]
        ultimo = salida[salida["anio_mes"] == meses[-1]].set_index("id_cliente")["revenue_real"]

        assert primero[2] / primero[1] == pytest.approx(0.8)
        assert ultimo[2] / ultimo[1] == pytest.approx(0.8), "no se diluye con el tiempo"

    def test_la_re_tasacion_prohibida_borraria_ese_descuento(self, escenario):
        """`unidades × precio_de_hoy` es la misma cuenta con el descuento forzado a 1.
        ADR-002 la prohíbe; este test muestra exactamente qué se perdería."""
        producto, clientes, meses = escenario
        ajustado = TransformadorDeflacion(ipc=_ipc(meses)).ajustar(producto, meses[-1])
        ancla = ajustado.ancla_["precio_prom_hoy"].item()

        re_tasado = clientes["unidades"] * ancla

        assert re_tasado.nunique() == 1, "los dos clientes quedan pagando exactamente lo mismo"

    def test_el_cliente_barato_sigue_por_debajo_del_promedio_del_producto(self, escenario):
        producto, clientes, meses = escenario
        ajustado = TransformadorDeflacion(ipc=_ipc(meses)).ajustar(producto, meses[-1])

        del_cliente = ajustado.transformar(clientes)
        del_producto = ajustado.transformar(producto)

        b = del_cliente[(del_cliente["id_cliente"] == 2) & (del_cliente["anio_mes"] == meses[0])]
        p = del_producto[del_producto["anio_mes"] == meses[0]]
        precio_real_b = b["revenue_real"].item() / b["unidades"].item()
        precio_real_p = p["revenue_real"].item() / p["unidades"].item()

        assert precio_real_b / precio_real_p == pytest.approx(80 / 90)


class TestCpInf03Cascada:
    """Fallback de ancla: producto → categoría → laboratorio → IPC."""

    @pytest.fixture
    def escenario(self):
        """Cuatro productos sin venta reciente, cada uno resolviendo por un peldaño
        distinto, más los productos vivos que le dan muestra a cada nivel."""
        meses = _meses("2024-01-01", 12)
        cortos = meses[:3]

        hechos = _hechos(
            # Vivos de la categoria GRANDE (y del laboratorio L1): le dan muestra a los dos.
            _serie(2, meses, 100.0, 1.10),
            _serie(3, meses, 110.0, 1.10),
            _serie(4, meses, 120.0, 1.10),
            # Vivo de la categoria CHICA: solo, nunca alcanza la muestra minima de 3.
            _serie(5, meses, 130.0, 1.10),
            # 10 resuelve por CATEGORIA: esta en GRANDE, que tiene muestra en los dos meses.
            _serie(10, cortos, 100.0, 1.10),
            # 11 resuelve por LABORATORIO: su categoria CHICA no llega, pero L1 si.
            _serie(11, cortos, 100.0, 1.10),
            # 12 resuelve por IPC: categoria y laboratorio propios, ambos de un solo producto.
            _serie(12, cortos, 100.0, 1.10),
        )
        catalogo = _catalogo(
            {
                2: ("GRANDE", "L1"), 3: ("GRANDE", "L1"), 4: ("GRANDE", "L1"),
                5: ("CHICA", "L1"),
                10: ("GRANDE", "L1"), 11: ("CHICA", "L1"), 12: ("SOLA", "LSOLO"),
            }
        )
        return hechos, catalogo, meses

    def test_cada_producto_resuelve_por_el_peldano_esperado(self, escenario):
        hechos, catalogo, meses = escenario

        ajustado = TransformadorDeflacion(catalogo=catalogo, ipc=_ipc(meses)).ajustar(
            hechos, meses[-1]
        )
        origen = ajustado.origen_ancla_

        assert origen[10] == "categoria"
        assert origen[11] == "laboratorio", "el peldano que los datos reales casi no ejercitan"
        assert origen[12] == "ipc"
        assert origen[2] == "producto", "los vivos tienen ancla propia"

    def test_la_cascada_presta_el_indice_y_no_el_nivel(self):
        """Un producto de $10.000 en una categoría de productos de $100. Al perder su
        ancla propia tiene que conservar **su** nivel de precio y tomar prestada solo la
        deriva del vecindario. Heredar el precio de la categoría lo abarataría 100 veces."""
        meses = _meses("2024-01-01", 12)
        hechos = _hechos(
            _serie(2, meses, 100.0, 1.10),
            _serie(3, meses, 100.0, 1.10),
            _serie(4, meses, 100.0, 1.10),
            _serie(9, meses[:3], 10_000.0, 1.10),
        )
        catalogo = _catalogo({p: ("A", "L") for p in (2, 3, 4, 9)})

        ajustado = TransformadorDeflacion(catalogo=catalogo, ipc=_ipc(meses)).ajustar(
            hechos, meses[-1]
        )
        ancla = ajustado.ancla_.set_index("id_producto")["precio_prom_hoy"]

        # Ultimo precio propio (mes 3) = 10.000·1,1² = 12.100; la categoria se mueve 1,1
        # por mes desde el mes 3 hasta el 12, o sea 1,1⁹.
        assert ancla[9] == pytest.approx(12_100 * 1.1**9, rel=1e-6)

        # Sigue valiendo ~100 veces lo que sus vecinos, que es su escala real. No da 100
        # exacto —da 109,7— porque el ancla de los vivos promedia tres meses y queda por
        # detrás del precio del corte, mientras que la derivada se traslada hasta el corte.
        # Lo que el test descarta es el orden de magnitud equivocado: heredar el *nivel*
        # de la categoría daría un cociente cercano a 1.
        assert ancla[9] / ancla[2] > 90

    def test_sin_catalogo_la_cascada_es_producto_a_ipc(self):
        meses = _meses("2024-01-01", 12)
        hechos = _hechos(_serie(1, meses, 100.0, 1.10), _serie(2, meses[:3], 50.0, 1.10))

        ajustado = TransformadorDeflacion(ipc=_ipc(meses)).ajustar(hechos, meses[-1])

        assert ajustado.origen_ancla_[2] == "ipc"
        assert set(ajustado.indices_["nivel"]) == {"ipc"}


class TestPreciosNoUtilizables:
    """§5.5 #6: 4.848 filas reales con precio NaN y 22 con precio ≤ 0."""

    def test_un_precio_negativo_no_produce_un_ancla_negativa(self):
        """El daño no son las 22 filas: es que un ancla negativa se propaga por la
        cascada y contamina a todos los productos que dependen de ese nivel."""
        meses = _meses("2024-01-01", 12)
        filas = _serie(1, meses, 100.0, 1.10)
        filas[-1] = (1, meses[-1], -5.0, 900.0, -180.0)  # nota de credito con signos cruzados
        hechos = _hechos(filas, _serie(2, meses, 100.0, 1.10))

        ajustado = TransformadorDeflacion(ipc=_ipc(meses)).ajustar(hechos, meses[-1])

        assert (ajustado.ancla_["precio_prom_hoy"].dropna() > 0).all()
        assert (ajustado.indices_["indice"] > 0).all()
        assert (ajustado.deflactor_["deflactor"].dropna() > 0).all()

    def test_un_mes_de_neto_cero_no_rompe_la_serie(self):
        meses = _meses("2024-01-01", 12)
        filas = _serie(1, meses, 100.0, 1.10)
        filas[5] = (1, meses[5], 0.0, 0.0, np.nan)
        hechos = _hechos(filas)

        ajustado = TransformadorDeflacion(ipc=_ipc(meses)).ajustar(hechos, meses[-1])
        deflactor = ajustado.deflactor_.set_index("anio_mes")["deflactor"]

        assert deflactor.notna().all(), "el mes sin precio se reconstruye, no queda hueco"
        assert deflactor[meses[5]] == pytest.approx(deflactor[meses[4]] / 1.1, rel=1e-9), (
            "reconstruido desde el mes anterior con la deriva del nivel"
        )

    def test_un_precio_propio_basura_infla_su_deflactor_pero_no_mueve_el_agregado(self):
        """**Limitación conocida de M2.1, medida y acotada — no es un descuido.**

        El clamp protege el índice *de nivel*, no el deflactor directo: cuando el producto
        tiene precio propio ese mes, el deflactor es `ancla / precio_propio`, y un precio
        de $0,01 lo hace explotar. Sobre el extract real son **93 filas de 7 productos**
        (0,068%) con deflactor hasta 1,2 millones.

        No mueve nada monetario porque esas filas tienen revenue ≈ 0: aportan 1,3 M sobre
        294.733 M de revenue real, o sea 0,000%. Pero la columna `deflactor` queda con
        valores sin sentido, y eso **sí** importa para cualquier feature de M2.2 que se
        construya sobre ella. Está anotado en el roadmap como decisión abierta.

        Este test fija las dos mitades del hecho para que ninguna cambie sin que se note.
        """
        meses = _meses("2024-01-01", 12)
        filas = _serie(1, meses, 100.0, 1.10)
        filas[3] = (1, meses[3], 2.0, 0.02, 0.01)  # precio basura, revenue despreciable
        hechos = _hechos(filas)

        ajustado = TransformadorDeflacion(ipc=_ipc(meses)).ajustar(hechos, meses[-1])
        salida = ajustado.transformar(hechos)
        deflactor = ajustado.deflactor_.set_index("anio_mes")["deflactor"]

        assert deflactor[meses[3]] > 1_000, "el deflactor de esa fila es absurdo"

        aporte = salida.loc[salida["anio_mes"] == meses[3], "revenue_real"].item()
        assert aporte < salida["revenue_real"].median(), (
            "y sin embargo aporta menos que una fila normal: el deflactor gigante lo "
            "compensa un revenue casi nulo, que es de donde salio el precio basura"
        )

    def test_un_producto_sin_ningun_precio_utilizable_queda_sin_ancla(self):
        """No se inventa un valor: queda `NaN` y la cobertura lo muestra."""
        meses = _meses("2024-01-01", 12)
        muerto = [(9, m, 0.0, 0.0, np.nan) for m in meses]
        hechos = _hechos(_serie(1, meses, 100.0, 1.10), muerto)

        ajustado = TransformadorDeflacion(ipc=_ipc(meses)).ajustar(hechos, meses[-1])
        ancla = ajustado.ancla_.set_index("id_producto")["precio_prom_hoy"]

        assert np.isnan(ancla[9])
        assert ajustado.origen_ancla_[9] == "sin_ancla"
        assert ajustado.cobertura_["sin_ancla"] == 1


class TestCobertura:
    def test_transformar_no_descarta_filas_sin_deflactor(self):
        """La cobertura tiene que ser visible, no silenciosa: si estas filas se cayeran,
        cualquier métrica calculada después se compararía sobre universos distintos
        (la leccion del piso de M1.8)."""
        meses = _meses("2024-01-01", 12)
        muerto = [(9, m, 0.0, 0.0, np.nan) for m in meses]
        hechos = _hechos(_serie(1, meses, 100.0, 1.10), muerto)

        salida = (
            TransformadorDeflacion(ipc=_ipc(meses)).ajustar(hechos, meses[-1]).transformar(hechos)
        )

        assert len(salida) == len(hechos)
        assert salida[salida["id_producto"] == 9]["revenue_real"].isna().all()


class TestAncla:
    def test_con_ventana_de_un_mes_el_corte_no_se_deflacta(self):
        """Invariante barato: el deflactor del mes del ancla vale 1, así que el monto del
        corte queda igual. Si esto falla, el ancla y la matriz no hablan del mismo precio."""
        meses = _meses("2024-01-01", 12)
        hechos = _hechos(_serie(1, meses, 100.0, 1.10))

        salida = (
            TransformadorDeflacion(ipc=_ipc(meses), ventana_ancla=1)
            .ajustar(hechos, meses[-1])
            .transformar(hechos)
        )
        fila = salida[salida["anio_mes"] == meses[-1]]

        assert fila["revenue_real"].item() == pytest.approx(fila["revenue"].item())

    def test_promedia_la_ventana_ponderando_por_unidades(self):
        meses = _meses("2024-01-01", 3)
        hechos = pd.DataFrame(
            [
                (1, meses[0], 1.0, 100.0, 100.0),
                (1, meses[1], 1.0, 200.0, 200.0),
                (1, meses[2], 8.0, 2400.0, 300.0),
            ],
            columns=COLUMNAS_HECHOS,
        )

        ajustado = TransformadorDeflacion(ipc=_ipc(meses)).ajustar(hechos, meses[-1])

        esperado = (100 * 1 + 200 * 1 + 300 * 8) / 10
        assert ajustado.ancla_["precio_prom_hoy"].item() == pytest.approx(esperado)


class TestCorte:
    def test_los_datos_posteriores_al_corte_se_ignoran(self):
        """La red completa es `verificar_sin_leakage` (M1.3, `test_leakage_deflacion.py`);
        esto es la versión directa y legible del mismo requisito."""
        meses = _meses("2024-01-01", 12)
        hechos = _hechos(_serie(1, meses, 100.0, 1.10))
        corte = meses[5]

        completo = TransformadorDeflacion(ipc=_ipc(meses)).ajustar(hechos, corte)
        truncado = TransformadorDeflacion(ipc=_ipc(meses)).ajustar(
            hechos[hechos["anio_mes"] <= corte], corte
        )

        pd.testing.assert_frame_equal(completo.ancla_, truncado.ancla_)
        assert completo.deflactor_["anio_mes"].max() == corte


class TestContrato:
    @pytest.fixture
    def ajustado(self):
        meses = _meses("2024-01-01", 12)
        hechos = _hechos(_serie(1, meses, 100.0, 1.10), _serie(2, meses, 50.0, 1.10))
        catalogo = _catalogo({1: ("A", "L"), 2: ("A", "L")})
        return TransformadorDeflacion(catalogo=catalogo, ipc=_ipc(meses)).ajustar(
            hechos, meses[-1]
        )

    @pytest.mark.parametrize("atributo, tabla", [("ancla_", "ancla_precio_producto"),
                                                 ("indices_", "indice_precio_nivel")])
    def test_las_salidas_respetan_el_esquema_c2(self, ajustado, atributo, tabla):
        salida = getattr(ajustado, atributo)

        assert list(salida.columns) == list(ESQUEMAS[tabla])
        for columna, tipo in ESQUEMAS[tabla].items():
            assert salida[columna].dtype == tipo, columna

    def test_nada_se_persiste(self, ajustado):
        """ADR-001: los hechos mensuales son inmutables y nominales. El transformador
        devuelve tablas en memoria; materializarlas es decisión de M4."""
        assert not hasattr(ajustado, "guardar")
