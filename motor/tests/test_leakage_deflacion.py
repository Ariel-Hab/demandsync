"""Red anti-leakage de deflación (M1.3) — **INNEGOCIABLE**.

`plan-diseno.md` §Protocolo: para el corte t, el ancla y todos los índices se calculan
solo con datos ≤ t. `viabilidad.md` §5 lo marca como el riesgo más sutil del motor,
porque su síntoma es un error de backtest *bajo*: se manifiesta como una buena noticia.

**Este archivo se escribió antes que la deflación de M2.1, a propósito** (orden del
roadmap). Como todavía no hay transformador que testear, lo que se prueba es que la red
funcione: se le pasan implementaciones **deliberadamente contaminadas** y se verifica
que las detecte. Un verificador que nunca se probó contra un caso malo no es una red,
es una decoración.

Cuando M2.1 exista, su transformador se pasa a `verificar_sin_leakage` y este archivo
gana un test más. No se toca lo de acá: los casos contaminados quedan como control
permanente de que la red sigue viva.

Corré solo esta red con: `pytest -m innegociable`
"""

import pandas as pd
import pytest

from motor.backtesting.leakage import LeakageTemporal, verificar_sin_leakage

pytestmark = pytest.mark.innegociable

MESES_ANCLA = 3
"""Ventana del ancla, como en ADR-002 (`precio_prom_hoy` sobre los meses recientes)."""


@pytest.fixture
def datos():
    """Tres productos, 24 meses, con precio creciente por inflación.

    El precio crece mes a mes a propósito: así, si un cálculo mira el futuro, el número
    que sale es visiblemente más alto y el leakage no se puede confundir con ruido.

    **El producto 3 deja de venderse en el mes 10**, y eso no es decorativo: es lo que
    hace que en los cortes posteriores no tenga ancla propia y se recorra el camino del
    fallback. Sin un producto así, el test del fallback contaminado pasaba sin ejercitar
    nunca la rama que dice probar — y el 25,4% de los productos reales está en esa
    situación (EDA §4).
    """
    meses = pd.date_range("2024-01-01", periods=24, freq="MS")
    filas = [
        {
            "id_producto": p,
            "anio_mes": m,
            "unidades": float(10 + i),
            "revenue": float((10 + i) * (100 + 5 * i) * p),
            "precio_prom": float((100 + 5 * i) * p),
        }
        for p in (1, 2, 3)
        for i, m in enumerate(meses)
        if not (p == 3 and i >= 10)
    ]
    return pd.DataFrame(filas)


@pytest.fixture
def cortes(datos):
    ultimo = datos["anio_mes"].max()
    return [ultimo - pd.DateOffset(months=k) for k in (12, 6, 1)]


# ---------------------------------------------------------------------------------
# Implementaciones de referencia (lo que M2.1 tiene que hacer)
# ---------------------------------------------------------------------------------


def ancla_correcta(datos: pd.DataFrame, corte: pd.Timestamp) -> pd.DataFrame:
    """`precio_prom_hoy` por producto, donde "hoy" es **el corte**."""
    desde = corte - pd.DateOffset(months=MESES_ANCLA - 1)
    ventana = datos[(datos["anio_mes"] <= corte) & (datos["anio_mes"] >= desde)]
    return (
        ventana.groupby("id_producto")["precio_prom"]
        .mean()
        .rename("precio_prom_hoy")
        .reset_index()
    )


def indice_correcto(datos: pd.DataFrame, corte: pd.Timestamp) -> pd.DataFrame:
    """Índice mensual rebasado al ancla **del corte**."""
    hasta = datos[datos["anio_mes"] <= corte]
    ancla = ancla_correcta(datos, corte).set_index("id_producto")["precio_prom_hoy"]
    con_ancla = hasta.join(ancla, on="id_producto")
    return (
        (con_ancla["precio_prom"] / con_ancla["precio_prom_hoy"])
        .groupby(con_ancla["anio_mes"])
        .mean()
        .rename("indice")
        .reset_index()
    )


# ---------------------------------------------------------------------------------
# Implementaciones contaminadas (los errores que la red tiene que atrapar)
# ---------------------------------------------------------------------------------


def ancla_con_leakage(datos: pd.DataFrame, corte: pd.Timestamp) -> pd.DataFrame:
    """El error textual de `plan-diseno.md`: el ancla "de hoy" se toma del hoy **real**
    del dataset y no del corte. Es el más fácil de escribir sin darse cuenta, porque
    `corte` queda como parámetro sin usar."""
    hoy = datos["anio_mes"].max()
    desde = hoy - pd.DateOffset(months=MESES_ANCLA - 1)
    ventana = datos[datos["anio_mes"] >= desde]
    return (
        ventana.groupby("id_producto")["precio_prom"]
        .mean()
        .rename("precio_prom_hoy")
        .reset_index()
    )


