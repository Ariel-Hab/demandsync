"""Parámetros del generador sintético — calibrados por motor/eda/eda-2026-07-15.md §8.

Cambiar un valor acá es cambiar la calibración del dataset: si un producto/cliente
más o el rango de un arquetipo se toca, hay que re-correr `generar_sintetico.py` y
revisar el manifiesto (el gate de S0 depende de que los cuadrantes sigan cayendo
dentro de ±3 puntos de los reales).
"""

from datetime import date

PRIMER_MES = date(2018, 7, 1)
N_MESES = 96  # 2018-07 .. 2026-06 (EDA §1)
VENTANA_INTERMITENCIA_MESES = 36  # últimos 36 meses para clasificación ADI/CV² (EDA §3)

N_PRODUCTOS = 2300  # EDA: ~2.200-2.400 productos con venta reciente
N_CLIENTES = 1600  # EDA: ~1.400-1.800 clientes activos

# Proporciones de cuadrante Syntetos-Boylan sobre productos con venta en la ventana (EDA §3)
PROPORCION_ARQUETIPOS = {
    "suave": 0.478,
    "intermitente": 0.309,
    "erratica": 0.101,
    "lumpy": 0.111,
}

# Los umbrales Syntetos-Boylan (ADI 1,32 / CV² 0,49) NO se definen acá: viven en
# `motor.clasificacion` y se importan desde `clasificacion.py`. Duplicarlos permitiría que
# el generador calibrara contra un criterio y el motor midiera contra otro, y el gate de
# calibración dejaría de significar algo.

TOLERANCIA_CALIBRACION_PUNTOS = 3.0  # gate de S0: ±3 puntos porcentuales
MAX_INTENTOS_CALIBRACION_PRODUCTO = 40  # rechazo/resorteo de parámetros por producto

# Probabilidad de ocurrencia mensual (Bernoulli) por arquetipo — controla el ADI esperado
RANGO_P_OCURRENCIA = {
    "suave": (0.85, 1.0),
    "intermitente": (0.25, 0.70),
    "erratica": (0.85, 1.0),
    "lumpy": (0.15, 0.65),
}

# Sigma lognormal del tamaño de demanda (meses con venta) — controla el CV²
RANGO_SIGMA_TAMANIO = {
    "suave": (0.15, 0.55),
    "intermitente": (0.15, 0.55),
    "erratica": (0.65, 1.30),
    "lumpy": (0.65, 1.30),
}

# Pool de clientes elegibles por producto — correlacionado con el arquetipo
# (un producto lumpy lo compran pocos clientes; uno suave, muchos)
RANGO_POOL_CLIENTES = {
    "suave": (60, 400),
    "intermitente": (15, 90),
    "erratica": (40, 220),
    "lumpy": (3, 30),
}

PORCENTAJE_SIN_ANCLA_PROPIA = 0.254  # EDA §4: sin venta en los últimos 3 meses
PORCENTAJE_NOTAS_CREDITO = 0.095  # EDA §1: ~9,5% de comprobantes con NC
MESES_SIN_ANCLA = 3

# ---------------------------------------------------------------------------
# T0.4 #3 — altas y bajas de producto
#
# Todo lo de acá está MEDIDO sobre el extract real (roadmap §12.1), no elegido.
# La única decisión de producto es el nivel de la tasa de baja; los ratios entre
# arquetipos son los medidos.
# ---------------------------------------------------------------------------

PORCENTAJE_PRESENTE_AL_INICIO = 0.481
"""Productos que ya vendían en el primer mes de la ventana. El 51,9% restante entra
después. Medido: 1.053 de 2.189."""

PROPORCION_ALTAS_TRAMO_RECIENTE = 0.381
"""De los productos que entran después del mes 0, la fracción que lo hace dentro de la
ventana de clasificación de 36 meses. Con el 51,9% de altas tardías da 19,8% del catálogo
con alta en la ventana, contra el 20,0% medido.

Es un reparto en dos tramos y no una tasa constante a propósito: las altas reales se
aceleran al final (2025 trajo 216 contra las ~100/año de 2020-2024)."""

TASA_BAJA_OBJETIVO = 0.05
"""Fracción del catálogo que muere a mitad de historia. **Decisión de producto**, no
medición: el valor medido con el criterio estricto es 5,8% (roadmap §12.1) y se redondeó
a 5%. La diferencia es inmaterial y queda anotada para que nadie la confunda con un dato."""

