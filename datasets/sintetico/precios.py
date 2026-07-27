"""Trayectoria de inflación nominal + descuento por cliente.

El target del motor es unidades (ADR-007), no pesos — la inflación acá solo tiene que
ser lo bastante realista como para ejercitar la deflación (M2) más adelante; no hace
falta reproducir la serie histórica real de Argentina mes a mes.
"""

import numpy as np


def indice_inflacion(rng: np.random.Generator, n_meses: int) -> np.ndarray:
    """Índice acumulado de inflación mensual (índice[0] = 1 + primera tasa)."""
    tasa_mensual = rng.uniform(0.02, 0.09, size=n_meses)
    return np.cumprod(1 + tasa_mensual)
