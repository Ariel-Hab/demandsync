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

**Dos criterios de selección, y no se mezclan (M1.9, ADR-016).**

- `elegir_mejor_por_serie` → un ganador **por serie**, con el MASE de *todos* los cortes.
  Reproduce el piso retrospectivo ya congelado.
- `elegir_mejor_por_corte` → un ganador **por (serie, corte)**, con el error que a esa
  altura ya se había observado. Es el piso contra el que se mide M2.

El primero es retrospectivo: elige el modelo de cada serie con información posterior a las
filas donde después se lo mide. Sirve como referencia fuerte, pero **el piso que produce
está inflado dos veces** — por el privilegio del hindsight y porque le baja la cobertura
(§5.6.1 punto 5). El segundo es el que hace comparables al piso y al global de M2.5, y va
acompañado de `armar_reporte_con_cascada`, que es la mitad que repara la cobertura.
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


def _orden_sin_mase(modelos: list[str], modelo_fallback: str) -> list[str]:
    """El orden fijo que se aplica cuando no hay ningún MASE con qué rankear: el fallback
    primero y el resto detrás, en el orden de `CANDIDATOS`.

    No es solo "quién gana": la cascada de `armar_reporte_con_cascada` necesita a dónde
    bajar si el fallback tampoco puede predecir esa celda, así que hace falta el orden
    completo y no un único nombre.
    """
    return [modelo_fallback] + [modelo for modelo in modelos if modelo != modelo_fallback]


def _ganador_por_fila(valores: np.ndarray, modelos: list[str], modelo_fallback: str) -> list[str]:
    """El de menor MASE en cada fila; `modelo_fallback` donde no hay ninguno definido.

    `valores` es la matriz (serie × modelo) de MASE medio.
    """
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
    return [
        modelo_fallback if sin_mase else modelos[i]
        for sin_mase, i in zip(sin_ganador, indice_ganador, strict=True)
    ]


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

    **Resuelto en M1.9 (ADR-016): esta función ya no produce el piso de M2.5** — lo hace
    `elegir_mejor_por_corte`. Se conserva porque la tabla del 2026-08-03 tiene que seguir
    siendo reproducible y porque los hallazgos de `roadmap-motor.md` §5.3 y §5.6.1 punto 4
    están construidos sobre ella. Para cualquier comparación contra un modelo nuevo, usá
    la prospectiva: el piso que sale de acá está inflado por el hindsight **y** por la
    cobertura que ese hindsight se lleva puesta (§5.6.1 punto 5).

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
    ganador = _ganador_por_fila(medio.to_numpy(), modelos, modelo_fallback)

    return pd.DataFrame({columna_id: medio.index, "modelo_ganador": ganador})


def elegir_mejor_por_corte(
    reporte: pd.DataFrame,
    train_df: pd.DataFrame,
    modelos: list[str] | None = None,
    estacionalidad: int = 12,
    columna_id: str = "id_producto",
    columna_fecha: str = "anio_mes",
    columna_corte: str = "corte",
    modelo_fallback: str = FALLBACK_SIN_MASE,
) -> pd.DataFrame:
    """Selección **prospectiva**: el ganador de cada serie se reelige en cada corte, con
    el error que a esa altura ya se había observado (M1.9, ADR-016).

    Devuelve una tabla **larga** — `columna_id`, `columna_corte`, `modelo`, `rango` — y no
    solo el ganador. El orden completo es lo que le permite a `armar_reporte_con_cascada`
    bajar al siguiente candidato cuando el elegido no puede cubrir esa celda, que es el
    componente que repara el 31% de la cobertura faltante del piso retrospectivo.

    **La regla de observabilidad (decisión 1 de M1.9), que es todo el asunto:** en el corte
    `t` solo entra el error de las filas con `columna_fecha <= t`. Un pronóstico emitido en
    `t-1` a h=12 recién se puede usar para elegir cuando su mes llegue, porque hasta
    entonces nadie sabe si acertó. Es la misma forma que la regla anti-leakage de la
    deflación, y ese único filtro implementa la regla entera: los cortes posteriores a `t`
    se caen solos —todos sus objetivos son posteriores a `t`— y del corte `t-1` sobrevive
    únicamente h=1.

    Usar "todos los cortes anteriores completos" parece prospectivo y no lo es: mira
    horizontes que en `t` todavía no se realizaron.

    **Arranque (decisión 2):** no se exige un mínimo de evidencia. El primer corte no tiene
    nada observado y cae entero a `modelo_fallback`; lo mismo las series que entran tarde
    al catálogo. La alternativa —un burn-in de k cortes— habría cambiado la ventana de
    evaluación y roto la comparación fila a fila contra el piso ya congelado.

    Se apoya en `backtesting.metricas.mase` en vez de recalcular la escala por su cuenta:
    ese wrapper ya tiene resueltas las incompatibilidades de `utilsforecast` y la
    densificación de ADR-010, y duplicarlas sería mantener dos definiciones de MASE.
    """
    modelos = list(modelos) if modelos else list(CANDIDATOS)
    _validar_fallback(modelos, modelo_fallback)
    orden_sin_mase = _orden_sin_mase(modelos, modelo_fallback)

    rankings = [
        _ranking_de_un_corte(
            reporte, corte, train_df, modelos, orden_sin_mase, estacionalidad,
            columna_id, columna_fecha, columna_corte,
        )
        for corte in sorted(reporte[columna_corte].dropna().unique())
    ]
    if not rankings:
        return pd.DataFrame(
            {columna_id: [], columna_corte: [], "modelo": [], "rango": []}
        ).astype({"modelo": object, "rango": int})
    return pd.concat(rankings, ignore_index=True)