TASA_BAJA_POR_ARQUETIPO = {
    "suave": 0.0281,
    "erratica": 0.0468,
    "intermitente": 0.0995,
    "lumpy": 0.1370,
}
"""Probabilidad de que un producto muera, por arquetipo.

Los **ratios** son los medidos (`lumpy` 16,1% · `intermitente` 11,7% · `erratica` 5,5% ·
`suave` 3,3%, o sea lumpy muere 4,9× más que suave). El **nivel** está escalado por 0,851
sobre esos valores.

El escalado no es directo, y conviene entender por qué: estas son tasas de **asignación**,
mientras que `TASA_BAJA_OBJETIVO` se verifica con el criterio **estricto** de medición, que
no cuenta como baja a un producto cuyo silencio final no supera su propio hueco histórico.
Un `lumpy` que ya tenía huecos de 30 meses puede morir y no ser reconocible como muerto. Por
eso hace falta asignar ~6,4% para medir 5%: la brecha es real, no un error de calibración, y
existe igual en los datos reales. Si tocás `TASA_BAJA_OBJETIVO` o `PROPORCION_ARQUETIPOS`
hay que reescalar contra la salida, no contra la aritmética — el test del generador verifica
la tasa **medida**."""

MESES_MIN_VIDA = 6
"""Vida mínima de un producto que nace y muere dentro de la ventana. El percentil 10 de la
vida real es 7 meses, así que 6 no es un caso patológico: existe."""

MESES_MIN_SILENCIO_BAJA = 25
"""Una baja tiene que quedar en silencio más de 24 meses para contar como tal según el
criterio con que se midió el 5,8%. Fija el último mes en que un producto puede morir."""

# ---------------------------------------------------------------------------
# T0.4 #1 — cliente_feature versionada
# ---------------------------------------------------------------------------

PASO_MESES_CLIENTE_FEATURE = 3
"""Cada cuántos meses se emite una versión de `cliente_feature`. Con 96 meses da 32
versiones. Se eligió 3 y no 1 porque 32 versiones ya ejercitan el recorte anti-leakage del
arnés (`tablas_auxiliares`), y 96 multiplican por tres el costo de generación sin agregar
nada que el motor pueda distinguir."""

# ---------------------------------------------------------------------------
# T0.4 #2 — meses con neto negativo o cero
# ---------------------------------------------------------------------------

PORCENTAJE_MESES_NETO_NEGATIVO = 0.00205
"""Filas producto-mes que cierran con unidades netas negativas. Medido: 281 de 137.399.
Son devoluciones que caen en un mes sin ventas de ese producto que las compensen."""

PORCENTAJE_MESES_NETO_CERO = 0.0353
"""Filas producto-mes con neto exactamente cero. Medido: 4.848 de 137.399. Importan porque
dejan `precio_prom` indefinido — es el insumo degenerado de la deflación de M2.1."""

PORCENTAJE_MESES_PRECIO_CRUZADO = 0.00016
"""Filas donde unidades y revenue netean con **signos distintos**, o sea precio implícito
negativo. Medido: 22 de 137.399 (roadmap §5.5 #6). Pasa cuando la nota de crédito lleva un
precio distinto del de la venta. Es el caso que el clamp de ratios de M2.1 tiene que
sobrevivir, y sin sembrarlo acá el sintético no lo produce nunca."""

# ---------------------------------------------------------------------------
# T0.4 #4 — categorías reales
# ---------------------------------------------------------------------------

CATEGORIAS_CONTEO = {
    "CLINICO": 723,
    "SIN CATEGORIA": 491,
    "ANTIPARASITARIO EXTERNO": 359,
    "HIGIENE Y BELLEZA": 213,
    "ANTIPARASITARIO INTERNO": 136,
    "CARDIOLOGICO": 63,
    "DESCARTABLES": 51,
    "ALIMENTO": 46,
    "BIOLOGICO": 44,
    "ANTIARTROSICO": 43,
    "ACCESORIO": 19,
    "HIGIENE Y BELLEZA (odontologico)": 1,
}
"""Las 12 categorías reales con su conteo de productos, medidos sobre el extract (§5.5).

Se guardan los **conteos** y no las probabilidades para que el origen quede a la vista y
recalibrar sea reemplazar una tabla, no recalcular decimales a mano.

Antes acá había ocho nombres inventados (`antiparasitarios`, `vacunas`, …) repartidos
uniforme. Dos cosas que esa versión no podía producir y esta sí: un bucket `SIN CATEGORIA`
del 22,4% —que no es un error de datos, es que un quinto del catálogo no tiene etiqueta— y
una categoría con **un solo producto**, que es el caso borde que va a encontrar el
encoding de features de M2.2."""

CATEGORIAS = tuple(CATEGORIAS_CONTEO)
LABORATORIOS = [f"laboratorio_{i:02d}" for i in range(1, 21)]

TOLERANCIA_CATEGORIAS_PUNTOS = 3.0
"""Gate de T0.4: desvío máximo, en puntos porcentuales, entre la distribución lograda de
categorías y `CATEGORIAS_CONTEO`. Mismo criterio que el gate de cuadrantes."""
