"""Modelo global LightGBM con `mlforecast` (M2.3) — multi-horizonte **directo**, con
intervalos por regresión cuantílica (M2.4).

Global (`plan-diseno.md` decisión 2): **un solo modelo para todas las series**, que aprende
de todo el catálogo a la vez (cross-learning) en vez de ajustar uno por producto. Es lo que
le permite predecir una serie corta apoyándose en las demás de su categoría — justamente el
hueco que los baselines no pueden cubrir (§5.6.2: 12.700 filas de arranque en frío).

**Directo y no recursivo:** un modelo por horizonte (`max_horizon`), en vez de uno que se
realimenta con sus propias predicciones. No acumula error encadenado y permite que cada
horizonte aprenda su propia relación. Cuesta más entrenamientos, que a esta escala es
trivial.

## Cómo se acopla con el resto

Conforma el contrato `PredictorFn` de `motor.backtesting.arnes` en su forma de **4
argumentos**: necesita el catálogo además de la serie, así que se corre con
`tablas_auxiliares={"catalogo": catalogo_producto}` y el arnés se lo pasa recortado al corte
(el catálogo no tiene columna de fecha, así que va entero).

Las features salen de M2.2: la **especificación** de lags/rollings/calendario la ejecuta
`mlforecast` (`features/especificacion.py`), y las derivadas de la deflación las construye
`features/construccion.py`. Acá no se reimplementa ninguna de las dos.

## Tres hechos de `mlforecast 0.15.1` que decidieron la forma

Ninguno está así en la documentación; salen de leer el código instalado y de correrlo.

1. **Con `max_horizon`, las features se calculan UNA sola vez, en el origen**
   (`core.py::TimeSeries._predict_multi`): se arma un vector de features y se le aplican los
   `h` modelos. Coincide exactamente con la forma del panel de M2.2 — una fila por origen de
   pronóstico, features del origen, target en `origen+h`.
2. **`_fit` rechaza una `static_feature` cuyo valor cambie en el tiempo.** Compara el valor
   al inicio y al final de cada serie y tira `ValueError`. Por eso `precio_rel_nivel` **no
   puede** ir en `static_features` aunque sea la feature de precio más informativa. Y por
   una razón más fina —la comparación es `!=`, y `NaN != NaN` es `True`— **`precio_ancla`
   tampoco**, aunque conceptualmente sí sea estática: ver `COLUMNAS_DINAMICAS`.
3. **Lo que no se declara estático es exógena dinámica y exige `X_df` al predecir**, del que
   `_get_features_for_next_step` toma **la primera fila futura de cada serie**.

De ahí la decisión de diseño de este módulo, que es la que hay que entender antes de
tocarlo:

> **`X_df` lleva las features de precio congeladas en su valor del corte**, repetidas para
> los `h` meses futuros.

Es lo honesto —el precio de `corte+h` no se conoce y no se va a inventar— y además lo
**alineado**: en entrenamiento la fila del origen `t` lleva el precio de `t`, así que en
predicción tiene que llevar el del corte, no el de `corte+1`. Lo fija
`test_el_x_df_lleva_el_precio_del_corte_y_no_el_del_mes_siguiente`, porque una versión nueva
de `mlforecast` que mueva ese índice desalinea el modelo **sin fallar**.
"""

from collections.abc import Sequence

import lightgbm as lgb
import numpy as np
import pandas as pd
from mlforecast import MLForecast
from mlforecast.target_transforms import LocalStandardScaler

from motor.features.construccion import construir_features
from motor.features.especificacion import (
    COLUMNAS_CATALOGO,
    COLUMNAS_PRECIO,
    DATE_FEATURES,
    LAG_TRANSFORMS,
    LAGS,
)

NOMBRE_MODELO = "GlobalLGBM"
"""Nombre de la columna de predicción. Es el que va a competir contra los 7 candidatos de
`modelado.seleccion`, así que no puede chocar con ninguno."""

HIPERPARAMETROS = {
    "n_estimators": 200,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_child_samples": 20,
    "verbose": -1,
}
"""**No están tuneados, y es deliberado.** El gate de M2.3 es que el modelo corra dentro del
arnés y sea comparable con el piso, no que gane (eso es M2.5). Tunear con el resultado a la
vista es elegir la vara según el resultado — el mismo argumento por el que ADR-015 se decidió
antes de M2.3. Si M2.5 muestra que vale la pena, el tuning entra como unidad propia con su
gate."""