def _ranking_de_un_corte(
    reporte: pd.DataFrame,
    corte: pd.Timestamp,
    train_df: pd.DataFrame,
    modelos: list[str],
    orden_sin_mase: list[str],
    estacionalidad: int,
    columna_id: str,
    columna_fecha: str,
    columna_corte: str,
) -> pd.DataFrame:
    """El ranking de candidatos de un corte, con la regla de observabilidad aplicada."""
    series = pd.Index(
        reporte.loc[reporte[columna_corte] == corte, columna_id].unique(), name=columna_id
    )
    # LA regla: solo el error cuyo mes objetivo ya ocurrió al corte. Cambiar `<=` por `<`
    # o sacar el filtro entero convierte esto en la selección retrospectiva de nuevo.
    observable = reporte[reporte[columna_fecha] <= corte]

    if observable.empty:
        medio = pd.DataFrame(np.nan, index=series, columns=modelos)
    else:
        por_corte = mase(
            observable,
            modelos=modelos,
            train_df=train_df,
            estacionalidad=estacionalidad,
            columna_id=columna_id,
            columna_fecha=columna_fecha,
            columna_corte=columna_corte,
        )
        medio = por_corte.groupby(columna_id, observed=True)[modelos].mean().reindex(series)

    valores = medio.to_numpy(dtype=float)
    sin_mase = np.isnan(valores).all(axis=1)
    # `kind="stable"`: ante empate —o entre los NaN, que van todos a +inf— manda el orden
    # de `CANDIDATOS`, así el ranking es determinístico y no depende del orden de las filas.
    orden = np.argsort(np.where(np.isnan(valores), np.inf, valores), axis=1, kind="stable")
    orden[sin_mase] = [modelos.index(modelo) for modelo in orden_sin_mase]

    n_series, n_modelos = orden.shape
    return pd.DataFrame(
        {
            columna_id: np.repeat(medio.index.to_numpy(), n_modelos),
            columna_corte: corte,
            # `dtype=object` y no el array de strings de numpy: ancho fijo, trunca en
            # silencio (ver el comentario de `_ganador_por_fila`).
            "modelo": np.asarray(modelos, dtype=object)[orden.ravel()],
            "rango": np.tile(np.arange(n_modelos), n_series),
        }
    )


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


def armar_reporte_con_cascada(
    reporte: pd.DataFrame,
    ranking: pd.DataFrame,
    modelos: list[str] | None = None,
    columna_id: str = "id_producto",
    columna_corte: str = "corte",
    columna_pred: str = "pred",
    modelo_fallback: str = FALLBACK_SIN_MASE,
) -> pd.DataFrame:
    """Arma `columna_pred` con el ranking prospectivo de `elegir_mejor_por_corte`,
    bajando al siguiente candidato **disponible** cuando el elegido no predijo esa celda.

    **Por qué la cascada, y no simplemente el ganador (decisión 3 de M1.9).** Sin ella, un
    ganador que no puede cubrir el horizonte deja la celda vacía aunque otros 5 o 6
    candidatos sí hayan predicho: son 5.655 filas del piso retrospectivo —el 31% de las que
    no tienen predicción—, casi todas de `SeasonalNaive`, que solo proyecta tantos meses
    como historia tiene (§5.6.1 punto 5). Un pipeline productivo no publicaría un hueco
    teniendo un pronóstico a mano; usaría el siguiente de su propio ranking.

    **Lo que NO hace: inventar.** Si ningún candidato predijo esa celda, queda en `NaN`.
    Ese es el arranque en frío genuino —productos con primera venta posterior al corte— y
    es la mitad de la brecha de cobertura que los baselines no pueden cerrar. Distinguir
    las dos causas es lo que le permite a M2.5 comparar a igual cobertura.

    Devuelve además `modelo_usado` y `rango_usado`: qué candidato terminó aportando cada
    fila y en qué puesto del ranking estaba. Es la evidencia de cuánto disparó la cascada,
    y sin ella el efecto queda indistinguible de una mejora del ganador.

    Ojo con lo que hay que esperar del resultado: rellenar esas filas **empeora** el WAPE
    (+0,0060 a h=6, medido en §5.6.1). Son las series difíciles que el piso retrospectivo
    omitía y por omitirlas puntuaba mejor.
    """
    modelos = list(modelos) if modelos else list(CANDIDATOS)
    _validar_fallback(modelos, modelo_fallback)
    corrida = reporte.attrs.get("corrida")

    desconocidos = sorted(set(ranking["modelo"].unique()) - set(modelos))
    if desconocidos:
        raise ValueError(
            f"`ranking` nombra modelos que no están en {modelos}: {desconocidos}. "
            "Sin columna de predicción con ese nombre no hay de dónde tomar el valor."
        )

    rangos = _matriz_de_rangos(
        reporte, ranking, modelos, modelo_fallback, columna_id, columna_corte
    )
    valores = reporte[modelos].to_numpy(dtype=float)
    disponible = ~np.isnan(valores)

    # El único criterio: entre los que SÍ predijeron, el de mejor rango. Los que no
    # predijeron se mandan a +inf y por lo tanto nunca ganan salvo que no quede nadie.
    efectivo = np.where(disponible, rangos, np.inf)
    elegido = np.nan_to_num(efectivo, nan=np.inf).argmin(axis=1)

    filas = np.arange(len(reporte))
    ninguno_predijo = ~disponible.any(axis=1)
    prediccion = np.where(ninguno_predijo, np.nan, valores[filas, elegido])
    usado = np.where(ninguno_predijo, None, np.asarray(modelos, dtype=object)[elegido])
    rango_usado = np.where(ninguno_predijo, np.nan, rangos[filas, elegido])

    resultado = reporte.copy()
    resultado[columna_pred] = prediccion
    resultado["modelo_usado"] = usado
    resultado["rango_usado"] = rango_usado
    if corrida is not None:
        resultado.attrs["corrida"] = corrida
    return resultado