def ancla_con_fallback_con_leakage(datos: pd.DataFrame, corte: pd.Timestamp) -> pd.DataFrame:
    """Caso realista y mucho más sutil: la ventana por producto **sí** está bien
    filtrada al corte, pero el fallback de los productos sin ancla propia usa el
    promedio global de toda la historia, futuro incluido.

    Importa porque el fallback no es un caso borde: el 25,4% de los productos activos no
    tiene venta en los últimos 3 meses (EDA §4), así que este camino se recorre seguido.
    """
    ancla = ancla_correcta(datos, corte)
    promedio_global = datos["precio_prom"].mean()  # <-- mira el futuro
    presentes = set(datos.loc[datos["anio_mes"] <= corte, "id_producto"].unique())
    faltantes = sorted(presentes - set(ancla["id_producto"]))
    if faltantes:
        relleno = pd.DataFrame(
            {"id_producto": faltantes, "precio_prom_hoy": promedio_global}
        )
        ancla = pd.concat([ancla, relleno], ignore_index=True)
    return ancla


def indice_con_leakage_por_conteo(datos: pd.DataFrame, corte: pd.Timestamp) -> pd.DataFrame:
    """Leakage por **existencia** y no por valores: normaliza por la cantidad de meses
    del dataset completo. Los valores futuros no se leen nunca, pero su presencia sí —
    el caso que justifica que el verificador también truncue y no solo perturbe."""
    n_meses_totales = datos["anio_mes"].nunique()  # <-- cuenta meses futuros
    hasta = datos[datos["anio_mes"] <= corte]
    return (
        hasta.groupby("anio_mes")["precio_prom"]
        .mean()
        .div(n_meses_totales)
        .rename("indice")
        .reset_index()
    )


# ---------------------------------------------------------------------------------
# La red acepta lo correcto
# ---------------------------------------------------------------------------------


def test_el_ancla_bien_calculada_pasa(datos, cortes):
    verificar_sin_leakage(ancla_correcta, datos, cortes)


def test_el_indice_bien_calculado_pasa(datos, cortes):
    verificar_sin_leakage(indice_correcto, datos, cortes)


# ---------------------------------------------------------------------------------
# La red atrapa lo contaminado — es la razón de existir de este archivo
# ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("nombre", "implementacion"),
    [
        ("ancla del 'hoy' real en vez del corte", ancla_con_leakage),
        ("fallback con promedio global", ancla_con_fallback_con_leakage),
        ("normalización por cantidad de meses", indice_con_leakage_por_conteo),
    ],
)
def test_la_red_detecta_el_leakage(datos, cortes, nombre, implementacion):
    with pytest.raises(LeakageTemporal) as detectado:
        verificar_sin_leakage(implementacion, datos, cortes)

    mensaje = str(detectado.value)
    assert "LEAKAGE TEMPORAL" in mensaje
    assert "corte" in mensaje, f"el mensaje tiene que decir en qué corte falló ({nombre})"


def test_el_mensaje_distingue_leer_valores_de_usar_su_existencia(datos, cortes):
    """Diagnóstico, no solo alarma. Que fallen las dos variantes o solo una es la
    información que dice *dónde* buscar el bug, así que el verificador prueba ambas
    antes de cortar en vez de fallar en la primera."""
    with pytest.raises(LeakageTemporal, match="leyendo los valores del futuro") as leyendo:
        verificar_sin_leakage(ancla_con_leakage, datos, cortes)
    assert "perturbando los valores del futuro" in str(leyendo.value)

    with pytest.raises(LeakageTemporal, match="existencia de filas futuras") as existencia:
        verificar_sin_leakage(indice_con_leakage_por_conteo, datos, cortes)
    assert "perturbando" not in str(existencia.value), (
        "normalizar por cantidad de meses no lee valores futuros: si la perturbación "
        "también lo delatara, el diagnóstico estaría mal"
    )


def test_la_red_no_se_puede_quedar_sin_columnas_que_perturbar(datos, cortes):
    """Si solo quedara la variante de truncado, la red pasaría a ser más débil sin
    avisar. Preferimos que corte."""
    solo_claves = datos[["id_producto", "anio_mes"]]

    with pytest.raises(ValueError, match="columnas de valor"):
        verificar_sin_leakage(lambda d, c: d.head(1), solo_claves, cortes)


