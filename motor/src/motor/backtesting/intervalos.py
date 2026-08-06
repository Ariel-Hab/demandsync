"""Calibración de los intervalos de predicción (M2.4): ¿el P10–P90 cubre de verdad el 80%?

ADR-015 punto 2 convierte este intervalo en **el entregable del producto para h=6/h=12**:
donde el pronóstico puntual tiene demasiada varianza para prometerse como número, lo que se
promete es el rango. Por eso su calibración no es un diagnóstico interno sino el criterio de
aceptación, y de ahí que este módulo mida tres cosas y no una:

| Métrica | Qué contesta | Por qué no alcanza sola |
|---|---|---|
| `cobertura_empirica` | ¿el real cae adentro el 80% de las veces? | se gana con `[0, ∞)` |
| `amplitud_relativa` | ¿cuán ancho es, en escala del real? | uno angosto que no cubre miente |
| `pinball` | pérdida propia de un cuantil | resume las dos en un número comparable |

**Sub-cobertura y sobre-cobertura no son el mismo error.** Un P10–P90 que cubre el 55% le
dice al analista de compras que su riesgo es menor del que es, y se traduce en quiebres de
stock más frecuentes de lo que el sistema promete. Uno que cubre el 98% no miente, pero es
tan ancho que no informa ninguna decisión. Las dos se reportan con el desvío contra el 80%
nominal a la vista (`desvio_vs_nominal`), con signo, para que no se lean como equivalentes.

## Tres decisiones de medición, que cambian el número

**1. El intervalo se evalúa CERRADO: `P10 <= real <= P90`.** Con 42% de series
intermitentes (EDA §3) y el panel densificado a ceros explícitos (ADR-010), el caso más
frecuente del dataset es `real == 0` con un `P10 == 0` — que es la respuesta correcta para
un producto que suele no venderse ese mes. Un intervalo abierto contaría ese acierto como
fallo y la cobertura saldría sistemáticamente pesimista sobre la mayor parte de las filas.

**2. Las filas sin intervalo no cuentan como cubiertas ni como falladas: se excluyen del
cociente y salen en la columna `cobertura`.** Es la misma disciplina de `metricas.py` — sin
ella, un modelo que no predice justo donde es difícil mejora su calibración por omisión.

**3. Solo a grano de predicción (producto). No hay `columnas_nivel`.** No es una omisión:
**la suma de cuantiles no es el cuantil de la suma.** Sumar los P90 de 2.128 productos
supone que a todos les va bien el mismo mes (comonotonicidad) y da un rango absurdamente
ancho para el total; el cuantil de la demanda agregada es más angosto porque los errores se
cancelan. Un intervalo por categoría hay que **predecirlo** a esa altura de la jerarquía
(M3.1, reconciliación), no sumarlo acá. Los cortes por categoría o cuadrante que sí ofrece
este módulo son **desagregados del mismo grano** —promedian coberturas de filas producto-mes
dentro del grupo—, que es cosa distinta y sí es legítima.
"""

import numpy as np
import pandas as pd

from .metricas import _ratio_por_grupo, _validar_sin_nulos

COBERTURA_NOMINAL = 0.8
"""Lo que el P10–P90 promete por construcción (0,9 − 0,1). El gate de M2.4 es reportar la
empírica contra esto; ADR-015 punto 2 lo convierte en el compromiso del producto."""


def _columnas_presentes(df: pd.DataFrame, columnas: list[str]) -> None:
    faltantes = [c for c in columnas if c not in df.columns]
    if faltantes:
        raise ValueError(
            f"el reporte no trae las columnas de cuantil {faltantes}. Corré el predictor con "
            f"`cuantiles=...` (M2.4): sin ellas no hay intervalo que calibrar"
        )


