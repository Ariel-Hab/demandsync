"""Tests del generador de dataset sintético (T0.4).

**Por qué existe este archivo.** Hasta T0.4 el generador no tenía un solo test: se
verificaba mirando el manifiesto a ojo. Eso alcanzó mientras el dataset solo tenía que
"parecerse" a los datos reales, pero las cuatro deudas que T0.4 cierra son justamente
propiedades que **el manifiesto podría reportar bien y el dataset no tener** — y peor, tres
de ellas son deudas cuya ausencia se lee como una buena noticia: cero meses negativos, cero
productos nuevos, cero categorías raras. Un dataset limpio parece un dataset bueno.

Lo que se testea acá son las cuatro condiciones **sobre la salida**, no sobre los
parámetros. Que `TASA_BAJA_OBJETIVO` diga 5% no prueba nada sobre el parquet.

Las aserciones de calibración usan una tolerancia acorde al tamaño de muestra del test, que
es chico a propósito (la suite tiene que correr rápido). **El gate estricto de ±3 puntos se
verifica al tamaño real y su evidencia es `datasets/sintetico/manifiesto.json`**, no este
archivo.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RAIZ_REPO = Path(__file__).resolve().parents[2]
if str(RAIZ_REPO) not in sys.path:
    sys.path.insert(0, str(RAIZ_REPO))

from datasets.sintetico import parametros as P  # noqa: E402
from datasets.sintetico.demanda import _ventana_de_calibracion  # noqa: E402
from datasets.sintetico.hechos import generar_todo  # noqa: E402
from datasets.sintetico.manifiesto import calcular_metricas  # noqa: E402

N_PRODUCTOS = 500
N_CLIENTES = 150


@pytest.fixture(scope="module")
def generado():
    """Un dataset chico, generado una sola vez para todo el módulo."""
    rng = np.random.default_rng(42)
    tablas, _series, productos = generar_todo(rng, N_PRODUCTOS, N_CLIENTES)
    return tablas, productos


@pytest.fixture(scope="module")
def tablas(generado):
    return generado[0]


# ---------------------------------------------------------------------------
# Deuda #1 — cliente_feature versionada
# ---------------------------------------------------------------------------


def test_cliente_feature_tiene_mas_de_una_version(tablas):
    """La deuda tal cual: antes había una sola `fecha_calculo` para todas las filas."""
    fechas = tablas["cliente_feature"]["fecha_calculo"]
    esperadas = P.N_MESES // P.PASO_MESES_CLIENTE_FEATURE
    assert fechas.nunique() == esperadas > 1


def test_la_clave_de_cliente_feature_es_cliente_mas_fecha(tablas):
    """Si `(id_cliente, fecha_calculo)` se repitiera, el recorte del arnés dejaría dos
    filas para el mismo cliente y el predictor de M2.2 elegiría una en silencio."""
    cf = tablas["cliente_feature"]
    assert not cf.duplicated(subset=["id_cliente", "fecha_calculo"]).any()


def test_ninguna_version_tiene_recency_negativa(tablas):
    """Invariante barato que delata leakage: una recency negativa significa que la última
    compra que vio esa versión es **posterior** a su propia `fecha_calculo`."""
    assert (tablas["cliente_feature"]["recency_dias"] >= 0).all()


def test_cada_version_se_calcula_solo_con_su_pasado(tablas):
    """El atajo tentador es emitir N versiones calculadas todas sobre la historia completa
    y solo cambiarles la etiqueta: la tabla *parece* versionada, el leakage sigue intacto y
    ahora además es invisible. Este test recalcula una versión temprana desde los hechos y
    exige que coincida.
    """
    cf = tablas["cliente_feature"]
    hechos = tablas["hecho_venta_mensual_cliente_producto"]

    fecha = sorted(cf["fecha_calculo"].unique())[1]
    ventana_ini = fecha - pd.DateOffset(months=11)
    esperado = (
        hechos[(hechos["anio_mes"] <= fecha) & (hechos["anio_mes"] >= ventana_ini)]
        .groupby("id_cliente")["unidades"]
        .sum()
    )

    version = cf[cf["fecha_calculo"] == fecha].set_index("id_cliente")
    comunes = version.index.intersection(esperado.index)
    assert len(comunes) > 0
    pd.testing.assert_series_equal(
        version.loc[comunes, "volumen_anual"],
        esperado.loc[comunes].rename("volumen_anual"),
        check_names=False,
    )


# Acá vivía un test de que un cliente no aparece en versiones anteriores a su primera
# compra. Se sacó porque **no falla con el bug puesto**: el generador no modela altas de
# cliente, así que los 1.600 compran en los primeros meses y la aserción no se puede
# violar. Un test que no discrimina es decoración, y encima da la sensación de que la
# propiedad está cubierta. Vuelve a tener sentido el día que el generador tenga altas de
# cliente — anotado como deuda en el roadmap §12.1.


# ---------------------------------------------------------------------------
# Deuda #2 — meses con neto negativo o cero
# ---------------------------------------------------------------------------


def test_existen_meses_con_neto_negativo(tablas):
    """Antes de T0.4 eran cero: las notas de crédito vivían solo en el JSON del contrato,
    aplicadas después de agregar, así que el neto mensual nunca podía dar negativo."""
    assert (tablas["hecho_venta_mensual_producto"]["unidades"] < 0).sum() > 0


def test_existen_meses_con_neto_exactamente_cero(tablas):
    assert (tablas["hecho_venta_mensual_producto"]["unidades"] == 0).sum() > 0


def test_precio_prom_de_un_mes_de_neto_cero_es_nan_y_no_infinito(tablas):
    """Misma regla que `extraer_snap.py:187` sobre datos reales. Un infinito no rompe
    nada acá: se propaga por la cadena de deflación de M2 y ensucia el resultado sin que
    nadie se entere, que es peor que fallar.
    """
    hechos = tablas["hecho_venta_mensual_producto"]
    neto_cero = hechos[hechos["unidades"] == 0]

    assert len(neto_cero) > 0
    assert neto_cero["precio_prom"].isna().all()
    assert not np.isinf(hechos["precio_prom"].to_numpy()).any()


def test_existe_al_menos_un_precio_implicito_negativo(tablas):
    """El caso de §5.5 #6: unidades y revenue netean con signos opuestos porque la
    devolución fue a un precio distinto del de la venta. Es el insumo contra el que M2.1
    tiene que defenderse con el clamp de ratios, y el sintético no lo produce solo.
    """
    hechos = tablas["hecho_venta_mensual_producto"]
    cruzados = hechos[(hechos["unidades"] < 0) & (hechos["revenue"] > 0)]
    assert len(cruzados) > 0
    assert (cruzados["precio_prom"] < 0).all()


def test_las_dos_tablas_de_hechos_netean_igual(tablas):
    """Las devoluciones se siembran a nivel cliente×producto; si la agregación a producto
    no las arrastrara, las dos tablas contarían historias distintas."""
    por_producto = (
        tablas["hecho_venta_mensual_cliente_producto"]
        .groupby(["id_producto", "anio_mes"], as_index=False)["unidades"]
        .sum()
    )
    esperado = tablas["hecho_venta_mensual_producto"][["id_producto", "anio_mes", "unidades"]]
    unido = esperado.merge(por_producto, on=["id_producto", "anio_mes"], suffixes=("", "_det"))
    assert len(unido) == len(esperado)
    assert np.allclose(unido["unidades"], unido["unidades_det"])


# ---------------------------------------------------------------------------
# Deuda #3 — altas y bajas de producto
# ---------------------------------------------------------------------------


def test_hay_productos_con_alta_dentro_de_la_ventana_de_clasificacion(tablas):
    """La deuda: 0 de 2.300 productos nacían dentro de la ventana, así que la regla de
    calendario de ADR-010 no la ejercitaba ningún dato a escala. M1.8 mostró que en la
    realidad esos productos son el 100% de la cobertura faltante del piso.
    """
    hechos = tablas["hecho_venta_mensual_producto"]
    con_venta = hechos[hechos["unidades"] > 0]
    primera = con_venta.groupby("id_producto")["anio_mes"].min()

    ultimo = con_venta["anio_mes"].max()
    inicio_ventana = ultimo - pd.DateOffset(months=P.VENTANA_INTERMITENCIA_MESES - 1)
    pct = 100 * (primera >= inicio_ventana).mean()

    assert pct > 0
    assert abs(pct - 20.0) <= 6.0, f"altas en ventana: {pct:.1f}% (objetivo 20%)"


def test_hay_productos_que_dejan_de_venderse(tablas):
    hechos = tablas["hecho_venta_mensual_producto"]
    con_venta = hechos[hechos["unidades"] > 0]
    ultima = con_venta.groupby("id_producto")["anio_mes"].max()
    limite = con_venta["anio_mes"].max() - pd.DateOffset(months=P.MESES_MIN_SILENCIO_BAJA - 1)
    assert (ultima <= limite).sum() > 0


def test_las_lumpy_mueren_mas_que_las_suaves(generado):
    """Medido sobre datos reales: `lumpy` muere 4,9× más que `suave` (roadmap §12.1). Si
    las bajas se sortearan independientes del arquetipo el dataset sería irreal justo en
    la cola, que es donde el modelo global de M2 tiene que demostrar que sirve.
    """
    _tablas, productos = generado
    murio = productos["mes_baja"] < P.N_MESES
    tasa = productos.assign(murio=murio).groupby("arquetipo")["murio"].mean()
    assert tasa["lumpy"] > tasa["suave"]


def test_un_producto_no_vende_antes_de_su_alta_ni_despues_de_su_baja(generado):
    tablas_, productos = generado
    hechos = tablas_["hecho_venta_mensual_producto"]
    meses = pd.date_range(P.PRIMER_MES, periods=P.N_MESES, freq="MS")

    con_venta = hechos[hechos["unidades"] > 0]
    limites = productos.set_index("id_producto")[["mes_alta", "mes_baja"]]
    unido = con_venta.join(limites, on="id_producto")

    assert (unido["anio_mes"] >= meses[unido["mes_alta"].to_numpy()]).all()
    fin = np.minimum(unido["mes_baja"].to_numpy(), P.N_MESES - 1)
    assert (unido["anio_mes"] <= meses[fin]).all()


@pytest.mark.parametrize(
    ("mes_alta", "fin_vida", "esperado"),
    [
        (0, 96, (60, 96)),  # producto de toda la historia: los últimos 36
        (86, 96, (86, 96)),  # alta reciente: 10 meses, NO 36
        (0, 40, (4, 40)),  # baja vieja: la ventana termina en la baja
        (30, 40, (30, 40)),  # nace y muere adentro: solo su vida
    ],
)
def test_la_ventana_de_calibracion_respeta_alta_y_baja(mes_alta, fin_vida, esperado):
    """El bug que T0.4 arregla en `demanda.py`, aislado.

    El bucle de rechazo clasificaba sobre `serie[-36:]` crudo, sin la regla de ADR-010 que
    sí aplica `clasificar_series` en el motor. Con un alta en el mes 86 eso arrastra 26
    ceros que nunca existieron: infla el ADI y calibra el producto como intermitente
    mientras el motor, midiéndolo sobre sus 10 meses reales, lo vería suave. **El generador
    y el motor dirían cosas distintas sobre la misma serie**, que es exactamente lo que
    compartir el clasificador debía impedir.
    """
    assert _ventana_de_calibracion(mes_alta, fin_vida, 36) == esperado


# ---------------------------------------------------------------------------
# Deuda #4 — categorías reales
# ---------------------------------------------------------------------------


def test_las_categorias_son_las_doce_reales(tablas):
    """Antes eran ocho inventadas (`antiparasitarios`, `vacunas`, …) que no existen en el
    catálogo del cliente."""
    assert set(tablas["catalogo_producto"]["categoria"]) == set(P.CATEGORIAS)


def test_la_categoria_de_un_solo_producto_siempre_aparece(tablas):
    """`HIGIENE Y BELLEZA (odontologico)` es 0,05% del catálogo real: con un sorteo
    ponderado sin más, una de cada tres semillas la deja vacía. Y es **el motivo** de traer
    la lista completa — el caso borde de una categoría con un único producto es lo que
    tiene que ejercitar el encoding de features de M2.2. Una deuda que se arregla en dos de
    cada tres semillas no está arreglada.
    """
    conteo = tablas["catalogo_producto"]["categoria"].value_counts()
    assert conteo.get("HIGIENE Y BELLEZA (odontologico)", 0) >= 1


def test_la_distribucion_de_categorias_no_es_uniforme(tablas):
    """El generador repartía uniforme; la realidad va de `CLINICO` 33% a un singleton."""
    frecuencia = tablas["catalogo_producto"]["categoria"].value_counts(normalize=True)
    assert frecuencia.max() > 4 * frecuencia.min()
    assert frecuencia.idxmax() == "CLINICO"


def test_sin_categoria_es_un_bucket_grande_y_no_un_hueco(tablas):
    """Un quinto del catálogo real no tiene etiqueta. No es un error de datos: es lo que
    va a recibir M2.2, y un generador que le da categoría al 100% lo esconde."""
    pct = 100 * (tablas["catalogo_producto"]["categoria"] == "SIN CATEGORIA").mean()
    assert abs(pct - 22.43) <= 6.0, f"SIN CATEGORIA: {pct:.1f}% (objetivo 22,4%)"


# ---------------------------------------------------------------------------
# El manifiesto es la evidencia del gate: tiene que reportar las cuatro
# ---------------------------------------------------------------------------


def test_el_manifiesto_reporta_las_cuatro_condiciones_de_t0_4(tablas):
    from datetime import date

    metricas = calcular_metricas(
        tablas, hoy=date(2026, 7, 31), semilla=42, n_productos=N_PRODUCTOS, n_clientes=N_CLIENTES
    )
    for bloque in (
        "cliente_feature_versionada",
        "meses_degenerados",
        "altas_y_bajas",
        "categorias",
    ):
        assert bloque in metricas, f"el manifiesto no reporta {bloque}"
        assert "gate_ok" in metricas[bloque]


TOLERANCIA_CUADRANTES_MUESTRA_CHICA = 6.0
"""El gate de S0 son ±3 puntos **a 2.300 productos**. Con los 500 de este módulo el error
de muestreo solo ya da ~2 puntos de desvío estándar en `intermitente`: medido sobre cinco
semillas, el desvío máximo va de 1,5 a 4,3, y a tamaño real se queda en ≤1,9. Asertar ±3 acá
sería un test que falla por la semilla y no por el código. Lo que este test cuida es que las
altas y bajas no rompan la calibración **estructuralmente** — un cuadrante que se vacía o
se dispara 10 puntos. El ±3 de verdad se verifica a tamaño real y su evidencia es
`datasets/sintetico/manifiesto.json`."""


def test_el_gate_de_cuadrantes_sobrevive_a_las_altas_y_bajas(tablas):
    """Las bajas correlacionadas con el arquetipo corren la mezcla de supervivientes hacia
    `suave`, y las altas recientes se clasifican sobre ventanas cortas. Ninguna de las dos
    puede romper la calibración que el gate de S0 ya exigía.
    """
    from datetime import date

    metricas = calcular_metricas(
        tablas, hoy=date(2026, 7, 31), semilla=42, n_productos=N_PRODUCTOS, n_clientes=N_CLIENTES
    )
    desvios = metricas["cuadrantes_intermitencia"]["desvio_puntos"]

    assert set(desvios) == set(P.PROPORCION_ARQUETIPOS), "algún cuadrante quedó vacío"
    peor = max(desvios.items(), key=lambda kv: abs(kv[1]))
    assert abs(peor[1]) <= TOLERANCIA_CUADRANTES_MUESTRA_CHICA, f"{peor[0]}: {peor[1]} pts"
