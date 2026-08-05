"""Features del modelo global (M2.2).

Dos mitades con dueños distintos, a propósito:

- **`especificacion`** — qué lags, medias móviles y features de calendario se usan. Los
  ejecuta `mlforecast` en M2.3; acá solo se declaran.
- **`construccion`** — lo que `mlforecast` no sabe hacer: las features derivadas de la
  deflación de ADR-002. Es lo único que tiene que pasar por la red anti-leakage de M1.3,
  que es el gate de salida de esta unidad.

Ver `README.md` para por qué "el precio deflactado" no es una de ellas.
"""

from motor.features.construccion import (
    COLUMNAS_CLAVE,
    COLUMNAS_FEATURES,
    cobertura_de_features,
    construir_features,
)
from motor.features.especificacion import (
    COLUMNAS_CATALOGO,
    COLUMNAS_PRECIO,
    DATE_FEATURES,
    LAG_TRANSFORMS,
    LAGS,
    STATIC_FEATURES,
    VENTANAS_MEDIA_MOVIL,
)
from motor.features.precio import precio_relativo_al_nivel

__all__ = [
    "COLUMNAS_CATALOGO",
    "COLUMNAS_CLAVE",
    "COLUMNAS_FEATURES",
    "COLUMNAS_PRECIO",
    "DATE_FEATURES",
    "LAGS",
    "LAG_TRANSFORMS",
    "STATIC_FEATURES",
    "VENTANAS_MEDIA_MOVIL",
    "cobertura_de_features",
    "construir_features",
    "precio_relativo_al_nivel",
]
