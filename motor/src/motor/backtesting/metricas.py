"""Métricas de error del motor (ADR-008): WAPE, MASE y sesgo — nunca MAPE como
métrica interna (se rompe con demanda cero, frecuente a nivel producto-mes).

`wape()` y `sesgo()` son implementación propia; `mase()` delega en `utilsforecast`
— ver la nota de compatibilidad en su docstring.

**Nivel de agregación.** ADR-008 pide "WAPE por nivel de agregación" y
`plan-diseno.md` la tabla por total/categoría/producto. No es lo mismo sumar
errores fila por fila y agruparlos, que agregar las cantidades al nivel y después
medir: el nivel agregado se beneficia de la cancelación de errores entre series
(medido sobre el sintético, factor 3 a 4). Las dos lecturas son legítimas y sirven
para cosas distintas —reponer un SKU vs. planificar una categoría— así que se
piden explícitamente con `columnas_nivel`:

- `columnas_nivel=None` (defecto): error del grano de las filas, agrupado. Es el
  error por producto si el reporte viene del arnés a nivel producto.
- `columnas_nivel=["categoria"]`: agrega unidades a categoría×mes y mide ahí.
- `columnas_nivel=[]`: **nivel total**, la métrica del gate "sesgo global ±5%".

**Cobertura.** Toda métrica devuelve `n` (filas agregadas) y `cobertura` (fracción
con predicción). Sin eso, un predictor que omite las series difíciles mejora su
score sin dejar rastro: omitir el 60% más errático llevaba el WAPE de 0,528 a
0,276 y las dos tablas eran indistinguibles.
"""

import numpy as np
import pandas as pd
from utilsforecast.losses import mase as _mase_utilsforecast

from .panel import densificar


def _validar_sin_nulos(df: pd.DataFrame, columnas: list[str]) -> None:
    """`groupby` descarta en silencio las filas con NaN en la clave de agrupación.

    En una métrica que alimenta un gate eso es inaceptable: en un caso medido, 200 de
    220 unidades reales (91%) y el peor error del set desaparecían del reporte sin
    dejar rastro. Preferimos cortar y que se arregle el cruce de origen — el
    disparador habitual es un `left join` contra el catálogo que no matcheó, o el
    clasificador de cuadrantes de M1.4 devolviendo `sin_actividad`.
    """
    for columna in columnas:
        if columna in df.columns and df[columna].isna().any():
            n = int(df[columna].isna().sum())
            raise ValueError(
                f"la columna de agrupación {columna!r} tiene {n} valores nulos (NaN). "
                f"`groupby` los descartaría en silencio y el reporte quedaría incompleto: "
                f"resolvé el origen (¿un cruce que no matcheó?) o filtralos explícitamente"
            )


def _agregar_al_nivel(
    df: pd.DataFrame,
    columnas_grupo: list[str],
    columnas_nivel: list[str] | None,
    columna_real: str,
    columna_pred: str,
    columna_fecha: str,
    columna_corte: str,
) -> pd.DataFrame:
    """Si se pidió un nivel, suma `real`/`pred` a ese nivel antes de medir.

    Las claves son el nivel + el corte de reporte + el tiempo: el tiempo se preserva
    siempre (cada mes es una observación distinta, no se colapsa).
    """
    if columnas_nivel is None:
        return df

    claves: list[str] = []
    for columna in [*columnas_nivel, *columnas_grupo, columna_fecha, columna_corte]:
        if columna in df.columns and columna not in claves:
            claves.append(columna)
    if not claves:
        return df.assign(**{columna_real: df[columna_real], columna_pred: df[columna_pred]})

    return (
        df.groupby(claves, observed=True)[[columna_real, columna_pred]]
        .sum(min_count=1)
        .reset_index()
    )


def _ratio_por_grupo(
    df: pd.DataFrame,
    columnas_grupo: list[str],
    numerador: pd.Series,
    denominador: pd.Series,
    tiene_prediccion: pd.Series,
    nombre: str,
) -> pd.DataFrame:
    """Agrega numerador/denominador por grupo y devuelve `<nombre>`, `n` y `cobertura`."""
    trabajo = pd.DataFrame(
        {
            "_numerador": numerador.to_numpy(),
            "_denominador": denominador.to_numpy(),
            "_con_prediccion": tiene_prediccion.to_numpy(),
        }
    )
    for columna in columnas_grupo:
        trabajo[columna] = df[columna].to_numpy()

    if columnas_grupo:
        agregado = trabajo.groupby(columnas_grupo, observed=True).agg(
            _numerador=("_numerador", "sum"),
            _denominador=("_denominador", "sum"),
            n=("_numerador", "size"),
            cobertura=("_con_prediccion", "mean"),
        )
    else:  # nivel total sin cortes de reporte: un único número global
        agregado = pd.DataFrame(
            {
                "_numerador": [trabajo["_numerador"].sum()],
                "_denominador": [trabajo["_denominador"].sum()],
                "n": [len(trabajo)],
                "cobertura": [trabajo["_con_prediccion"].mean()],
            }
        )

    agregado[nombre] = agregado["_numerador"] / agregado["_denominador"].replace(0, np.nan)
    resultado = agregado[[nombre, "n", "cobertura"]]
    return resultado.reset_index() if columnas_grupo else resultado


