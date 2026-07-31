"""Catálogo sintético: productos (con arquetipo Syntetos-Boylan asignado) y clientes."""

import numpy as np
import pandas as pd

from . import parametros as P


def generar_productos(rng: np.random.Generator, n_productos: int = P.N_PRODUCTOS) -> pd.DataFrame:
    arquetipos = list(P.PROPORCION_ARQUETIPOS.keys())
    probs = np.array(list(P.PROPORCION_ARQUETIPOS.values()))
    probs = probs / probs.sum()  # evita drift de punto flotante (numpy exige suma == 1)

    arquetipo = rng.choice(arquetipos, size=n_productos, p=probs)

    # Categorías con las proporciones reales, no uniforme (T0.4 #4). Con `p=` uniforme el
    # dataset daba ~287 productos por categoría; la realidad va de 723 (`CLINICO`) a 1
    # (`HIGIENE Y BELLEZA (odontologico)`), y eso es lo que va a ver el encoding de M2.2.
    conteos = np.array(list(P.CATEGORIAS_CONTEO.values()), dtype="float64")
    categoria = rng.choice(P.CATEGORIAS, size=n_productos, p=conteos / conteos.sum())
    categoria = _garantizar_todas_las_categorias(rng, categoria)

    laboratorio = rng.choice(P.LABORATORIOS, size=n_productos)

    # Escala base (unidades/mes cuando el producto vende) — cola larga, como el catálogo real.
    tamanio_base = rng.lognormal(mean=np.log(15), sigma=1.0, size=n_productos)
    tamanio_base = np.clip(tamanio_base, 1.0, 800.0)

    # Precio base "real" (antes de inflación) — también con cola larga.
    precio_base = rng.lognormal(mean=np.log(300), sigma=0.8, size=n_productos)
    precio_base = np.clip(precio_base, 20.0, 20000.0)

    mes_alta = _sortear_altas(rng, n_productos)
    mes_baja = _sortear_bajas(rng, arquetipo, mes_alta)

    # 25,4% sin ancla propia (EDA §4): sesgado hacia arquetipos de menor ocurrencia.
    #
    # Las bajas YA no tienen venta reciente, así que acá solo se completa el resto. Sumar
    # un 25,4% independiente encima del 5% de bajas daría 31% y rompería la calibración de
    # EDA §4 — el mismo dato, contado dos veces por dos mecanismos distintos.
    murio = mes_baja < P.N_MESES
    n_objetivo = round(n_productos * P.PORCENTAJE_SIN_ANCLA_PROPIA)
    n_faltan = max(0, n_objetivo - int(murio.sum()))

    sin_ancla = np.zeros(n_productos, dtype=bool)
    candidatos = np.flatnonzero(~murio)
    if n_faltan and len(candidatos):
        peso = np.where(np.isin(arquetipo[candidatos], ["intermitente", "lumpy"]), 3.0, 1.0)
        elegidos = rng.choice(
            candidatos, size=min(n_faltan, len(candidatos)), replace=False, p=peso / peso.sum()
        )
        sin_ancla[elegidos] = True

    return pd.DataFrame(
        {
            "id_producto": np.arange(1, n_productos + 1),
            "categoria": categoria,
            "laboratorio": laboratorio,
            "arquetipo": arquetipo,
            "tamanio_base": tamanio_base,
            "precio_base": precio_base,
            "sin_ancla_propia": sin_ancla,
            "mes_alta": mes_alta,
            "mes_baja": mes_baja,
        }
    )


def _garantizar_todas_las_categorias(
    rng: np.random.Generator, categoria: np.ndarray
) -> np.ndarray:
    """Fuerza que las 12 categorías tengan al menos un producto.

    `HIGIENE Y BELLEZA (odontologico)` tiene un solo producto en el catálogo real, o sea
    0,05%: con 2.300 productos el sorteo la deja vacía una de cada tres semillas. Y esa
    categoría **es el motivo de incluir la lista completa** — el caso borde de una
    categoría con un único producto es exactamente lo que tiene que ejercitar el encoding
    de features de M2.2. Una deuda que se arregla solo en dos de cada tres semillas no está
    arreglada.

    Se roba el producto a una categoría con más de uno, así que arreglar la cola no puede
    vaciar otra.
    """
    if len(categoria) < len(P.CATEGORIAS):
        return categoria

    for faltante in [c for c in P.CATEGORIAS if c not in set(categoria)]:
        valores, cuentas = np.unique(categoria, return_counts=True)
        donantes = np.flatnonzero(np.isin(categoria, valores[cuentas > 1]))
        categoria[rng.choice(donantes)] = faltante
    return categoria


def _sortear_altas(rng: np.random.Generator, n_productos: int) -> np.ndarray:
    """Mes de la primera venta posible de cada producto (0 = ya vendía en el mes 1).

    Dos tramos y no una tasa constante porque las altas reales se aceleran al final: 2025
    trajo 216 contra las ~100/año de 2020-2024 (T0.4 #3).
    """
    mes_alta = np.zeros(n_productos, dtype="int64")
    tardios = np.flatnonzero(rng.random(n_productos) >= P.PORCENTAJE_PRESENTE_AL_INICIO)
    if not len(tardios):
        return mes_alta

    inicio_ventana = P.N_MESES - P.VENTANA_INTERMITENCIA_MESES
    reciente = rng.random(len(tardios)) < P.PROPORCION_ALTAS_TRAMO_RECIENTE
    mes_alta[tardios[reciente]] = rng.integers(
        inicio_ventana, P.N_MESES, size=int(reciente.sum())
    )
    mes_alta[tardios[~reciente]] = rng.integers(
        1, inicio_ventana, size=int((~reciente).sum())
    )
    return mes_alta


def _sortear_bajas(
    rng: np.random.Generator, arquetipo: np.ndarray, mes_alta: np.ndarray
) -> np.ndarray:
    """Primer mes SIN ventas de cada producto; `N_MESES` si nunca muere.

    La probabilidad depende del arquetipo: medido sobre datos reales, `lumpy` muere 4,9×
    más que `suave` (T0.4 #3). Un producto solo puede morir si le queda margen para vivir
    `MESES_MIN_VIDA` y después quedar en silencio `MESES_MIN_SILENCIO_BAJA` — si no, la
    baja no sería distinguible de un hueco y no contaría como tal con el criterio con que
    se midió la tasa.
    """
    n = len(arquetipo)
    mes_baja = np.full(n, P.N_MESES, dtype="int64")

    ultimo_mes_posible = P.N_MESES - P.MESES_MIN_SILENCIO_BAJA
    primer_mes_posible = mes_alta + P.MESES_MIN_VIDA
    elegible = primer_mes_posible <= ultimo_mes_posible

    tasas = np.array([P.TASA_BAJA_POR_ARQUETIPO[a] for a in arquetipo])
    muere = elegible & (rng.random(n) < tasas)

    for i in np.flatnonzero(muere):
        mes_baja[i] = rng.integers(primer_mes_posible[i], ultimo_mes_posible + 1)
    return mes_baja


def generar_clientes(rng: np.random.Generator, n_clientes: int = P.N_CLIENTES) -> pd.DataFrame:
    # Peso relativo del cliente (tamaño de compra) — cola larga, igual que el padrón real.
    peso = rng.lognormal(mean=0.0, sigma=1.0, size=n_clientes)
    descuento = rng.uniform(0.0, 0.18, size=n_clientes)  # descuento individual (ADR-002)

    return pd.DataFrame(
        {
            "id_cliente": np.arange(1, n_clientes + 1),
            "peso": peso,
            "descuento": descuento,
        }
    )
