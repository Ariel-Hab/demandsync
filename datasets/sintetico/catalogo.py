"""Catálogo sintético: productos (con arquetipo Syntetos-Boylan asignado) y clientes."""

import numpy as np
import pandas as pd

from . import parametros as P


def generar_productos(rng: np.random.Generator, n_productos: int = P.N_PRODUCTOS) -> pd.DataFrame:
    arquetipos = list(P.PROPORCION_ARQUETIPOS.keys())
    probs = np.array(list(P.PROPORCION_ARQUETIPOS.values()))
    probs = probs / probs.sum()  # evita drift de punto flotante (numpy exige suma == 1)

    arquetipo = rng.choice(arquetipos, size=n_productos, p=probs)
    categoria = rng.choice(P.CATEGORIAS, size=n_productos)
    laboratorio = rng.choice(P.LABORATORIOS, size=n_productos)

    # Escala base (unidades/mes cuando el producto vende) — cola larga, como el catálogo real.
    tamanio_base = rng.lognormal(mean=np.log(15), sigma=1.0, size=n_productos)
    tamanio_base = np.clip(tamanio_base, 1.0, 800.0)

    # Precio base "real" (antes de inflación) — también con cola larga.
    precio_base = rng.lognormal(mean=np.log(300), sigma=0.8, size=n_productos)
    precio_base = np.clip(precio_base, 20.0, 20000.0)

    # 25,4% sin ancla propia (EDA §4): sesgado hacia arquetipos de menor ocurrencia.
    peso_sin_ancla = np.where(np.isin(arquetipo, ["intermitente", "lumpy"]), 3.0, 1.0)
    sin_ancla = np.zeros(n_productos, dtype=bool)
    n_sin_ancla = round(n_productos * P.PORCENTAJE_SIN_ANCLA_PROPIA)
    idx_sin_ancla = rng.choice(
        n_productos, size=n_sin_ancla, replace=False, p=peso_sin_ancla / peso_sin_ancla.sum()
    )
    sin_ancla[idx_sin_ancla] = True

    return pd.DataFrame(
        {
            "id_producto": np.arange(1, n_productos + 1),
            "categoria": categoria,
            "laboratorio": laboratorio,
            "arquetipo": arquetipo,
            "tamanio_base": tamanio_base,
            "precio_base": precio_base,
            "sin_ancla_propia": sin_ancla,
        }
    )


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
