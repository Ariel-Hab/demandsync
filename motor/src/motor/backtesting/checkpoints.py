"""Releer corridas ya ejecutadas y cruzarlas entre sí (M2.5).

El champion/challenger de M2.5 necesita, en un solo reporte, las predicciones de los 7
baselines (M1.8) y las del modelo global (M2.3/M2.4). Las dos corridas ya existen en
disco: **el `id` de corrida es hash de configuración + huella de datos y no incluye el
predictor** (`corrida.py`), así que dos corridas sobre los mismos datos y cortes producen
exactamente las mismas filas y se cruzan por `(id_producto, anio_mes, corte, horizonte)`.
Es la contracara de la trampa que documenta `ablaciones_global.py`: el mismo hecho que
obliga a un directorio por variante es el que hace que M2.5 no tenga que reajustar nada.

Sin este módulo, M2.5 costaría **294 min** (los 7 baselines sobre el catálogo real) para
recalcular predicciones que ya están escritas.

**Por qué se relee con `ejecutar_backtest` y no con un `read_parquet` suelto.** El arnés
ya tiene la guarda que hace falta: `_preparar_checkpoint` compara el `id` del manifiesto
contra el de la corrida que se le pide, y si difieren corta. Releyendo por ese camino, el
`id` se **recalcula desde los datos que se van a usar después** (los mismos que alimentan
el MASE de la selección), así que la validación no es "el directorio dice ser X" sino
"estos datos producen X". Un `read_parquet` directo se saltearía eso y cruzaría checkpoints
de otro extract sin una sola excepción.

El predictor que se le pasa está **prohibido**: si el arnés lo invoca es que a los
checkpoints les falta un corte, y eso hay que verlo, no completarlo en silencio con una
corrida parcial de horas.
"""

from pathlib import Path

import pandas as pd

from .arnes import ejecutar_backtest

CLAVES_DE_CRUCE = ("id_producto", "anio_mes", "corte", "horizonte")
"""Grano del reporte del arnés. Es la clave con la que dos corridas de la misma `Corrida`
se cruzan fila a fila."""

COLUMNAS_NO_MODELO = ("real", "id_corrida")
"""Columnas del reporte que no son predicciones de un modelo. Todo lo demás que no sea
clave se trata como columna de modelo y se lleva al reporte cruzado."""


def _predictor_prohibido(historia: pd.DataFrame, corte: pd.Timestamp, *_: object) -> pd.DataFrame:
    """Se invoca solo si falta un checkpoint, y en ese caso corta.

    La alternativa —dejar que prediga— convertiría una relectura de segundos en una
    corrida de horas y, peor, produciría un reporte mitad checkpoint y mitad recalculado
    sin que nada lo distinga del completo.
    """
    raise ValueError(
        f"Falta el checkpoint del corte {corte.date()}: la corrida guardada no cubre los "
        "cortes pedidos. Relanzá la corrida original con `--checkpoint-dir` en vez de "
        "completarla desde acá — este camino no predice."
    )


def cargar_desde_checkpoints(
    datos: pd.DataFrame,
    directorio: str | Path,
    n_cortes: int = 18,
    horizonte_max: int = 12,
    columnas_id: list[str] | None = None,
    columna_fecha: str = "anio_mes",
    columna_objetivo: str = "unidades",
    densificar_calendario: bool = True,
) -> pd.DataFrame:
    """Reconstruye el reporte de una corrida ya ejecutada, sin predecir nada.

    `datos` y la configuración tienen que ser **los de la corrida original**: de ahí sale
    el `id` que el arnés compara contra el manifiesto del directorio. Si no coinciden, la
    lectura falla con el mensaje de `_preparar_checkpoint` — que es el comportamiento
    querido: significa que el extract o los cortes cambiaron y que ese cruce habría
    mezclado dos universos distintos.

    Devuelve el reporte largo completo, con `id_corrida` y `.attrs["corrida"]`, igual que
    si se hubiera corrido de cero. Los metadatos vienen de recalcular la `Corrida`, no de
    leer el manifiesto (que solo guarda `id` y fecha), así que la tabla congelada que salga
    de acá tiene la trazabilidad completa.
    """
    directorio = Path(directorio)
    if not directorio.exists():
        raise ValueError(f"No existe el directorio de checkpoints {directorio}")

    return ejecutar_backtest(
        datos,
        _predictor_prohibido,
        n_cortes=n_cortes,
        horizonte_max=horizonte_max,
        columnas_id=columnas_id,
        columna_fecha=columna_fecha,
        columna_objetivo=columna_objetivo,
        densificar_calendario=densificar_calendario,
        directorio_checkpoint=directorio,
    )


def columnas_de_modelo(
    reporte: pd.DataFrame, claves: tuple[str, ...] = CLAVES_DE_CRUCE
) -> list[str]:
    """Las columnas de predicción: todo lo que no es clave ni `real`/`id_corrida`."""
    excluidas = set(claves) | set(COLUMNAS_NO_MODELO)
    return [columna for columna in reporte.columns if columna not in excluidas]


