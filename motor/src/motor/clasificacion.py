"""Clasificador de intermitencia Syntetos-Boylan por serie (M1.4).

Cada serie cae en uno de cuatro cuadrantes según dos medidas: cada cuánto se vende
(ADI, intervalo medio entre demandas) y cuánto varía la cantidad cuando se vende
(CV², coeficiente de variación al cuadrado de las demandas no nulas).

| | CV² bajo | CV² alto |
|---|---|---|
| **ADI bajo** (se vende seguido) | `suave` | `erratica` |
| **ADI alto** (se vende salteado) | `intermitente` | `lumpy` |

Para qué se usa, y son dos cosas distintas:

1. **Enrutar el método de forecast** (M1.5/M1.6). ~42% de las series del cliente 1
   requiere la rama Croston/SBA/TSB (EDA §3); un `SeasonalNaive` les queda pésimo.
   **Acá la clasificación tiene que calcularse con datos ≤ corte**, si no el modelo
   elige su método con información del futuro. La red de `backtesting/leakage.py`
   verifica exactamente eso, y hay un test que la corre sobre este módulo.
2. **Desagregar el reporte de backtest** por cuadrante, que lo exige el gate de M1.2.
   Un WAPE global esconde que las series intermitentes se comportan distinto.

Este módulo vive en el motor y **no** en `datasets/`. Antes estaba en
`datasets/sintetico/clasificacion.py`, que era una dependencia invertida: el código de
producción no puede depender de una herramienta de desarrollo, y de hecho no podía —
`datasets/` no es un paquete instalable, así que el import fallaba con
`ModuleNotFoundError`. El generador ahora importa de acá.
"""

import numpy as np
import pandas as pd

ADI_UMBRAL = 1.32
CV2_UMBRAL = 0.49
"""Umbrales de Syntetos-Boylan. Son constantes del método, no calibración nuestra: no
se tocan sin un ADR, porque mover un umbral recategoriza series y cambia el método de
forecast que se les asigna."""

VENTANA_MESES = 36
"""Ventana de clasificación (EDA §3). Tres años: suficiente para estimar el intervalo
entre demandas de una serie intermitente sin arrastrar comportamiento viejo."""

CUADRANTES = ("suave", "intermitente", "erratica", "lumpy")
SIN_ACTIVIDAD = "sin_actividad"


def clasificar_serie(unidades_mensuales: np.ndarray) -> tuple[str, float, float]:
    """Clasifica una serie mensual **densa** (con ceros explícitos en los meses sin
    demanda) y devuelve `(cuadrante, adi, cv2)`.

    La serie tiene que venir densa: si le pasás solo los meses con venta, el ADI da 1
    para todo y no hay intermitencia que detectar. `clasificar_series()` se encarga de
    densificar; esta función es el núcleo y asume que ya está hecho.

    Casos degenerados, documentados porque son frecuentes en la cola larga:
    - sin ninguna demanda → `sin_actividad`, con ADI infinito y CV² indefinido. No entra
      en ningún cuadrante y queda fuera de la distribución.
    - una sola demanda en la ventana → CV² = 0 (una observación no tiene dispersión), así
      que cae en `intermitente` y no en `lumpy`. Es una propiedad conocida de la
      taxonomía con muestras mínimas, no un error. Importa a nivel cliente×producto,
      donde el 53,5% de los pares compró en ≤2 de 36 meses (EDA §5).
    """
    no_cero = unidades_mensuales[unidades_mensuales > 0]
    n_periodos = len(unidades_mensuales)
    n_demandas = len(no_cero)
    if n_demandas == 0:
        return SIN_ACTIVIDAD, np.inf, np.nan

    adi = n_periodos / n_demandas
    media = no_cero.mean()
    cv2 = (no_cero.std(ddof=0) / media) ** 2 if media > 0 else np.nan

    if adi < ADI_UMBRAL:
        cuadrante = "suave" if cv2 < CV2_UMBRAL else "erratica"
    else:
        cuadrante = "intermitente" if cv2 < CV2_UMBRAL else "lumpy"
    return cuadrante, adi, cv2