def wape(
    df: pd.DataFrame,
    columnas_grupo: list[str],
    columna_real: str = "real",
    columna_pred: str = "pred",
    columnas_nivel: list[str] | None = None,
    columna_fecha: str = "anio_mes",
    columna_corte: str = "corte",
) -> pd.DataFrame:
    """Weighted Absolute Percentage Error: sum(|real-pred|) / sum(|real|).

    A diferencia de MAPE, una fila con `real == 0` no rompe nada — el resultado solo
    se indefine (NaN) si el grupo entero no tuvo actividad real. Ver el encabezado
    del módulo por `columnas_nivel` y por las columnas `n`/`cobertura`.
    """
    columnas_grupo = list(columnas_grupo)
    _validar_sin_nulos(df, columnas_grupo + list(columnas_nivel or []))
    datos = _agregar_al_nivel(
        df, columnas_grupo, columnas_nivel, columna_real, columna_pred, columna_fecha, columna_corte
    )
    return _ratio_por_grupo(
        datos,
        columnas_grupo,
        numerador=(datos[columna_real] - datos[columna_pred]).abs(),
        denominador=datos[columna_real].abs(),
        tiene_prediccion=datos[columna_pred].notna(),
        nombre="wape",
    )


def sesgo(
    df: pd.DataFrame,
    columnas_grupo: list[str],
    columna_real: str = "real",
    columna_pred: str = "pred",
    columnas_nivel: list[str] | None = None,
    columna_fecha: str = "anio_mes",
    columna_corte: str = "corte",
) -> pd.DataFrame:
    """Sesgo relativo (ADR-008): sum(pred-real) / sum(|real|).

    Positivo = sobre-pronóstico sistemático; negativo = sub-pronóstico. Con
    `columnas_nivel=[]` da el sesgo a **nivel total**, que es el punto 4 de la
    Definición de listo del Release 2 (±5%).
    """
    columnas_grupo = list(columnas_grupo)
    _validar_sin_nulos(df, columnas_grupo + list(columnas_nivel or []))
    datos = _agregar_al_nivel(
        df, columnas_grupo, columnas_nivel, columna_real, columna_pred, columna_fecha, columna_corte
    )
    return _ratio_por_grupo(
        datos,
        columnas_grupo,
        numerador=datos[columna_pred] - datos[columna_real],
        denominador=datos[columna_real].abs(),
        tiene_prediccion=datos[columna_pred].notna(),
        nombre="sesgo",
    )


def mase(
    df: pd.DataFrame,
    modelos: list[str],
    train_df: pd.DataFrame,
    estacionalidad: int = 12,
    columna_id: str = "id_producto",
    columna_fecha: str = "anio_mes",
    columna_real: str = "real",
    columna_corte: str = "corte",
    columna_objetivo_train: str = "unidades",
) -> pd.DataFrame:
    """Mean Absolute Scaled Error contra un naive estacional (ADR-008), vía `utilsforecast`.

    `train_df` es la historia completa (todas las series, todas las fechas) — no
    hace falta pre-cortarla por corte: la función arma internamente, para cada
    corte, la porción de historia con fecha <= corte. Es la tabla cruda del
    repositorio (`hecho_venta_mensual_producto`, columna `unidades`), no el reporte
    del arnés — por eso su columna de objetivo se nombra aparte
    (`columna_objetivo_train`) y no se asume igual a `columna_real`.

    **`train_df` se densifica acá adentro (ADR-010)**, no es responsabilidad del
    llamador. Motivo: `utilsforecast` calcula la escala del naive estacional con un
    desplazamiento de `estacionalidad` **filas**, no de meses. Sobre la tabla cruda
    —que es dispersa— "12 filas atrás" no es "12 meses atrás", y el denominador de
    MASE deja de ser la escala que promete. Medido sobre el sintético, el 68,8% de
    las series tenía la escala mal por más de 10%, hasta 9,6x. Densificado, el
    desplazamiento posicional vuelve a coincidir con el calendario. Densificar además
    ordena por `(serie, mes)`, que `utilsforecast` exige y antes no se garantizaba.

    Una serie de escala cero (constante, o un solo mes de historia) da MASE
    indefinido: se devuelve **NaN, no `inf`**, porque un solo infinito envenena
    cualquier promedio de la tabla de referencia.

    Solo soporta series con **id simple** (una columna). Para cliente×producto (M3)
    hay que armar un id sintético antes de llamar.

    Nota de compatibilidad (utilsforecast 0.2.16): la función de la librería acepta
    parámetros `id_col`/`time_col`/`target_col`/`cutoff_col`, pero el join interno
    contra `train_df` (`_create_train_with_cutoffs`) tiene hardcodeado el nombre de
    columna `"unique_id"` sin importar qué se pase en `id_col` — confirmado leyendo
    el código fuente instalado. Por eso acá renombramos a las convenciones nativas
    de utilsforecast (`unique_id`/`ds`/`y`/`cutoff`) antes de llamarla y deshacemos
    el rename al volver, en vez de exponer ese bug a quien use este wrapper.
    """
    df_nativo = df.rename(
        columns={
            columna_id: "unique_id",
            columna_fecha: "ds",
            columna_real: "y",
            columna_corte: "cutoff",
        }
    )
    train_denso = densificar(
        train_df,
        columnas_id=[columna_id],
        columna_fecha=columna_fecha,
        columnas_cero=[columna_objetivo_train],
    )
    train_nativo = train_denso.rename(
        columns={columna_id: "unique_id", columna_fecha: "ds", columna_objetivo_train: "y"}
    )

    resultado = _mase_utilsforecast(
        df=df_nativo, models=modelos, seasonality=estacionalidad, train_df=train_nativo
    )
    for modelo in modelos:
        resultado[modelo] = resultado[modelo].replace([np.inf, -np.inf], np.nan)
    return resultado.rename(columns={"unique_id": columna_id, "cutoff": columna_corte})
