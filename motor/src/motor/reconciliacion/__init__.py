"""Reconciliación jerárquica de pronósticos (M3.1, `roadmap-motor.md` §7.2).

Dos piezas:

- `estructura` — construye la **estructura agrupada** `total → {categoría, laboratorio} →
  producto` y su matriz `S`, con las validaciones que hacen que un error de armado corte en
  vez de producir números plausibles.
- `reconciliar` — aplica bottom-up y las variantes de MinT sobre pronósticos base, con la
  covarianza estimada **prospectivamente** (ADR-016).

**Por qué agrupada y no jerárquica:** 47 de 77 laboratorios venden en más de una categoría y
cubren el 89% de los productos, así que `laboratorio` no está anidado en `categoria` (§7.2).
"""

from .estructura import (
    ESPECIFICACION,
    NIVELES,
    Estructura,
    construir_estructura,
    verificar_coherencia,
)
from .reconciliar import METODOS, reconciliar

__all__ = [
    "ESPECIFICACION",
    "METODOS",
    "NIVELES",
    "Estructura",
    "construir_estructura",
    "reconciliar",
    "verificar_coherencia",
]
