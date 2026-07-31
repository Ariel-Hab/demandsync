"""Selección por serie (M1.7): cada producto queda con su mejor baseline según MASE.

`plan-diseno.md` §M1: "Selección por serie: cada producto queda con su mejor baseline
según MASE en backtest." M1.5 (`baselines.py`) y M1.6 (`intermitentes.py`) ya corren los
7 candidatos dentro del arnés, pero ninguno enruta: cada uno predice toda la serie que
recibe, sea cual sea su cuadrante. Este módulo es el que decide, por producto, cuál de
los 7 se queda.

**Decisión de diseño:** los candidatos compiten libres, sin restricción por cuadrante de
`motor.clasificacion` (M1.4). El cuadrante se sigue usando para desagregar el reporte
(M1.2), pero no filtra qué modelos se prueban en cada serie — es el dato (MASE medido) el
que decide, no una regla de enrutamiento fija. Si un candidato nunca gana en un cuadrante
dado, esa ausencia queda documentada en la tabla congelada, no oculta de antemano.

Contrato de las tres piezas:

1. `predecir_todos_los_candidatos` — un `PredictorFn` combinado (mismo contrato que
   `modelado.baselines`/`modelado.intermitentes`) que junta las 7 columnas de predicción
   en un solo reporte, para no correr el arnés dos veces.
2. `elegir_mejor_por_serie` — a partir de ese reporte, calcula el MASE medio de cada
   candidato por producto (vía `backtesting.metricas.mase`, que ya soporta una lista de
   modelos) y devuelve el ganador.
3. `armar_reporte_seleccionado` — arma la columna `pred` final tomando, fila por fila, la
   predicción del modelo ganador de esa serie. Vectorizado: a escala real (~2.300
   productos × 18 cortes × 12 horizontes) un `.apply` fila a fila sería el cuello de
   botella, no los modelos.
"""

import numpy as np
import pandas as pd

from ..backtesting.metricas import mase
from .baselines import predecir_baselines
from .intermitentes import predecir_intermitentes

CANDIDATOS = [
    "SeasonalNaive",
    "WindowAverage",
    "AutoETS",
    "AutoTheta",
    "AutoARIMA",
    "CrostonSBA",
    "TSB",
]
"""Los 7 predictores de M1.5+M1.6, en el orden en que compiten. El fallback de
`elegir_mejor_por_serie` (`FALLBACK_SIN_MASE`) tiene que ser uno de estos."""

FALLBACK_SIN_MASE = "SeasonalNaive"
"""A qué modelo cae una serie cuando el MASE queda indefinido (NaN) para los 7
candidatos — el caso de una serie de escala cero (constante, o con muy poca historia;
ver `backtesting.metricas.mase`). Sin un fallback la serie quedaría sin predicción,
violando la garantía de M1.0 de que ninguna celda del reporte se borra."""


def _validar_fallback(modelos: list[str], modelo_fallback: str) -> None:
    """El fallback tiene que ser uno de los candidatos: si no, la serie que caiga en él
    queda con un `modelo_ganador` que no corresponde a ninguna columna de predicción y el
    reporte final no se puede armar. Mejor cortar acá que fallar más adelante."""
    if modelo_fallback not in modelos:
        raise ValueError(
            f"modelo_fallback={modelo_fallback!r} no está entre los modelos {modelos}: "
            "ninguna columna de predicción se llamaría así"
        )


def predecir_todos_los_candidatos(
    historia: pd.DataFrame,
    corte: pd.Timestamp,
    horizonte_max: int,
    columna_id: str = "id_producto",
    columna_fecha: str = "anio_mes",
    columna_objetivo: str = "unidades",
    n_jobs: int = 1,
) -> pd.DataFrame:
    """Predictor combinado — conforme al contrato `PredictorFn` de `motor.backtesting.arnes`.

    Corre `predecir_baselines` (M1.5) y `predecir_intermitentes` (M1.6) sobre la misma
    `historia` y junta las 7 columnas en un solo DataFrame, para que `ejecutar_backtest`
    se corra una sola vez con las 7 predicciones disponibles por fila.
    """
    normales = predecir_baselines(
        historia, corte, horizonte_max, columna_id, columna_fecha, columna_objetivo, n_jobs=n_jobs
    )
    intermitentes = predecir_intermitentes(
        historia, corte, horizonte_max, columna_id, columna_fecha, columna_objetivo, n_jobs=n_jobs
    )
    return normales.merge(intermitentes, on=[columna_id, columna_fecha])


