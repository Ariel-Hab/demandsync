"""Adaptador del clasificador Syntetos-Boylan del motor, para el gate del generador.

**El clasificador vive en el motor** (`motor.clasificacion`), no acá. Antes era al revés
y estaba mal por dos motivos: el motor es código de producción y no puede depender de una
herramienta de desarrollo, y de hecho no podía —`datasets/` no es un paquete instalable,
así que el import fallaba con `ModuleNotFoundError` (M1.4 del roadmap del motor).

Que el generador use **el mismo código** que el motor no es una comodidad: es lo que hace
que el gate de calibración signifique algo. Si el generador midiera su intermitencia con
una implementación propia, podría cumplir su gate y producir un dataset que el motor
clasifica distinto — y todo lo que M1 mida por cuadrante estaría contra un mundo que no
existe.

Lo único propio de acá es `desvios_vs_objetivo`: comparar contra `PROPORCION_ARQUETIPOS`
es calibración del generador, no dominio del motor.
"""

from motor.clasificacion import (
    ADI_UMBRAL,
    CV2_UMBRAL,
    SIN_ACTIVIDAD,
    clasificar_serie,
    clasificar_series,
    distribucion_cuadrantes,
)

from . import parametros as P

__all__ = [
    "ADI_UMBRAL",
    "CV2_UMBRAL",
    "SIN_ACTIVIDAD",
    "clasificar_productos",
    "clasificar_serie",
    "clasificar_series",
    "desvios_vs_objetivo",
    "distribucion_cuadrantes",
]


def clasificar_productos(
    hecho_producto, ventana_meses: int = P.VENTANA_INTERMITENCIA_MESES
):
    """`clasificar_series` del motor, con la ventana del generador. Se conserva el nombre
    porque es el que usa el manifiesto."""
    return clasificar_series(hecho_producto, ventana_meses=ventana_meses)


def desvios_vs_objetivo(distribucion: dict) -> dict:
    """Diferencia en puntos porcentuales contra `PROPORCION_ARQUETIPOS` (gate de ±3 pts).

    Es lo único que no se comparte con el motor: el objetivo es la distribución que midió
    el EDA sobre datos reales, y solo tiene sentido como criterio de calibración del
    generador.
    """
    objetivo = {k: v * 100 for k, v in P.PROPORCION_ARQUETIPOS.items()}
    return {
        cuadrante: round(distribucion.get(cuadrante, 0.0) - objetivo_pct, 2)
        for cuadrante, objetivo_pct in objetivo.items()
    }
