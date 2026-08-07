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

import operator

from mlforecast.lag_transforms import Combine, RollingMean, RollingStd

LAGS = [1, 2, 3, 6, 12]
"""Lags del target (`unidades`), de `plan-diseno.md` §M2.

El 12 es el que captura la estacionalidad anual —el mismo mes del año anterior— y por eso
`mismo_mes_año_anterior` sería una columna repetida.
"""

VENTANAS_MEDIA_MOVIL = [3, 6, 12]
"""Ventanas de las medias móviles, de `plan-diseno.md` §M2."""

def armar_lag_transforms(usar_dispersion: bool = False) -> dict:
    """Transformaciones sobre el lag 1. Con `usar_dispersion`, agrega desvío y CV (M3.0).

    La clave del dict es **el lag sobre el que se aplica la transformación**, no la ventana:
    `{1: [RollingMean(3)]}` es la media de los 3 meses que terminan en t−1. Sobre el lag 1
    —y no sobre el 0— porque en el origen `t` el valor de `t` todavía no se conoce; es
    `mlforecast` quien garantiza ese desfasaje, y es la razón de delegarle esto.

    **Por qué existe el interruptor (M3.0, `roadmap-motor.md` §6.10).** Hasta M2 la
    especificación no tenía **ninguna** medida de dispersión: solo medias móviles. Y los
    cuadrantes de `motor.clasificacion` se separan por dos ejes — ADI (cada cuánto vende) y
    **CV² (cuánto varía cuando vende)**. El ADI el modelo lo ve, porque una serie salteada
    tiene ceros en sus lags; el CV² **no lo ve por ningún lado**. Consecuencia medida en
    M2.4: a `erratica` —que se diferencia de `suave` *solo* por el CV²— le da la misma
    anchura relativa de intervalo que a `suave`, y por eso sub-cubre 10 a 13 puntos.

    Se construyen instancias nuevas en cada llamada a propósito: los objetos de
    `mlforecast` llevan estado interno al transformar, y compartir una instancia entre dos
    `MLForecast` distintos es pedir un bug que no falla, solo devuelve otro número.

    **`0/0` en el CV da `NaN`, no `inf`** — verificado sobre una serie intermitente. Es lo
    que se quiere: LightGBM le da una rama propia al nulo, y "la ventana estuvo dormida" es
    justamente información sobre el régimen de la serie. Un `inf` en cambio envenenaría los
    cortes del árbol.
    """
    transformaciones = [RollingMean(window_size=v) for v in VENTANAS_MEDIA_MOVIL]
    if usar_dispersion:
        for ventana in VENTANAS_DISPERSION:
            transformaciones.append(RollingStd(window_size=ventana))
            transformaciones.append(
                Combine(
                    RollingStd(window_size=ventana),
                    RollingMean(window_size=ventana),
                    operator.truediv,
                )
            )
    return {1: transformaciones}


VENTANAS_DISPERSION = [3, 6, 12]
"""Ventanas del desvío móvil y del CV (M3.0). Las mismas que las medias móviles: el CV es
`std/mean` sobre la **misma** ventana, y usar ventanas distintas daría un cociente entre
dos cosas que no se corresponden."""

LAG_TRANSFORMS = armar_lag_transforms()
"""El juego de M2: solo medias móviles. Es el que reproducen las tablas congeladas de
`motor/backtests/` hasta M2.5 inclusive, así que **no cambia** — la dispersión entra por el
interruptor y no por acá."""

DATE_FEATURES = ["month"]
"""Mes del año. `mlforecast` lo deriva del índice temporal, así que no necesita datos."""

STATIC_FEATURES = ["categoria", "laboratorio", "precio_ancla"]
"""Columnas **constantes por serie dentro de un corte**.

`precio_ancla` es estática a propósito: es la escala de precio del producto, lo que separa
una jeringa de $20 de una vacuna de $20.000. Su falta de variación temporal no es un
defecto — la señal temporal de precio la llevan las columnas de `motor.features.precio`.

⚠️ **Esta lista describe la naturaleza de las columnas, no lo que M2.3 le pasa a
`fit(static_features=...)`.** Las dos listas coincidían hasta que M2.3 chocó con una
validación de `mlforecast`: compara el primer valor de la serie contra el último con `!=`, y
como **`NaN != NaN` es `True`**, un producto sin ancla —nulo en *todas* sus filas— aborta la
corrida entera diciendo que "cambia en el tiempo". Así que `precio_ancla` viaja por `X_df`
igual que las demás de precio. Ver `modelado/modelo_global.py::COLUMNAS_DINAMICAS`.
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
