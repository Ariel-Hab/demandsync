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

# Umbrales Syntetos-Boylan (mismo criterio que motor/eda/eda-2026-07-15.md §3)
ADI_UMBRAL = 1.32
CV2_UMBRAL = 0.49

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

CATEGORIAS = [
    "antiparasitarios", "antibioticos", "vacunas", "suplementos",
    "analgesicos", "dermatologicos", "reproductivos", "alimentos_balanceados",
]
LABORATORIOS = [f"laboratorio_{i:02d}" for i in range(1, 21)]
