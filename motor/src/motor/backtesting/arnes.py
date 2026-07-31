"""Arnés de backtesting (M1.1): orquesta cortes rolling-origin + predictor pluggable.

Es el punto de entrada único del backtesting — nada en M1 corre baselines
directamente contra los datos, todo pasa por acá. El contrato del predictor es
intencionalmente angosto (recibe historia + corte + horizonte, devuelve
predicciones) para que enchufar un baseline nuevo (M1.5/M1.6) no toque este módulo.
"""

import json
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from .corrida import Corrida, identificar_corrida
from .cortes import generar_cortes
from .panel import densificar

MANIFIESTO_CHECKPOINT = "corrida.json"
"""Archivo que identifica a qué corrida pertenecen los checkpoints de un directorio."""

PredictorFn = Callable[..., pd.DataFrame]
"""Firma del predictor: `(historia_hasta_el_corte, corte, horizonte_max)` -> DataFrame.

Si se le pasan `tablas_auxiliares` al arnés, la firma lleva un cuarto argumento:
`(historia, corte, horizonte_max, auxiliares)`, donde `auxiliares` es el mismo dict
pero con cada tabla recortada al corte.

El DataFrame devuelto debe tener `columnas_id` + `columna_fecha` + al menos una
columna de predicción, para (o hasta) las fechas corte+1..corte+horizonte_max. No
hace falta que el predictor sepa cuánto real existe en verdad más adelante — el
arnés se queda con las fechas para las que hay real.
"""


def _validar_grano(df: pd.DataFrame, claves: list[str], que_es: str, contexto: str = "") -> None:
    """Corta si `df` no tiene una sola fila por combinación de `claves`.

    Sin esto, el cruce contra las predicciones multiplica filas en silencio y el
    arnés devuelve un WAPE con cara de válido. Caso medido: pasar
    `hecho_venta_mensual_cliente_producto` con el `columnas_id` por defecto daba
    hasta 50 reales contra una sola predicción, sin ninguna excepción.
    """
    duplicadas = df.duplicated(subset=claves, keep=False)
    if not duplicadas.any():
        return
    ejemplo = df.loc[duplicadas, claves].iloc[0].to_dict()
    raise ValueError(
        f"{que_es} tiene grano más fino que {claves}: {int(duplicadas.sum())} filas "
        f"duplicadas para esa clave (ej. {ejemplo}). {contexto}"
    )


def _recortar_auxiliares(
    tablas: dict[str, pd.DataFrame], corte: pd.Timestamp, columna_fecha: str
) -> dict[str, pd.DataFrame]:
    """Recorta cada tabla auxiliar a `<= corte`. Las que no tienen la columna de fecha
    (catálogo, por ejemplo) se pasan enteras: no tienen versión temporal que recortar."""
    return {
        nombre: (tabla[tabla[columna_fecha] <= corte] if columna_fecha in tabla.columns else tabla)
        for nombre, tabla in tablas.items()
    }


def _preparar_checkpoint(directorio: Path, corrida: Corrida) -> None:
    """Crea el directorio de checkpoints y verifica que sea de **esta** corrida.

    Sin esta guarda, reanudar con otra configuración (otros cortes, otro horizonte, otros
    datos) leería checkpoints ajenos y devolvería un reporte mezclado que parece válido.
    Como el `id` de corrida es hash de configuración + huella de datos, alcanza con
    compararlo: si no coincide, la reanudación se rechaza en vez de contaminar el
    resultado.
    """
    directorio.mkdir(parents=True, exist_ok=True)
    manifiesto = directorio / MANIFIESTO_CHECKPOINT

    if manifiesto.exists():
        previo = json.loads(manifiesto.read_text(encoding="utf-8"))
        if previo.get("id") != corrida.id:
            raise ValueError(
                f"{directorio} tiene checkpoints de la corrida {previo.get('id')}, no de "
                f"{corrida.id}: cambió la configuración o los datos. Usá un directorio "
                "nuevo, o borrá este si querés rehacer la corrida desde cero."
            )
        return

    manifiesto.write_text(
        json.dumps({"id": corrida.id, "fecha_ejecucion": corrida.fecha_ejecucion}, indent=2),
        encoding="utf-8",
    )