CUANTILES_ESTANDAR = (0.1, 0.5, 0.9)
"""Los cuantiles de M2.4 (`plan-diseno.md` §M2). El **P10–P90** es el intervalo que ADR-015
punto 2 convierte en el entregable del producto para h=6/h=12, y su cobertura nominal es del
**80%**: la empírica es lo que mide `motor.backtesting.intervalos`."""


def nombre_de_cuantil(cuantil: float) -> str:
    """`0.1` → `GlobalLGBM_P10`. Una sola función para que el nombre de columna no se
    escriba a mano en el predictor, en las métricas y en el script — tres lugares donde un
    typo no falla, solo deja la tabla sin la columna que se creía estar midiendo."""
    return f"{NOMBRE_MODELO}_P{round(cuantil * 100):02d}"


def _armar_modelos(
    cuantiles: Sequence[float] | None, hiperparametros: dict
) -> dict[str, lgb.LGBMRegressor]:
    """El modelo de media más un modelo por cuantil, todos con las mismas features.

    **La columna de media (`GlobalLGBM`) no cambia por agregar cuantiles**, y eso es
    condición de la unidad: es el pronóstico puntual que M2.3 midió contra el piso y con el
    que M2.5 va a comparar. Los cuantiles se suman al mismo `MLForecast`, que ajusta cada
    modelo por separado sobre la misma matriz — lo fija
    `test_los_cuantiles_no_mueven_el_pronostico_puntual`.

    Cada cuantil es un LightGBM con **pinball loss** (`objective="quantile"`), que es
    asimétrica: con `alpha=0.9` quedarse corto cuesta 9 veces más que pasarse, así que el
    modelo se acomoda en el nivel que la demanda solo supera 1 de cada 10 veces. No es un
    post-proceso del punto: son modelos distintos con la misma entrada.
    """
    modelos = {NOMBRE_MODELO: lgb.LGBMRegressor(**hiperparametros)}
    for cuantil in cuantiles or ():
        if not 0.0 < cuantil < 1.0:
            raise ValueError(f"cuantil fuera de (0, 1): {cuantil}")
        modelos[nombre_de_cuantil(cuantil)] = lgb.LGBMRegressor(
            objective="quantile", alpha=cuantil, **hiperparametros
        )
    return modelos

COLUMNAS_DINAMICAS = list(COLUMNAS_PRECIO)
"""**Todas** las features de precio viajan por `X_df`, incluida `precio_ancla`.

Que `precio_ancla` esté acá y no en `static_features` es contraintuitivo —conceptualmente
*es* estática, y así la declara M2.2— pero es forzado por `mlforecast`, y el motivo importa:

`_fit` valida que una `static_feature` no cambie en el tiempo comparando el valor al inicio
y al final de cada serie. La comparación es `!=`, y **`NaN != NaN` es `True`**, así que un
producto **sin ancla** —que tiene `NaN` en *todas* sus filas, o sea que justamente no
cambia— hace abortar la corrida entera con "its values change over time".

No es hipotético: medido sobre el sintético estratificado, **1 o 2 productos por corte** no
tienen ancla (sin precio propio utilizable ni fallback de nivel). Alcanza uno para tirar
abajo las 18 corridas.

La alternativa era imputar el ancla faltante, y va contra la regla que M2.1/M2.2 vienen
sosteniendo: los nulos se dejan en nulo y se reportan, porque imputar esconde la cobertura.
Por `X_df` el `NaN` llega intacto a LightGBM, que lo trata como *missing* nativo."""

ESTATICAS = list(COLUMNAS_CATALOGO)
"""Lo que sí puede ir en `static_features`: las categóricas, que nunca quedan nulas porque
`_preparar_categoricas` les pone `SIN DATO`. Un `"SIN DATO" != "SIN DATO"` es `False`, así
que pasan la validación."""


def _preparar_categoricas(datos: pd.DataFrame) -> pd.DataFrame:
    """`categoria` y `laboratorio` a dtype `category`, que es como LightGBM las trata sin
    inventar un orden.

    Como `object`, LightGBM las rechaza; codificadas a entero, les impone un orden que no
    tienen (`ALIMENTO` < `BIOLOGICO` no significa nada). Los nulos se dejan como categoría
    propia: `SIN CATEGORIA` es un valor real del catálogo —221 productos— y un producto sin
    laboratorio también informa.
    """
    datos = datos.copy()
    for columna in COLUMNAS_CATALOGO:
        if columna in datos.columns:
            datos[columna] = datos[columna].astype("string").fillna("SIN DATO").astype("category")
    return datos