def resumen_de_cascada(reporte: pd.DataFrame) -> pd.DataFrame:
    """De dónde salió cada predicción: del ganador del corte, de la cascada, o de ningún
    lado.

    Es el número que hace legible el resultado de M1.9. Sin él, el piso prospectivo
    aparece con más cobertura y peor WAPE sin que se vea que las dos cosas son la misma:
    las filas que la cascada agrega son las series jóvenes que el piso retrospectivo
    omitía, y por omitirlas puntuaba mejor.
    """
    origen = pd.Series("cascada", index=reporte.index, dtype=object)
    origen[reporte["rango_usado"] == 0] = "ganador del corte"
    origen[reporte["rango_usado"].isna()] = "sin predicción (ningún candidato)"

    tabla = origen.value_counts().rename("filas").rename_axis("origen").reset_index()
    tabla["%"] = (tabla["filas"] / len(reporte) * 100).round(2)
    return tabla


def _matriz_de_rangos(
    reporte: pd.DataFrame,
    ranking: pd.DataFrame,
    modelos: list[str],
    modelo_fallback: str,
    columna_id: str,
    columna_corte: str,
) -> np.ndarray:
    """Alinea el ranking largo contra las filas del reporte → matriz (fila × modelo).

    Se alinea por índice en vez de por `merge` a propósito: el reporte ya tiene columnas
    con el nombre de cada modelo (sus predicciones), así que un merge las chocaría contra
    las del ranking y pandas resolvería el choque agregando sufijos en silencio.

    Los pares `(serie, corte)` que el ranking no cubre caen al orden fijo de
    `_orden_sin_mase`, igual que las series sin MASE: no se pueden dejar sin ranking sin
    romper la garantía de M1.0 de que ninguna celda del reporte se borra.
    """
    ancho = ranking.pivot(index=[columna_id, columna_corte], columns="modelo", values="rango")
    ancho = ancho.reindex(columns=modelos)

    clave = pd.MultiIndex.from_arrays([reporte[columna_id], reporte[columna_corte]])
    rangos = ancho.reindex(clave).to_numpy(dtype=float)

    orden_fijo = np.full(len(modelos), np.nan)
    for rango, modelo in enumerate(_orden_sin_mase(modelos, modelo_fallback)):
        orden_fijo[modelos.index(modelo)] = rango
    rangos[np.isnan(rangos).all(axis=1)] = orden_fijo
    return rangos


def estabilidad_de_la_seleccion(
    ranking: pd.DataFrame,
    columna_id: str = "id_producto",
    columna_corte: str = "corte",
) -> pd.DataFrame:
    """Cuántas veces cambia de ganador cada serie a lo largo de los cortes.

    Es la lectura que dice **cuánto compraba el hindsight**: si el ganador prospectivo casi
    nunca cambia, la selección retrospectiva no estaba haciendo gran diferencia y el piso
    se mueve poco; si cambia seguido, elegir con todos los cortes a la vista era un
    privilegio grande. Sin este número, el resultado de M1.9 se puede leer como ruido.
    """
    ganadores = ranking[ranking["rango"] == 0].sort_values([columna_id, columna_corte])
    cambios = (
        ganadores.groupby(columna_id, observed=True)["modelo"]
        .agg(lambda modelos: int((modelos != modelos.shift()).sum() - 1))
        .rename("cambios")
    )
    distribucion = cambios.value_counts().rename("n_series").rename_axis("cambios").reset_index()
    distribucion = distribucion.sort_values("cambios").reset_index(drop=True)
    distribucion["%"] = (distribucion["n_series"] / distribucion["n_series"].sum() * 100).round(1)
    return distribucion


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
