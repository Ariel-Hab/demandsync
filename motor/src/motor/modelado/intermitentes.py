"""Rama intermitente con `statsforecast` (M1.6): `CrostonSBA` y `TSB`.

Para las series `intermitente`/`lumpy` de `motor.clasificacion` (M1.4) — ~42% de las
series del cliente real (EDA §3), donde un `SeasonalNaive` o una media móvil predicen
un promedio que nunca ocurre (ej. "0,75 unidades por mes") y revientan el WAPE. Croston
y sus variantes modelan por separado el intervalo entre demandas y el tamaño cuando hay
demanda, en vez de una tasa mensual continua.

Mismo contrato `PredictorFn` que `modelado.baselines` (M1.5) y mismas dos gotchas de
integración con `statsforecast==1.7.8` (recorte de columnas + `reset_index()`); ver el
docstring de `baselines.py` para el detalle. No enruta por cuadrante: corre sobre toda
la historia que reciba, igual que M1.5 — el enrutamiento es responsabilidad de quien
arme la selección de M1.7.
"""

import pandas as pd
from statsforecast import StatsForecast
from statsforecast.models import TSB, CrostonSBA

ALPHA_DEMANDA = 0.2
ALPHA_PROBABILIDAD = 0.2
"""Constantes de suavizado de TSB (tamaño de demanda y probabilidad de venta). No tienen
default en la librería. Son un punto de partida documentado, no una calibración —
literatura y ejemplos de referencia usan valores en este rango; M1.7 es quien decide
por MASE si TSB le gana a algo, no el valor de estas constantes."""


def predecir_intermitentes(
    historia: pd.DataFrame,
    corte: pd.Timestamp,
    horizonte_max: int,
    columna_id: str = "id_producto",
    columna_fecha: str = "anio_mes",
    columna_objetivo: str = "unidades",
    n_jobs: int = 1,
) -> pd.DataFrame:
    """Predictor M1.6 — conforme al contrato `PredictorFn` de `motor.backtesting.arnes`.

    Devuelve `columna_id`, `columna_fecha`, `CrostonSBA` y `TSB` para los
    `horizonte_max` meses siguientes al corte. Ambos métodos predicen un valor **plano**
    a lo largo del horizonte (no varían mes a mes): es el comportamiento esperado de
    Croston/TSB, que modelan una tasa de demanda de largo plazo, no un patrón estacional
    — no es un defecto de esta implementación.
    """
    solo_serie = historia[[columna_id, columna_fecha, columna_objetivo]]
    sf = StatsForecast(
        models=[CrostonSBA(), TSB(alpha_d=ALPHA_DEMANDA, alpha_p=ALPHA_PROBABILIDAD)],
        freq="MS",
        n_jobs=n_jobs,
    )
    predicciones = sf.forecast(
        h=horizonte_max,
        df=solo_serie,
        id_col=columna_id,
        time_col=columna_fecha,
        target_col=columna_objetivo,
    )
    return predicciones.reset_index()