def _armar_entrenamiento(
    historia: pd.DataFrame,
    corte: pd.Timestamp,
    catalogo: pd.DataFrame | None,
    usar_precio: bool,
    columna_id: str,
    columna_fecha: str,
    columna_objetivo: str,
) -> tuple[pd.DataFrame, list[str]]:
    """Panel de entrenamiento: la serie más las features de M2.2, a grano origen-de-pronóstico."""
    features = construir_features(historia, corte, catalogo=catalogo)
    columnas = [columna_id, columna_fecha, *ESTATICAS]
    if usar_precio:
        columnas += COLUMNAS_DINAMICAS

    entrenamiento = historia[[columna_id, columna_fecha, columna_objetivo]].merge(
        features[[c for c in columnas if c in features.columns]],
        on=[columna_id, columna_fecha],
        how="left",
    )
    dinamicas = [c for c in COLUMNAS_DINAMICAS if usar_precio and c in entrenamiento.columns]
    return _preparar_categoricas(entrenamiento), dinamicas


def _armar_x_df(
    entrenamiento: pd.DataFrame,
    corte: pd.Timestamp,
    horizonte_max: int,
    dinamicas: list[str],
    columna_id: str,
    columna_fecha: str,
) -> pd.DataFrame | None:
    """Las exógenas dinámicas para `corte+1..corte+h`, **congeladas en el valor del corte**.

    Ver el encabezado del módulo: es la decisión de diseño central. El valor que se repite es
    el de la fila del corte —el origen— y no el del mes siguiente, para que el modelo reciba
    en predicción lo mismo que vio en entrenamiento.

    Series sin fila en el corte (no vendieron ese mes) quedan con `NaN`: LightGBM lo maneja,
    e imputar inventaría un precio que nadie observó.
    """
    if not dinamicas:
        return None

    series = pd.DataFrame({columna_id: entrenamiento[columna_id].unique()})
    en_el_corte = entrenamiento.loc[
        entrenamiento[columna_fecha] == corte, [columna_id, *dinamicas]
    ]
    origen = series.merge(en_el_corte, on=columna_id, how="left")

    futuros = pd.DataFrame(
        {
            columna_fecha: pd.date_range(
                corte + pd.DateOffset(months=1), periods=horizonte_max, freq="MS"
            )
        }
    )
    return (
        origen.merge(futuros, how="cross")
        .sort_values([columna_id, columna_fecha])
        .reset_index(drop=True)[[columna_id, columna_fecha, *dinamicas]]
    )


