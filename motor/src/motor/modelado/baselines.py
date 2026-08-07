"""Baselines "normales" con `statsforecast` (M1.5): SeasonalNaive, media móvil, AutoETS,
AutoTheta, AutoARIMA.

`plan-diseno.md` §M1: cada producto queda con su mejor baseline según MASE en backtest —
esa selección es **M1.7**. Acá solo se corren los cinco, conformando el contrato
`PredictorFn` de `motor.backtesting.arnes`. Tampoco enruta por cuadrante de intermitencia
(M1.4): corre sobre toda la historia que reciba. Enrutar `modelado.baselines` vs
`modelado.intermitentes` por cuadrante es responsabilidad de quien arme la selección de
M1.7, no de este módulo.

Tres gotchas de integración con `statsforecast==1.7.8`, verificadas contra el dataset
real antes de escribir este módulo (no están en la documentación de la librería):

1. **Columnas exógenas fantasma:** `StatsForecast.forecast` interpreta cualquier columna
   del `df` además de id/fecha/objetivo como regresor exógeno obligatorio — pasarle
   `historia` completa (con `revenue`, `precio_prom`) explota pidiendo esas columnas por
   `X_df`. Por eso se recorta a las tres columnas necesarias antes de llamar.
2. **El id vuelve como índice, no como columna** (hay un `FutureWarning` sobre esto, con
   una variable de entorno para adoptar el comportamiento nuevo). El contrato del arnés
   exige `columnas_id` como columnas, así que se hace `reset_index()` antes de devolver.
3. **`AutoETS` y `AutoTheta` explotan** (`IndexError`, `ZeroDivisionError` respectivamente)
   con series de 1 a 3 meses de historia — el caso real de un producto recién entrado al
   catálogo en un corte temprano. `fallback_model=SeasonalNaive(season_length=1)` lo
   resuelve: la serie corta cae a ese fallback sin tirar abajo la corrida completa de
   todos los productos. Verificado con series de 1, 3 y 24 meses en el mismo lote.
"""

import pandas as pd
from statsforecast import StatsForecast
from statsforecast.models import AutoARIMA, AutoETS, AutoTheta, SeasonalNaive, WindowAverage

ESTACIONALIDAD = 12
"""Meses por ciclo estacional — el grano del motor es mensual (plan-diseno.md §Decisión 7)."""

VENTANA_MEDIA_MOVIL = 3
"""Meses que promedia `WindowAverage`. No es un valor tuneado, es el punto de partida de
M1.5; la comparación real contra los demás baselines la hace M1.7 vía MASE."""


def _modelos(nombres: list[str] | None = None) -> list:
    """Los 5 baselines de M1.5, o el subconjunto que se pida.

    **`nombres=None` devuelve los 5, que es el comportamiento de siempre**: el parámetro es
    aditivo y ninguna corrida existente cambia. Se agregó en M3.1 (§7.2) porque el costo por
    serie depende de la *forma* de la serie y a veces hay que dejar uno afuera con motivo
    medido — ver el docstring de `predecir_baselines`.
    """
    todos = {
        "SeasonalNaive": lambda: SeasonalNaive(season_length=ESTACIONALIDAD),
        "WindowAverage": lambda: WindowAverage(window_size=VENTANA_MEDIA_MOVIL),
        "AutoETS": lambda: AutoETS(season_length=ESTACIONALIDAD),
        "AutoTheta": lambda: AutoTheta(season_length=ESTACIONALIDAD),
        "AutoARIMA": lambda: AutoARIMA(season_length=ESTACIONALIDAD),
    }
    if nombres is None:
        return [construir() for construir in todos.values()]

    desconocidos = sorted(set(nombres) - set(todos))
    if desconocidos:
        raise ValueError(
            f"Baselines desconocidos: {desconocidos}. Disponibles: {sorted(todos)}"
        )
    # Se respeta el orden canónico y no el del argumento, para que dos llamadas con los
    # mismos modelos en distinto orden produzcan columnas idénticas.
    return [construir() for nombre, construir in todos.items() if nombre in set(nombres)]


def predecir_baselines(
    historia: pd.DataFrame,
    corte: pd.Timestamp,
    horizonte_max: int,
    columna_id: str = "id_producto",
    columna_fecha: str = "anio_mes",
    columna_objetivo: str = "unidades",
    n_jobs: int = 1,
    modelos: list[str] | None = None,
) -> pd.DataFrame:
    """Predictor M1.5 — conforme al contrato `PredictorFn` de `motor.backtesting.arnes`.

    Devuelve `columna_id`, `columna_fecha` y una columna por modelo (`SeasonalNaive`,
    `WindowAverage`, `AutoETS`, `AutoTheta`, `AutoARIMA`), para los `horizonte_max` meses
    siguientes al corte. `corte` no se usa directamente: `statsforecast` solo necesita
    saber hasta dónde llega `historia`, que ya viene recortada por el arnés — está en la
    firma porque el contrato de `PredictorFn` lo exige para todo predictor.

    Args:
        modelos: subconjunto de baselines a correr. **`None` corre los 5, que es el
            comportamiento de siempre** — el parámetro es aditivo y no mueve ninguna tabla
            congelada.

    `n_jobs` en 1 por defecto: subilo para correr a escala. Medido contra el dataset
    real, `AutoARIMA` cuesta ~2,9s por producto y `AutoTheta` ~1,6s — en serie, a 2.300
    productos x 18 cortes es inviable. Es una preocupación de quien corra M1.7/M1.8, no
    de este módulo, pero el parámetro queda expuesto desde ya para no tener que tocar la
    firma después.

    **El modelo caro depende de la forma de la serie, y eso sorprendió en M3.1 (§7.2).**
    Sobre las series de producto —dispersas y muchas cortas— el cuello es `AutoARIMA`
    (§6.5). Sobre las **series agregadas** —densas, 95 meses sin huecos— el reparto se da
    vuelta: `AutoTheta` se lleva el **89,7%** del tiempo (7,97 s/serie/corte contra 0,81 de
    `AutoARIMA`). Por eso existe `modelos`: no para tunear la lista de candidatos, sino para
    poder dejar afuera uno cuyo costo se midió y no se puede pagar."""
    solo_serie = historia[[columna_id, columna_fecha, columna_objetivo]]
    sf = StatsForecast(
        models=_modelos(modelos),
        freq="MS",
        n_jobs=n_jobs,
        fallback_model=SeasonalNaive(season_length=1),
    )
    predicciones = sf.forecast(
        h=horizonte_max,
        df=solo_serie,
        id_col=columna_id,
        time_col=columna_fecha,
        target_col=columna_objetivo,
    )
    return predicciones.reset_index()