def _validar_una_corrida(nombre: str, reporte: pd.DataFrame, claves: tuple[str, ...]) -> str:
    faltantes = (set(claves) | {"real", "id_corrida"}) - set(reporte.columns)
    if faltantes:
        raise ValueError(f"El reporte '{nombre}' no tiene las columnas {sorted(faltantes)}")

    ids = reporte["id_corrida"].unique()
    if len(ids) != 1:
        raise ValueError(
            f"El reporte '{nombre}' mezcla {len(ids)} corridas ({sorted(ids)[:3]}...): "
            "un reporte cruzable viene de una sola."
        )

    duplicadas = reporte.duplicated(subset=list(claves), keep=False)
    if duplicadas.any():
        ejemplo = reporte.loc[duplicadas, list(claves)].iloc[0].to_dict()
        raise ValueError(
            f"El reporte '{nombre}' tiene {int(duplicadas.sum())} filas duplicadas para "
            f"{list(claves)} (ej. {ejemplo}): el cruce las multiplicaría."
        )
    return str(ids[0])


def cruzar_reportes(
    reportes: dict[str, pd.DataFrame],
    claves: tuple[str, ...] = CLAVES_DE_CRUCE,
) -> pd.DataFrame:
    """Cruza reportes de **la misma corrida** en uno solo con todas las columnas de modelo.

    `reportes` es `nombre -> reporte`; el nombre solo se usa en los mensajes de error, que
    es donde importa saber cuál de los dos directorios está mal.

    Corta —no avisa— ante cualquiera de estas cuatro, porque las cuatro producen una tabla
    con cara de válida:

    1. **`id_corrida` distinto entre reportes.** Son otros datos u otros cortes; las filas
       cruzarían por casualidad donde los productos se llamen igual.
    2. **Claves que no están en los dos.** Una comparación sobre la intersección le da
       ventaja al modelo que predijo menos filas, que es exactamente el sesgo por omisión
       que §5.6.1 midió en el piso retrospectivo.
    3. **`real` distinto para la misma clave.** El `id` coincide pero la verdad contra la
       que se mide no: no hay comparación posible.
    4. **Columnas de modelo con el mismo nombre.** Un `pred` en los dos lados saldría como
       `pred_x`/`pred_y` y la selección elegiría la que quedó primera, en silencio.

    No valida que los reportes vengan de predictores distintos: cruzar una corrida consigo
    misma es legítimo (falla por (4) si trae modelos, y es un no-op si no).
    """
    if len(reportes) < 2:
        raise ValueError(f"Hacen falta al menos dos reportes para cruzar, llegaron {len(reportes)}")

    ids = {nombre: _validar_una_corrida(nombre, r, claves) for nombre, r in reportes.items()}
    distintos = set(ids.values())
    if len(distintos) > 1:
        detalle = " · ".join(f"{nombre}: {id_}" for nombre, id_ in ids.items())
        raise ValueError(
            f"Los reportes son de corridas distintas ({detalle}). El `id` es hash de "
            "configuración + datos: si difiere, cambiaron los cortes o el extract y las "
            "filas no son las mismas aunque el producto se llame igual."
        )

    vistas: dict[str, list[str]] = {}
    for nombre, reporte in reportes.items():
        for columna in columnas_de_modelo(reporte, claves):
            vistas.setdefault(columna, []).append(nombre)
    repetidas = {columna: donde for columna, donde in vistas.items() if len(donde) > 1}
    if repetidas:
        detalle = " · ".join(
            f"{columna} en {donde}" for columna, donde in sorted(repetidas.items())
        )
        raise ValueError(
            f"Hay columnas de modelo repetidas entre reportes ({detalle}). Renombralas "
            "antes de cruzar: el merge les pondría sufijo y la selección tomaría una sola "
            "sin avisar."
        )

    nombres = list(reportes)
    cruzado = reportes[nombres[0]][
        [*claves, "real", "id_corrida", *columnas_de_modelo(reportes[nombres[0]], claves)]
    ].copy()

    for nombre in nombres[1:]:
        derecha = reportes[nombre]
        cruzado = cruzado.merge(
            derecha[[*claves, "real", *columnas_de_modelo(derecha, claves)]],
            on=list(claves),
            how="outer",
            indicator=True,
            suffixes=("", "_der"),
        )
        _validar_cruce_completo(cruzado, nombres[0], nombre)
        _validar_real_coherente(cruzado, nombres[0], nombre)
        cruzado = cruzado.drop(columns=["_merge", "real_der"])

    return cruzado.reset_index(drop=True)


def _validar_cruce_completo(cruzado: pd.DataFrame, izquierda: str, derecha: str) -> None:
    conteo = cruzado["_merge"].value_counts()
    solo_izq, solo_der = int(conteo.get("left_only", 0)), int(conteo.get("right_only", 0))
    if solo_izq or solo_der:
        raise ValueError(
            f"El cruce de '{izquierda}' con '{derecha}' no es fila a fila: {solo_izq} filas "
            f"solo en el primero y {solo_der} solo en el segundo. Comparar sobre la "
            "intersección premiaría al que predijo menos filas."
        )


def _validar_real_coherente(cruzado: pd.DataFrame, izquierda: str, derecha: str) -> None:
    """El `real` tiene que ser el mismo en los dos: es la verdad contra la que se mide.

    Se compara con `NaN == NaN` tratado como igual, porque el arnés deja celdas sin real
    en ninguno de los dos lados por la misma razón (no hay dato), y eso no es discrepancia.
    """
    izq, der = cruzado["real"], cruzado["real_der"]
    difiere = ~((izq == der) | (izq.isna() & der.isna()))
    if difiere.any():
        raise ValueError(
            f"'{izquierda}' y '{derecha}' declaran distinto `real` en "
            f"{int(difiere.sum())} filas pese a compartir `id_corrida`. Una de las dos "
            "corridas se escribió contra otros datos."
        )