def _ruta_de_corte(directorio: Path, corte: pd.Timestamp) -> Path:
    return directorio / f"corte_{corte:%Y-%m}.parquet"


def ejecutar_backtest(
    datos: pd.DataFrame,
    predecir: PredictorFn,
    n_cortes: int = 18,
    horizonte_max: int = 12,
    columnas_id: list[str] | None = None,
    columna_fecha: str = "anio_mes",
    columna_objetivo: str = "unidades",
    densificar_calendario: bool = True,
    tablas_auxiliares: dict[str, pd.DataFrame] | None = None,
    columna_fecha_auxiliares: str = "fecha_calculo",
    fecha_ejecucion: str | None = None,
    directorio_checkpoint: str | Path | None = None,
) -> pd.DataFrame:
    """Corre el arnés rolling-origin completo y devuelve un reporte largo.

    Para cada uno de los `n_cortes` cortes: arma `historia` con `datos` <= corte
    (nunca expone nada posterior al predictor — es la garantía anti-leakage de
    esta unidad), invoca `predecir(historia, corte, horizonte_max)`, y cruza el
    resultado contra el real que efectivamente existe hasta corte+horizonte_max.

    `densificar_calendario=True` (ADR-010) rellena con cero los meses sin venta,
    desde la primera venta de cada serie, **antes** de medir. No apagarlo para
    medir: sin ceros explícitos se pierde ~30% de los pares producto-mes, el error
    queda condicionado a que hubo venta y sobre-pronosticar sobre demanda cero se
    vuelve invisible. Está solo para el caso en que `datos` ya venga denso.

    `tablas_auxiliares` son tablas que el predictor necesita además de la serie
    (`cliente_feature`, catálogo, índices). Se recortan a `<= corte` por
    `columna_fecha_auxiliares` antes de pasárselas, y ahí el predictor recibe un
    cuarto argumento. Sin esto el anti-leakage cubría solo `datos`: `cliente_feature`
    es una foto única del último mes, así que un predictor de M2.2 que la usara
    estaría viendo el futuro y el arnés no podría impedirlo. Una tabla sin la columna
    de fecha se pasa entera (es el caso del catálogo, que no tiene versión temporal).

    Devuelve una fila por (id, corte, fecha) con: `columnas_id`, `columna_fecha`,
    `corte`, `horizonte` (1..horizonte_max), `real`, y las columnas de predicción
    que haya devuelto `predecir` (una por modelo). Pensado para alimentar
    `motor.backtesting.metricas` directamente (sus defaults asumen columnas
    `real`/`corte`).

    Las celdas que el predictor **no** predijo quedan en el reporte con predicción
    nula, no se borran: si desaparecieran, omitir las series difíciles mejoraría el
    score sin dejar rastro (medido: el WAPE bajaba de 0,528 a 0,276). La columna
    `cobertura` de las métricas es la que lo delata.

    **Trazabilidad (M1.0 (g)):** el reporte lleva una columna `id_corrida` y los
    metadatos completos en `reporte.attrs["corrida"]` (un `Corrida`). La columna es el
    vínculo durable —sobrevive merges y escrituras a parquet—, mientras que `.attrs`
    de pandas se pierde en varias operaciones; para conservar los metadatos, tomalos
    antes de transformar el reporte. `fecha_ejecucion` se puede fijar para tests
    determinísticos: no entra en el `id`, que es hash de configuración + datos.

    **Checkpointing (M1.7a).** Con `directorio_checkpoint`, cada corte se persiste a
    parquet apenas termina y una corrida interrumpida se reanuda salteando los cortes ya
    hechos. Está pensado para las corridas largas de M1.7/M1.8 (medido: el catálogo real
    con los 7 baselines son horas, y el pool de procesos corre al límite de memoria), no
    para el uso normal — por defecto está apagado y el comportamiento no cambia.

    El directorio lleva un `corrida.json` con el `id`: si se reanuda con otra
    configuración o con otros datos, el `id` no coincide y la corrida **falla** en vez de
    mezclar checkpoints ajenos. Para rehacer desde cero, borrá el directorio.
    """
    columnas_id = list(columnas_id) if columnas_id else ["id_producto"]
    _validar_grano(
        datos,
        columnas_id + [columna_fecha],
        "`datos`",
        "Si son hechos de cliente×producto, pasá columnas_id=['id_cliente', 'id_producto'] "
        "o agregá la tabla al grano que querés medir.",
    )
    if densificar_calendario:
        datos = densificar(
            datos,
            columnas_id=columnas_id,
            columna_fecha=columna_fecha,
            columnas_cero=[columna_objetivo],
        )
    cortes = generar_cortes(datos[columna_fecha], n_cortes=n_cortes)

    # La Corrida se arma acá, antes del loop, porque su `id` es lo que valida los
    # checkpoints: depende solo de la configuración y de los datos, no de los resultados.
    corrida = identificar_corrida(
        datos=datos,
        cortes=cortes,
        n_cortes=n_cortes,
        horizonte_max=horizonte_max,
        columnas_id=columnas_id,
        columna_fecha=columna_fecha,
        columna_objetivo=columna_objetivo,
        densificado=densificar_calendario,
        fecha_ejecucion=fecha_ejecucion,
    )

    checkpoint = Path(directorio_checkpoint) if directorio_checkpoint is not None else None
    if checkpoint is not None:
        _preparar_checkpoint(checkpoint, corrida)

    reportes = []
    for corte in cortes:
        ruta_corte = _ruta_de_corte(checkpoint, corte) if checkpoint is not None else None
        if ruta_corte is not None and ruta_corte.exists():
            reportes.append(pd.read_parquet(ruta_corte))
            continue

        historia = datos[datos[columna_fecha] <= corte]
        if tablas_auxiliares is None:
            predicciones = predecir(historia, corte, horizonte_max)
        else:
            predicciones = predecir(
                historia,
                corte,
                horizonte_max,
                _recortar_auxiliares(tablas_auxiliares, corte, columna_fecha_auxiliares),
            )

        columnas_esperadas = set(columnas_id) | {columna_fecha}
        faltantes = columnas_esperadas - set(predicciones.columns)
        if faltantes:
            raise ValueError(
                f"El predictor no devolvió las columnas {faltantes} para el corte {corte.date()}"
            )
        _validar_grano(
            predicciones,
            columnas_id + [columna_fecha],
            f"la predicción del corte {corte.date()}",
            "Cada serie puede tener una sola predicción por mes; revisá los cruces "
            "aguas arriba del predictor.",
        )

        fin_ventana = corte + pd.DateOffset(months=horizonte_max)
        reales = datos.loc[
            (datos[columna_fecha] > corte) & (datos[columna_fecha] <= fin_ventana),
            columnas_id + [columna_fecha, columna_objetivo],
        ].rename(columns={columna_objetivo: "real"})

        combinado = reales.merge(predicciones, on=columnas_id + [columna_fecha], how="left")
        if combinado.empty:
            # Sin checkpoint: un corte vacío no cuesta nada de recalcular al reanudar, y
            # un parquet vacío haría ida y vuelta de dtypes sin necesidad.
            continue
        combinado["corte"] = corte
        combinado["horizonte"] = (combinado[columna_fecha].dt.year - corte.year) * 12 + (
            combinado[columna_fecha].dt.month - corte.month
        )
        if ruta_corte is not None:
            combinado.to_parquet(ruta_corte, index=False)
        reportes.append(combinado)

    if not reportes:
        raise ValueError("Ningún corte produjo filas comparables entre predicción y real")

    reporte = pd.concat(reportes, ignore_index=True)
    reporte["id_corrida"] = corrida.id
    reporte.attrs["corrida"] = corrida
    return reporte