def clasificar_series(
    datos: pd.DataFrame,
    columnas_id: list[str] | None = None,
    columna_fecha: str = "anio_mes",
    columna_objetivo: str = "unidades",
    hasta: pd.Timestamp | None = None,
    ventana_meses: int = VENTANA_MESES,
) -> pd.DataFrame:
    """Clasifica cada serie de `datos` sobre los últimos `ventana_meses`.

    Args:
        hasta: último mes de la ventana. **Pasalo explícitamente cuando clasifiques
            dentro de un backtest**: tiene que ser el corte, no el último mes de los
            datos, o la clasificación mira el futuro. Por defecto, el último mes de
            `datos`.

    Devuelve una fila por serie con `columnas_id` + `cuadrante`, `adi`, `cv2`.

    **Regla de calendario (ADR-010):** la ventana de cada serie arranca en el más
    reciente entre el inicio de la ventana y su **primera venta histórica**. Un producto
    que entró al catálogo hace 10 meses se clasifica sobre 10 meses, no sobre 36: contar
    26 meses de ceros que nunca existieron le infla el ADI y lo etiqueta como
    intermitente cuando puede ser perfectamente suave. Es la misma regla que la
    densificación del arnés, por el mismo motivo — y pega en los productos nuevos, que
    son justamente los que más incertidumbre tienen.

    La primera venta se busca en **toda la historia disponible ≤ `hasta`**, no dentro de
    la ventana. La distinción importa: un producto que existe desde 2018 y no vendió en
    los primeros meses de la ventana tuvo demanda cero de verdad, y esos ceros cuentan.
    Solo se recorta el arranque de los productos que todavía no existían.
    """
    columnas_id = list(columnas_id) if columnas_id else ["id_producto"]
    ultimo_mes = pd.Timestamp(hasta) if hasta is not None else datos[columna_fecha].max()
    inicio_ventana = ultimo_mes - pd.DateOffset(months=ventana_meses - 1)

    historia = datos[datos[columna_fecha] <= ultimo_mes]
    # Ojo con la clave: `groupby` sobre una lista de una sola columna devuelve la clave
    # como tupla `(valor,)` (pandas ≥2.2) pero indexa la Series por el escalar. Buscar
    # con la tupla devuelve siempre NaT y la regla de ADR-010 no se aplica nunca —
    # sin error, simplemente sin efecto. Se normaliza explícitamente.
    primera_venta_por_serie = (
        historia.loc[historia[columna_objetivo] > 0]
        .groupby(columnas_id, observed=True)[columna_fecha]
        .min()
        .to_dict()
    )
    clave_unica = len(columnas_id) == 1

    ventana = historia[historia[columna_fecha] >= inicio_ventana]
    if ventana.empty:
        return pd.DataFrame(columns=[*columnas_id, "cuadrante", "adi", "cv2"])

    filas = []
    for claves, grupo in ventana.groupby(columnas_id, observed=True, sort=True):
        clave_tupla = claves if isinstance(claves, tuple) else (claves,)
        primera_venta = primera_venta_por_serie.get(
            clave_tupla[0] if clave_unica else clave_tupla, pd.NaT
        )
        desde = inicio_ventana if pd.isna(primera_venta) else max(inicio_ventana, primera_venta)
        meses = pd.date_range(desde, ultimo_mes, freq="MS")
        serie = (
            grupo.set_index(columna_fecha)[columna_objetivo]
            .reindex(meses, fill_value=0.0)
            .to_numpy()
        )
        cuadrante, adi, cv2 = clasificar_serie(serie)
        filas.append(
            {
                **dict(zip(columnas_id, clave_tupla, strict=True)),
                "cuadrante": cuadrante,
                "adi": adi,
                "cv2": cv2,
            }
        )
    return pd.DataFrame(filas)


def distribucion_cuadrantes(clasificacion: pd.DataFrame) -> dict[str, float]:
    """Porcentaje de series en cada cuadrante, **excluyendo `sin_actividad`**.

    Se excluye porque no es un cuadrante: es la ausencia de señal. Incluirlo en el
    denominador haría que los porcentajes no fueran comparables con los del EDA, que se
    calcularon sobre productos activos.
    """
    clasificados = clasificacion[clasificacion["cuadrante"] != SIN_ACTIVIDAD]
    if clasificados.empty:
        return {}
    return (clasificados["cuadrante"].value_counts(normalize=True) * 100).to_dict()


def muestra_estratificada(
    hechos: pd.DataFrame,
    n_por_cuadrante: int,
    semilla: int = 42,
    columna_id: str = "id_producto",
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Hasta `n_por_cuadrante` productos de cada cuadrante, con semilla fija.

    Es el muestreo con el que se congeló la tabla sintética de M1.7 (`roadmap-motor.md`
    §5.2): estratificar da mejores estadísticas por cuadrante que la distribución natural,
    donde `lumpy` es ~11%.

    **Vive en el paquete y no en el script que la usa** porque cualquier corrida que quiera
    compararse contra esa tabla tiene que muestrear **exactamente igual** — misma semilla,
    mismo criterio, mismo orden. Dos implementaciones equivalentes que sortean distinto
    producen tablas que parecen comparables y no lo son (M2.3).

    `sin_actividad` se excluye: no es un cuadrante sino la ausencia de señal, el mismo
    criterio con el que `distribucion_cuadrantes` compara contra el EDA.

    Devuelve los hechos recortados y cuántos productos quedaron por cuadrante — el conteo
    va a la tabla: si algún cuadrante tenía menos de `n_por_cuadrante` y se tomaron todos,
    eso tiene que verse y no quedar como un recorte silencioso.
    """
    clasificacion = clasificar_series(hechos)
    activos = clasificacion[clasificacion["cuadrante"] != SIN_ACTIVIDAD]

    # Barajar y tomar los primeros N de cada grupo, en vez de `groupby().apply(sample)`:
    # da lo mismo, no usa el `include_groups` que pandas deprecó, y un cuadrante con
    # menos de N productos devuelve todos los que tenga sin caso especial.
    barajado = activos.sample(frac=1, random_state=semilla)
    elegidos = barajado.groupby("cuadrante", observed=True).head(n_por_cuadrante)

    conteo = elegidos["cuadrante"].value_counts().to_dict()
    return hechos[hechos[columna_id].isin(elegidos[columna_id])], conteo


def etiquetar(reporte: pd.DataFrame, clasificacion: pd.DataFrame) -> pd.DataFrame:
    """Pega la columna `cuadrante` a un reporte de backtest para desagregarlo (gate M1.2).

    Usa un `left join` y **rellena con `sin_actividad`** en vez de dejar nulos: las
    métricas cortan ante nulos en una columna de agrupación (defecto 6 del relevamiento),
    así que una serie sin clasificar tiene que quedar visible como tal y no hacer
    explotar el reporte ni desaparecer de él.
    """
    columnas_clave = [c for c in clasificacion.columns if c not in ("cuadrante", "adi", "cv2")]
    etiquetado = reporte.merge(
        clasificacion[[*columnas_clave, "cuadrante"]], on=columnas_clave, how="left"
    )
    etiquetado["cuadrante"] = etiquetado["cuadrante"].fillna(SIN_ACTIVIDAD)
    etiquetado.attrs = reporte.attrs  # el merge descarta attrs y ahí viaja la Corrida
    return etiquetado