def elegir_mejor_por_serie(
    reporte: pd.DataFrame,
    train_df: pd.DataFrame,
    modelos: list[str] | None = None,
    estacionalidad: int = 12,
    columna_id: str = "id_producto",
    columna_corte: str = "corte",
    modelo_fallback: str = FALLBACK_SIN_MASE,
) -> pd.DataFrame:
    """Por cada serie, promedia el MASE de cada candidato a través de los cortes del
    backtest y devuelve una fila con `columna_id` + `modelo_ganador` (el de menor MASE
    medio).

    **La selección es retrospectiva, y eso hace que el piso sea optimista.** El ganador
    de cada serie se elige con el MASE de *todos* los cortes, y después
    `armar_reporte_seleccionado` lo aplica también a los cortes más viejos: el modelo se
    eligió con información posterior a las filas donde se mide. Es lo que especifica
    `plan-diseno.md` §M1 ("cada producto queda con su mejor baseline según MASE en
    backtest") y es la convención habitual para fijar una referencia fuerte, pero **no
    es un procedimiento prospectivo**: un pipeline productivo tendría que elegir el
    método en cada corte usando solo datos ≤ corte.

    Consecuencia para M2.5, que hay que tener presente al comparar: este piso está
    medido con selección en hindsight, así que está **más alto** que el de un
    procedimiento prospectivo. Si el modelo global de M2 se mide sin ese privilegio, la
    comparación lo castiga. Antes del champion/challenger hay que decidir si se nivela
    (selección prospectiva para el baseline) o si el global recibe el mismo trato — ver
    `roadmap-motor.md` §12.5.

    Esto **no** es el leakage que ataja la red de M1.3: ahí el peligro es que un
    predictor vea el futuro *de los datos* al predecir un corte. Acá cada predicción
    individual sigue siendo limpia (el arnés garantiza historia ≤ corte); lo que usa
    información posterior es la elección de *qué modelo* mirar.

    Series con MASE indefinido en los `modelos` para todos los cortes (NaN en las 7
    columnas: escala cero, ver `backtesting.metricas.mase`) caen a `modelo_fallback` en
    vez de quedar sin ganador — una serie sin escala para medir MASE igual necesita una
    predicción en la tabla final.

    `estacionalidad` default 12 (grano mensual, igual que `modelado.baselines`); bajalo
    en tests para no necesitar 13+ meses de historia por serie.
    """
    modelos = list(modelos) if modelos else list(CANDIDATOS)
    _validar_fallback(modelos, modelo_fallback)
    por_corte = mase(
        reporte,
        modelos=modelos,
        train_df=train_df,
        estacionalidad=estacionalidad,
        columna_id=columna_id,
        columna_corte=columna_corte,
    )
    medio = por_corte.groupby(columna_id, observed=True)[modelos].mean()

    valores = medio.to_numpy()
    sin_ganador = np.isnan(valores).all(axis=1)
    # `argmin` sobre una fila toda-NaN devolvería 0 sin avisar, así que los NaN se
    # mandan a +inf y las filas sin ningún MASE válido se sobrescriben con el fallback.
    indice_ganador = np.where(np.isnan(valores), np.inf, valores).argmin(axis=1)

    # Una lista y no `np.array(modelos)[indice]` con asignación posterior: los arrays de
    # strings de numpy tienen ancho FIJO, así que escribirles un nombre más largo que el
    # candidato más largo lo trunca en silencio (verificado: sobre `np.array(["TSB"])`,
    # asignar "SeasonalNaive" guarda "Sea"). Hoy `_validar_fallback` hace ese caso
    # inalcanzable —el fallback siempre es uno de `modelos`, así que el array siempre
    # entra—; esto es defensa en profundidad para que un cambio futuro en la validación
    # no reabra un bug silencioso.
    ganador = [
        modelo_fallback if sin_mase else modelos[i]
        for sin_mase, i in zip(sin_ganador, indice_ganador, strict=True)
    ]

    return pd.DataFrame({columna_id: medio.index, "modelo_ganador": ganador})