def cobertura_empirica(
    df: pd.DataFrame,
    columnas_grupo: list[str],
    columna_real: str = "real",
    columna_inferior: str = "GlobalLGBM_P10",
    columna_superior: str = "GlobalLGBM_P90",
) -> pd.DataFrame:
    """Fracción de reales dentro de `[inferior, superior]`, con su amplitud y su desvío.

    Devuelve, por grupo: `cobertura_empirica`, `desvio_vs_nominal` (empírica − 0,8, con
    signo), `amplitud_relativa`, `n` y `cobertura`.

    `amplitud_relativa` es `Σ(superior − inferior) / Σ|real|`, el mismo denominador que usa
    `wape()`. Que sea el mismo importa: deja el ancho del intervalo leíble en la misma escala
    que el error del punto, así que un P10–P90 de amplitud 1,2 contra un WAPE de 0,30 se
    puede comparar sin traducir nada.
    """
    columnas_grupo = list(columnas_grupo)
    _validar_sin_nulos(df, columnas_grupo)
    _columnas_presentes(df, [columna_inferior, columna_superior])

    inferior, superior = df[columna_inferior], df[columna_superior]
    real = df[columna_real]
    tiene_intervalo = inferior.notna() & superior.notna()
    # Cerrado a propósito (decisión 1 del encabezado): `real == 0 == P10` es el caso más
    # frecuente del dataset y es un acierto, no un fallo.
    dentro = (real >= inferior) & (real <= superior) & tiene_intervalo

    tabla = _ratio_por_grupo(
        df,
        columnas_grupo,
        numerador=dentro.astype(float),
        denominador=tiene_intervalo.astype(float),
        tiene_prediccion=tiene_intervalo,
        nombre="cobertura_empirica",
    )
    amplitud = _ratio_por_grupo(
        df,
        columnas_grupo,
        numerador=(superior - inferior).where(tiene_intervalo, 0.0),
        denominador=real.abs().where(tiene_intervalo, 0.0),
        tiene_prediccion=tiene_intervalo,
        nombre="amplitud_relativa",
    )
    tabla.insert(
        list(tabla.columns).index("cobertura_empirica") + 1,
        "desvio_vs_nominal",
        tabla["cobertura_empirica"] - COBERTURA_NOMINAL,
    )
    columnas_amplitud = [*columnas_grupo, "amplitud_relativa"]
    if columnas_grupo:
        tabla = tabla.merge(amplitud[columnas_amplitud], on=columnas_grupo)
    else:
        tabla["amplitud_relativa"] = amplitud["amplitud_relativa"].to_numpy()
    return tabla[
        [
            *columnas_grupo,
            "cobertura_empirica",
            "desvio_vs_nominal",
            "amplitud_relativa",
            "n",
            "cobertura",
        ]
    ]


def pinball(
    df: pd.DataFrame,
    columnas_grupo: list[str],
    columnas_cuantil: dict[float, str],
    columna_real: str = "real",
) -> pd.DataFrame:
    """Pérdida pinball por cuantil, normalizada por `Σ|real|`.

    Es la función de pérdida con la que se entrena cada cuantil, y por lo tanto la única
    métrica que lo evalúa como lo que es. Para el cuantil `q`:

        L_q = q · (real − pred)          si real >= pred   (quedarse corto)
              (1 − q) · (pred − real)    si real <  pred   (pasarse)

    Asimétrica: con `q = 0,9` quedarse corto cuesta 9 veces más que pasarse, que es lo que
    empuja al modelo hacia el nivel que la demanda solo supera 1 de cada 10 veces.

    Se normaliza por `Σ|real|` —igual que WAPE— para que sea comparable entre horizontes,
    cuadrantes y corridas en vez de estar dominada por los productos de mayor volumen. Una
    consecuencia útil de eso: **para `q = 0,5` la pinball normalizada es exactamente la mitad
    del WAPE de esa columna**, así que el P50 se compara contra el pronóstico puntual
    multiplicando por 2, sin cambiar de métrica.
    """
    columnas_grupo = list(columnas_grupo)
    _validar_sin_nulos(df, columnas_grupo)
    _columnas_presentes(df, list(columnas_cuantil.values()))

    tablas = []
    for cuantil, columna in sorted(columnas_cuantil.items()):
        error = df[columna_real] - df[columna]
        perdida = np.maximum(cuantil * error, (cuantil - 1.0) * error)
        tiene_prediccion = df[columna].notna()
        tabla = _ratio_por_grupo(
            df,
            columnas_grupo,
            numerador=pd.Series(perdida).where(tiene_prediccion, 0.0),
            denominador=df[columna_real].abs().where(tiene_prediccion, 0.0),
            tiene_prediccion=tiene_prediccion,
            nombre="pinball",
        )
        tabla.insert(0, "cuantil", cuantil)
        tablas.append(tabla)
    return pd.concat(tablas, ignore_index=True)