def predecir_global(
    historia: pd.DataFrame,
    corte: pd.Timestamp,
    horizonte_max: int,
    auxiliares: dict[str, pd.DataFrame] | None = None,
    usar_precio: bool = True,
    escalar_target: bool = False,
    hiperparametros: dict | None = None,
    cuantiles: Sequence[float] | None = None,
    columna_id: str = "id_producto",
    columna_fecha: str = "anio_mes",
    columna_objetivo: str = "unidades",
) -> pd.DataFrame:
    """Predictor M2.3 — contrato `PredictorFn` de 4 argumentos.

    Args:
        historia: hechos mensuales hasta el corte, ya densificados por el arnés (ADR-010).
        corte: el "hoy" de esta corrida.
        horizonte_max: cuántos meses hacia adelante. Es también el `max_horizon` de
            `mlforecast`, o sea **cuántos modelos se entrenan**.
        auxiliares: del arnés. Se espera `{"catalogo": catalogo_producto}`. Sin catálogo el
            modelo corre igual —las columnas salen en nulo, el esquema de M2.2 es estable—
            pero pierde `categoria`, `laboratorio` y el contraste de nivel del precio.
        usar_precio: ablación de M2.3. En `False` no entra ninguna feature de precio
            dinámica y el modelo queda con lags + calendario + estáticas. Sirve para saber
            **qué compró M2.2**; sin este interruptor, M2.5 no puede atribuir su resultado.
        escalar_target: `LocalStandardScaler` de `mlforecast`. Las escalas por producto van
            de jeringas a vacunas y el modelo es uno solo, así que sin escalar las series
            grandes dominan el ajuste. Cuál conviene **se mide**, no se supone.
        cuantiles: M2.4. Con `CUANTILES_ESTANDAR` agrega `GlobalLGBM_P10/_P50/_P90` sin
            tocar la columna de media. Cuesta un ajuste por cuantil **y por horizonte**
            (con `max_horizon=12`, tres cuantiles son 36 modelos más), así que se pide
            explícitamente y no viene por defecto.

    Returns:
        `columna_id`, `columna_fecha` y la columna `GlobalLGBM`, para `corte+1..corte+h`.
        Más una columna por cuantil pedido.
    """
    catalogo = (auxiliares or {}).get("catalogo")
    corte = pd.Timestamp(corte).normalize().replace(day=1)

    # El recorte al corte se hace acá, una sola vez, aunque el arnés ya entregue la
    # historia recortada: este módulo no puede depender de que su llamador lo haya hecho.
    # No es teórico — sin esta línea, un mes posterior al corte entra al panel, el merge de
    # features lo deja sin catálogo, y `mlforecast` **corta** diciendo que `categoria`
    # "cambia en el tiempo". Lo encontró la red de M1.3.
    historia = historia[historia[columna_fecha] <= corte]
    if usar_precio and "precio_prom" not in historia.columns:
        raise ValueError(
            "`historia` no trae `precio_prom`, que es de donde salen las features de precio "
            "de M2.2. Pasá la tabla de hechos completa, o corré con `usar_precio=False` si "
            "querés el modelo sin precio a propósito (la ablación de M2.3)."
        )

    entrenamiento, dinamicas = _armar_entrenamiento(
        historia, corte, catalogo, usar_precio, columna_id, columna_fecha, columna_objetivo
    )

    modelos = _armar_modelos(cuantiles, hiperparametros or HIPERPARAMETROS)
    fcst = MLForecast(
        models=modelos,
        freq="MS",
        lags=LAGS,
        lag_transforms=LAG_TRANSFORMS,
        date_features=DATE_FEATURES,
        target_transforms=[LocalStandardScaler()] if escalar_target else None,
    )
    fcst.fit(
        entrenamiento,
        id_col=columna_id,
        time_col=columna_fecha,
        target_col=columna_objetivo,
        static_features=[c for c in ESTATICAS if c in entrenamiento.columns],
        max_horizon=horizonte_max,
    )

    x_df = _armar_x_df(
        entrenamiento, corte, horizonte_max, dinamicas, columna_id, columna_fecha
    )
    predicciones = fcst.predict(h=horizonte_max, X_df=x_df)

    # El target son unidades (ADR-007) y una demanda negativa no existe. LightGBM no lo
    # sabe: extrapola libre y una serie en descenso puede dar negativo. Se recorta en 0,
    # igual que hacen `CrostonSBA`/`TSB` por construcción (M1.6).
    #
    # Vale para los cuantiles con más razón que para la media: con 42% de series
    # intermitentes, el P10 de un producto que suele no venderse **es** 0, y ese cero es una
    # respuesta legítima ("bien puede no venderse nada"), no un faltante. Por eso el
    # intervalo se evalúa cerrado en `motor.backtesting.intervalos`.
    for columna in modelos:
        predicciones[columna] = predicciones[columna].clip(lower=0.0)
    return predicciones


def series_entrenables(
    historia: pd.DataFrame,
    columna_id: str = "id_producto",
    minimo_meses: int = 0,
) -> pd.Series:
    """Cuántos meses de historia tiene cada serie al corte.

    `mlforecast` descarta en silencio (`dropna=True`) las filas sin lags completos, así que
    una serie más corta que el lag más largo **no aporta filas de entrenamiento y tampoco
    recibe predicción**. Esa es la cobertura del modelo global y hay que poder mirarla, por
    la misma razón que la columna `cobertura` de las métricas existe.
    """
    conteo = historia.groupby(columna_id, observed=True).size()
    return conteo[conteo >= minimo_meses] if minimo_meses else conteo


def cobertura_esperada(historia: pd.DataFrame, columna_id: str = "id_producto") -> float:
    """Fracción de series con historia suficiente para que `mlforecast` genere features.

    El corte lo pone el lag más largo (`max(LAGS)`) más la ventana móvil más larga que se
    aplique sobre él. Es una **cota superior** de la cobertura del global, útil para saber si
    una corrida con cobertura baja es del modelo o del catálogo.
    """
    minimo = max(LAGS) + 1
    conteo = series_entrenables(historia, columna_id=columna_id)
    return float(np.mean(conteo >= minimo)) if len(conteo) else 0.0