def armar_reporte_seleccionado(
    reporte: pd.DataFrame,
    ganadores: pd.DataFrame,
    modelos: list[str] | None = None,
    columna_id: str = "id_producto",
    columna_pred: str = "pred",
    modelo_fallback: str = FALLBACK_SIN_MASE,
) -> pd.DataFrame:
    """Arma `columna_pred` tomando, fila por fila, la predicción del modelo ganador de
    esa serie (`ganadores`, de `elegir_mejor_por_serie`).

    Series que no aparecen en `ganadores` (sin ninguna fila comparable en el cálculo de
    MASE) caen también a `modelo_fallback`, no se excluyen del reporte: `ejecutar_backtest`
    (M1.0) ya garantiza que ninguna celda se borra y esta función no puede violar esa
    garantía silenciosamente.

    Vectorizado con `numpy` a propósito: un `.apply` fila a fila sobre el reporte
    completo (~2.300 productos × 18 cortes × 12 horizontes) sería más lento que los
    modelos que lo generaron.

    Preserva `reporte.attrs["corrida"]` a través del merge (pandas lo descarta —
    ver `roadmap-motor.md` §12.2).
    """
    modelos = list(modelos) if modelos else list(CANDIDATOS)
    _validar_fallback(modelos, modelo_fallback)
    corrida = reporte.attrs.get("corrida")

    combinado = reporte.merge(ganadores[[columna_id, "modelo_ganador"]], on=columna_id, how="left")
    combinado["modelo_ganador"] = combinado["modelo_ganador"].fillna(modelo_fallback)

    indice_de_modelo = {modelo: i for i, modelo in enumerate(modelos)}
    indice_ganador = combinado["modelo_ganador"].map(indice_de_modelo)
    if indice_ganador.isna().any():
        desconocidos = sorted(combinado.loc[indice_ganador.isna(), "modelo_ganador"].unique())
        raise ValueError(
            f"`ganadores` nombra modelos que no están en {modelos}: {desconocidos}. "
            "Sin columna de predicción con ese nombre no hay de dónde tomar el valor."
        )

    # `astype(int)` explícito: sin NaN el `map` ya da int64, pero con un reporte vacío
    # daría dtype object y numpy no puede indexar con eso.
    valores = combinado[modelos].to_numpy()
    combinado[columna_pred] = valores[np.arange(len(combinado)), indice_ganador.astype(int)]

    resultado = combinado.drop(columns=["modelo_ganador"])
    if corrida is not None:
        resultado.attrs["corrida"] = corrida
    return resultado


def resumen_de_ganadores(
    ganadores: pd.DataFrame,
    clasificacion: pd.DataFrame | None = None,
    columna_id: str = "id_producto",
    columna_cuadrante: str = "cuadrante",
) -> pd.DataFrame:
    """Cuántas series ganó cada modelo, abierto por cuadrante de intermitencia.

    Es el contenido propio de M1.7 y la razón de ser de la unidad: si un solo modelo
    ganara en todo el catálogo, seleccionar por serie no valdría la pena y bastaría con
    correr ese. Abierto por cuadrante muestra además si el enrutamiento que M1.4 sugiere
    (intermitentes → Croston/TSB) lo confirma el MASE medido o no.

    Sin `clasificacion` devuelve solo el conteo por modelo. Con ella, una columna por
    cuadrante más `total`, ordenado por `total` descendente. Los modelos que **no
    ganaron ninguna serie no aparecen**: eso también es información, y queda explícito
    al comparar contra `CANDIDATOS`.
    """
    if clasificacion is None:
        conteo = ganadores["modelo_ganador"].value_counts()
        return conteo.rename("total").rename_axis("modelo_ganador").reset_index()

    con_cuadrante = ganadores.merge(
        clasificacion[[columna_id, columna_cuadrante]], on=columna_id, how="left"
    )
    con_cuadrante[columna_cuadrante] = con_cuadrante[columna_cuadrante].fillna("sin_clasificar")

    tabla = pd.crosstab(con_cuadrante["modelo_ganador"], con_cuadrante[columna_cuadrante])
    tabla["total"] = tabla.sum(axis=1)
    return tabla.sort_values("total", ascending=False).rename_axis(None, axis=1).reset_index()