def tasa_de_cruce(
    df: pd.DataFrame,
    columnas_grupo: list[str],
    columnas_cuantil: dict[float, str],
) -> pd.DataFrame:
    """Fracción de filas donde los cuantiles salen desordenados (`P10 > P50`, `P50 > P90`).

    Los tres modelos se ajustan **por separado**, así que nada les impone monotonía: es
    perfectamente posible que el P10 de una fila quede por encima de su P90. Un cruce no es
    un error de código —es la consecuencia de estimar cada cuantil independiente— pero sí es
    un intervalo que no se puede mostrar, así que se mide antes de decidir si hay que
    reordenar. Reordenar sin haber medido esconde cuán frecuente es el problema.
    """
    columnas_grupo = list(columnas_grupo)
    _validar_sin_nulos(df, columnas_grupo)
    _columnas_presentes(df, list(columnas_cuantil.values()))

    ordenadas = [columna for _, columna in sorted(columnas_cuantil.items())]
    valores = df[ordenadas]
    completas = valores.notna().all(axis=1)
    # `diff` sobre las columnas ya ordenadas por cuantil: un negativo es un cruce. No lleva
    # guarda de completitud **porque no la necesita** —el `NaN` propaga y `NaN < 0` es
    # `False`, así que una fila sin predicción nunca entra al numerador—; la guarda va donde
    # sí cambia el resultado, que es el **denominador**: una fila vacía no es una fila que
    # pudo cruzarse. Agregarla también acá sería decoración, y una mutación lo destapó.
    cruza = (valores.diff(axis=1).iloc[:, 1:] < 0).any(axis=1)

    return _ratio_por_grupo(
        df,
        columnas_grupo,
        numerador=cruza.astype(float),
        denominador=completas.astype(float),
        tiene_prediccion=completas,
        nombre="tasa_de_cruce",
    )


def construir_tablas_de_intervalos(
    reporte: pd.DataFrame,
    columnas_cuantil: dict[float, str],
    horizontes: tuple[int, ...] = (1, 3, 6, 12),
    columna_categoria: str = "categoria",
    columna_cuadrante: str = "cuadrante",
    columna_real: str = "real",
) -> dict[str, pd.DataFrame]:
    """El juego de tablas de M2.4, con los mismos cortes que exige el gate de M1.2.

    `columnas_cuantil` mapea cuantil → columna (ej. `{0.1: "GlobalLGBM_P10", ...}`). El
    intervalo se arma con el **menor y el mayor** de los cuantiles pasados, así que pedir
    `{0.1, 0.5, 0.9}` mide el P10–P90 y el P50 entra solo en la pinball.
    """
    if len(columnas_cuantil) < 2:
        raise ValueError(
            f"hacen falta al menos dos cuantiles para tener un intervalo, llegaron "
            f"{sorted(columnas_cuantil)}"
        )
    inferior = columnas_cuantil[min(columnas_cuantil)]
    superior = columnas_cuantil[max(columnas_cuantil)]

    del_horizonte = reporte[reporte["horizonte"].isin(horizontes)]
    if del_horizonte.empty:
        raise ValueError(
            f"El reporte no tiene ninguna fila en los horizontes {horizontes}: "
            f"tiene {sorted(reporte['horizonte'].unique())}"
        )

    def _cobertura(columnas_grupo: list[str]) -> pd.DataFrame:
        return cobertura_empirica(
            del_horizonte,
            columnas_grupo,
            columna_real=columna_real,
            columna_inferior=inferior,
            columna_superior=superior,
        )

    tablas = {
        "intervalos_por_horizonte": _cobertura(["horizonte"]).merge(
            tasa_de_cruce(del_horizonte, ["horizonte"], columnas_cuantil).drop(
                columns=["n", "cobertura"]
            ),
            on="horizonte",
        ),
        "pinball_por_horizonte": pinball(
            del_horizonte, ["horizonte"], columnas_cuantil, columna_real=columna_real
        ),
    }
    for columna, nombre in (
        (columna_cuadrante, "intervalos_por_cuadrante"),
        (columna_categoria, "intervalos_por_categoria"),
    ):
        if columna in del_horizonte.columns:
            tablas[nombre] = _cobertura([columna, "horizonte"])
    return tablas
