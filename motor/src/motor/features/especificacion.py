"""Qué features de serie temporal se construyen — la **especificación**, no la ejecución.

`mlforecast` ya sabe armar lags, medias móviles y features de calendario sin leakage, y
M2.3 lo va a usar igual para el multi-horizonte directo. Reimplementar esa maquinaria acá
sería duplicar código que después hay que mantener sincronizado con el que efectivamente
corre. Así que M2.2 se queda con la **especificación** —qué lags, qué ventanas— y M2.3 se
la pasa a `MLForecast` tal cual:

```python
MLForecast(
    models=[...],
    freq="MS",
    lags=LAGS,
    lag_transforms=LAG_TRANSFORMS,
    date_features=DATE_FEATURES,
).fit(df, static_features=STATIC_FEATURES, max_horizon=12)
```

Lo que `mlforecast` **no** sabe hacer —las features derivadas de la deflación de ADR-002—
lo construye `motor.features.construccion`, y es lo único que necesita pasar por la red
anti-leakage de M1.3.

**`mismo_mes_año_anterior` no está, y no es un olvido:** a grano mensual es exactamente
`lag 12`, que ya está en `LAGS`. La lista de `plan-diseno.md` §M2 lo nombraba aparte.
"""

from mlforecast.lag_transforms import RollingMean

LAGS = [1, 2, 3, 6, 12]
"""Lags del target (`unidades`), de `plan-diseno.md` §M2.

El 12 es el que captura la estacionalidad anual —el mismo mes del año anterior— y por eso
`mismo_mes_año_anterior` sería una columna repetida.
"""

VENTANAS_MEDIA_MOVIL = [3, 6, 12]
"""Ventanas de las medias móviles, de `plan-diseno.md` §M2."""

LAG_TRANSFORMS = {1: [RollingMean(window_size=v) for v in VENTANAS_MEDIA_MOVIL]}
"""Medias móviles sobre el lag 1.

La clave del dict es **el lag sobre el que se aplica la transformación**, no la ventana:
`{1: [RollingMean(3)]}` es la media de los 3 meses que terminan en t−1. Sobre el lag 1
—y no sobre el 0— porque en el origen `t` el valor de `t` todavía no se conoce; es
`mlforecast` quien garantiza ese desfasaje, y es la razón de delegarle esto.
"""

DATE_FEATURES = ["month"]
"""Mes del año. `mlforecast` lo deriva del índice temporal, así que no necesita datos."""

STATIC_FEATURES = ["categoria", "laboratorio", "precio_ancla"]
"""Columnas constantes por serie dentro de un corte, que van en `fit(static_features=...)`.

`precio_ancla` es estática **a propósito**: es la escala de precio del producto, lo que
separa una jeringa de $20 de una vacuna de $20.000. Su falta de variación temporal no es
un defecto — la señal temporal de precio la llevan las columnas de
`motor.features.precio`, que son otras (ver el README de este paquete).
"""

COLUMNAS_PRECIO = [
    "precio_ancla",
    "precio_rel_nivel",
    "var_precio_rel_3m",
    "var_precio_rel_12m",
]
"""Lo que produce `construir_features` a partir de la deflación (ADR-002)."""

COLUMNAS_CATALOGO = ["categoria", "laboratorio"]
"""Atributos de producto que salen de `catalogo_producto`."""