def test_se_verifica_en_todos_los_cortes(datos):
    """Un leakage puede no manifestarse en algunos cortes —por ejemplo en el último, que
    casi no tiene futuro por delante—, así que no alcanza con probar uno."""
    ultimo = datos["anio_mes"].max()
    corte_sin_futuro = ultimo

    # con el corte pegado al final del dataset, el ancla contaminada coincide con la
    # correcta y el leakage es invisible
    verificar_sin_leakage(ancla_con_leakage, datos, [corte_sin_futuro])

    # el mismo cálculo, mirando también un corte con futuro por delante, sí lo delata
    with pytest.raises(LeakageTemporal):
        verificar_sin_leakage(
            ancla_con_leakage, datos, [ultimo - pd.DateOffset(months=6), corte_sin_futuro]
        )


# ---------------------------------------------------------------------------------
# El transformador de verdad (M2.1). Lo de arriba no se toca: queda como control
# permanente de que la red sigue siendo capaz de detectar algo.
# ---------------------------------------------------------------------------------


@pytest.fixture
def datos_con_nivel():
    """Ocho productos, 24 meses, y el 8 se retira en el mes 10.

    No reusa el fixture `datos` de arriba a propósito: con tres productos y muestra mínima
    3, la categoría se queda sin pares apenas uno se retira y el índice de nivel deja de
    existir en el mes 10. La verificación de `indices_` pasaría sin haber comparado
    prácticamente nada — se comprobó por mutación que en ese fixture sacar el recorte por
    corte **no** hace fallar la variante `indices_`. Con ocho productos el índice de
    categoría sobrevive a los tres cortes y la comparación es real.
    """
    meses = pd.date_range("2024-01-01", periods=24, freq="MS")
    filas = [
        {
            "id_producto": p,
            "anio_mes": m,
            "unidades": float(10 + i),
            "revenue": float((10 + i) * (100 + 5 * i) * p),
            "precio_prom": float((100 + 5 * i) * p),
        }
        for p in range(1, 9)
        for i, m in enumerate(meses)
        if not (p == 8 and i >= 10)
    ]
    return pd.DataFrame(filas)


@pytest.fixture
def catalogo():
    """Todos en la misma categoría y laboratorio, para que la corrida pase por los
    peldaños de la cascada y no solo por el ancla propia."""
    return pd.DataFrame(
        {
            "id_producto": list(range(1, 9)),
            "categoria": ["CLINICO"] * 8,
            "laboratorio": ["L1"] * 8,
        }
    )


@pytest.mark.parametrize("salida", ["ancla_", "indices_", "deflactor_"])
def test_el_transformador_de_m2_1_no_filtra_futuro(datos_con_nivel, cortes, catalogo, salida):
    """Las tres salidas se verifican por separado.

    No alcanza con el ancla: el índice encadenado es donde vive la trampa más sutil
    —normalizar la base en el último mes haría que todo el pasado se recalcule con cada
    corte— y el deflactor es el que efectivamente multiplica los montos.
    """
    from motor.deflacion import TransformadorDeflacion

    verificar_sin_leakage(
        lambda d, c: getattr(
            TransformadorDeflacion(catalogo=catalogo).ajustar(d, c), salida
        ),
        datos=datos_con_nivel,
        cortes=cortes,
    )


def test_la_verificacion_de_arriba_ejercita_el_fallback_y_el_indice_de_nivel(
    datos_con_nivel, cortes, catalogo
):
    """Comprueba que el test anterior tenga de qué agarrarse.

    Dos formas de que aquella verificación pase sin probar nada: que todos los productos
    resuelvan por ancla directa —y entonces la rama del fallback, la que el docstring de
    `leakage.py` señala como el caso realista, no se corra nunca— o que el índice de
    categoría esté vacío y comparar `indices_` sea comparar el IPC contra sí mismo.
    """
    from motor.deflacion import TransformadorDeflacion

    ajustado = TransformadorDeflacion(catalogo=catalogo).ajustar(datos_con_nivel, cortes[-1])

    assert ajustado.origen_ancla_[8] not in ("producto", "sin_ancla"), "el 8 usa el fallback"

    indice_categoria = ajustado.indices_[ajustado.indices_["nivel"] == "categoria"]
    assert indice_categoria["anio_mes"].max() == cortes[-1], (
        "el indice de categoria tiene que llegar hasta el corte, no morirse antes"
    )
