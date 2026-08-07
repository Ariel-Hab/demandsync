"""Bottom-up y MinT sobre la estructura agrupada, con covarianza **prospectiva** (M3.1).

**La trampa fina de la unidad, y está en §7.2 punto 2.** MinT pondera los niveles por la
covarianza de los residuos. Estimarla con todos los cortes del backtest mete exactamente el
hindsight que ADR-016 le sacó al piso — y esta vez sería mucho más difícil de ver, porque no
queda en una elección de modelo visible en una tabla sino adentro de una matriz de pesos.
Por eso el recorte `anio_mes <= corte` **vive acá adentro** y no en el script que llama: una
regla que depende de que el llamador se acuerde no es una regla, es una convención.

**Los cuatro métodos, y por qué esos.** `BottomUp` es el piso a batir de la unidad: sale
gratis de sumar las predicciones de producto que los checkpoints ya tienen, así que MinT
tiene que ganarle *a él* para justificar predecir 296 series agregadas más. Las tres
variantes de `MinTrace` forman una escalera por cuánta información piden:

| método | qué necesita | comentario |
|---|---|---|
| `bottom_up` | nada | el piso |
| `ols` | nada | asume varianzas iguales en todos los niveles |
| `wls_struct` | nada | pondera por cuántas hojas cuelgan de cada serie |
| `mint_shrink` | residuos | el que usa la covarianza, y el único con riesgo de hindsight |

Que los tres primeros no necesiten residuos no es un detalle: si `mint_shrink` no le gana a
`wls_struct`, la covarianza no está aportando y la unidad se cierra con el método barato.
"""

from collections.abc import Callable

import numpy as np
import pandas as pd
from hierarchicalforecast.core import HierarchicalReconciliation
from hierarchicalforecast.methods import BottomUp, MinTrace

from .estructura import Estructura

METODOS: dict[str, Callable[[], object]] = {
    "bottom_up": BottomUp,
    "ols": lambda: MinTrace(method="ols"),
    "wls_struct": lambda: MinTrace(method="wls_struct"),
    "mint_shrink": lambda: MinTrace(method="mint_shrink"),
}
"""**Fábricas, no instancias, y no es estilo: reusar una instancia rompe la salida.**

`HierarchicalReconciliation.reconcile` **muta** el objeto reconciliador — le guarda el estado
ajustado (`P`, `W`, `y_hat`, `fitted`, `sampler`) en su `__dict__`— y `core._build_fn_name`
arma el nombre de la columna de salida **leyendo ese mismo `__dict__`**. La primera llamada
devuelve `modelo/BottomUp`; la segunda, con la instancia ya usada, devuelve
`modelo/BottomUp_intervals_method-None_P-[[...]]_W-[[...]]_fitted-True` con las matrices
enteras serializadas en el nombre.

Como acá se reconcilia **un corte por vez en un bucle**, una instancia compartida haría que
el corte 1 saliera bien y del 2 en adelante no se encontrara la columna. Se instancian de
cero en cada corte."""

NECESITAN_RESIDUOS = frozenset({"mint_shrink"})

HORIZONTE_DE_RESIDUOS = 1
"""Los residuos salen de las predicciones a **h=1**, una por (serie, mes).

Dos motivos. (a) El panel de residuos tiene que tener una sola fila por `(serie, mes)` y el
backtest produce hasta 12 —el mismo mes predicho desde 12 cortes distintos—; quedarse con
h=1 es la convención estándar de MinT y la única que da una serie temporal sin duplicados.
(b) Es lo más parecido a un residuo in-sample que un rolling-origin puede ofrecer sin mirar
el futuro."""


def _matriz_de_residuos(
    observable: pd.DataFrame,
    estructura: Estructura,
    columna_modelo: str,
    columna_serie: str,
    columna_fecha: str,
) -> pd.DataFrame:
    """El `Y_df` que `mint_shrink` espera: `unique_id` índice, `ds`, `y` y la columna del
    modelo, con **solo** las filas ya observadas al corte.

    Se descartan los meses en que alguna serie no tiene residuo en vez de rellenarlos con
    cero: un cero es un residuo perfecto y le diría a MinT que esa serie es la más confiable
    de todas, justo donde no hay dato. Es la misma lógica por la que `metricas.wape` expone
    `cobertura` en vez de contar las celdas vacías como aciertos (§6.7 punto 3).
    """
    del_horizonte = observable[observable["horizonte"] == HORIZONTE_DE_RESIDUOS]
    ancho_real = del_horizonte.pivot_table(
        index=columna_fecha, columns=columna_serie, values="y", aggfunc="sum"
    )
    ancho_pred = del_horizonte.pivot_table(
        index=columna_fecha, columns=columna_serie, values=columna_modelo, aggfunc="sum"
    )

    series = list(estructura.S.index)
    ancho_real = ancho_real.reindex(columns=series)
    ancho_pred = ancho_pred.reindex(columns=series)
    completos = ancho_real.notna().all(axis=1) & ancho_pred.notna().all(axis=1)
    ancho_real, ancho_pred = ancho_real[completos], ancho_pred[completos]

    if ancho_real.empty:
        return pd.DataFrame(columns=[columna_fecha, "y", columna_modelo])

    largo = (
        ancho_real.stack().rename("y").reset_index()
        .merge(
            ancho_pred.stack().rename(columna_modelo).reset_index(),
            on=[columna_fecha, columna_serie],
        )
    )
    return largo.set_index(columna_serie)


def reconciliar(
    base: pd.DataFrame,
    estructura: Estructura,
    columna_modelo: str,
    metodos: list[str] | None = None,
    columna_serie: str = "unique_id",
    columna_fecha: str = "ds",
    columna_corte: str = "corte",
) -> pd.DataFrame:
    """Reconcilia corte por corte y devuelve una columna por método.

    `base` es largo y trae, por cada `(serie, corte)`, las predicciones del horizonte
    (`columna_modelo`), el real (`y`) y el `horizonte`. Se devuelve la misma forma con una
    columna extra por método —`pred_bottom_up`, `pred_mint_shrink`, …— para que
    `backtesting.reporte` y `backtesting.comparacion` la consuman sin cambios, que es lo que
    hizo barata a M3.1a.

    **La regla prospectiva.** Para el corte `t`, la covarianza se estima **solo** con filas
    cuyo `columna_fecha <= t`. Un pronóstico emitido en `t-1` a h=12 recién sirve de residuo
    cuando su mes llega; hasta entonces nadie sabe si acertó. Es literalmente el mismo filtro
    de `modelado.seleccion.elegir_mejor_por_corte`, por el mismo motivo.

    **Las celdas sin pronóstico entran en 0 y salen en `NaN`.** El champion tiene nulos a
    propósito —`armar_reporte_con_cascada` no inventa donde ningún candidato predijo, que son
    las altas de catálogo de §5.6.1— y `hierarchicalforecast` rechaza una `Y_hat_df` con
    nulos. Se rellenan con 0 para poder reconciliar, que además es lo que ya hacían
    implícitamente las tablas de M2.3/M2.5 al agregar por categoría (`sum` saltea nulos, o sea
    los cuenta como 0), y **se vuelven a enmascarar en la salida** para que todos los
    contendientes se midan sobre exactamente las mismas celdas. Publicar ahí el 0 relleno
    inflaría la cobertura del reconciliado y le sumaría error contra un real positivo: la
    comparación quedaría torcida en las dos direcciones.
    """
    metodos = list(metodos) if metodos else list(METODOS)
    desconocidos = sorted(set(metodos) - set(METODOS))
    if desconocidos:
        raise ValueError(f"Métodos desconocidos: {desconocidos}. Disponibles: {sorted(METODOS)}")

    partes = []
    for corte in sorted(base[columna_corte].dropna().unique()):
        del_corte = base[base[columna_corte] == corte]
        # LA regla: solo el error cuyo mes objetivo ya ocurrió al corte.
        observable = base[base[columna_fecha] <= corte]

        # `hierarchicalforecast` rechaza nulos en `Y_hat_df`, y el champion los tiene a
        # propósito: `armar_reporte_con_cascada` deja `NaN` donde **ningún** candidato
        # predijo — las altas de catálogo de §5.6.1, productos cuya primera venta es
        # posterior al corte. Se rellenan con 0 para poder reconciliar y se vuelven a
        # enmascarar al final; ver el docstring de `reconciliar`.
        Y_hat = del_corte[[columna_serie, columna_fecha, columna_modelo]].copy()
        Y_hat[columna_modelo] = Y_hat[columna_modelo].fillna(0.0)
        Y_hat = Y_hat.set_index(columna_serie)
        residuos = _matriz_de_residuos(
            observable, estructura, columna_modelo, columna_serie, columna_fecha
        )

        # Sin residuos observados no se puede estimar covarianza: los métodos que la piden
        # se saltean en ese corte (queda NaN, y `cobertura` lo expone) en vez de caer a una
        # matriz identidad que se leería como si mint hubiera corrido.
        aplicables = [
            m for m in metodos if m not in NECESITAN_RESIDUOS or not residuos.empty
        ]
        # Instancias nuevas en cada corte: ver el docstring de `METODOS`.
        reconciliador = HierarchicalReconciliation(
            reconcilers=[METODOS[metodo]() for metodo in aplicables]
        )
        reconciliado = reconciliador.reconcile(
            Y_hat_df=Y_hat,
            S=estructura.S,
            tags=estructura.tags,
            Y_df=residuos if not residuos.empty else None,
        )

        salida = reconciliado.reset_index()
        renombres = {
            _nombre_de_salida(columna_modelo, metodo): f"pred_{metodo}" for metodo in aplicables
        }
        faltan = sorted(set(renombres) - set(salida.columns))
        if faltan:
            raise RuntimeError(
                f"`hierarchicalforecast` no devolvió {faltan} en el corte {corte}. "
                f"Devolvió {sorted(salida.columns)}; probablemente cambió la convención de "
                "nombres de la librería."
            )
        salida = salida[[columna_serie, columna_fecha, *renombres]].rename(columns=renombres)
        for metodo in metodos:
            if metodo not in aplicables:
                salida[f"pred_{metodo}"] = np.nan
        salida[columna_corte] = corte
        partes.append(salida)

    if not partes:
        return base.copy()

    reconciliado = pd.concat(partes, ignore_index=True)
    resultado = base.merge(
        reconciliado, on=[columna_serie, columna_fecha, columna_corte], how="left"
    )

    # Se devuelve el `NaN` donde el base no tenía pronóstico. Sin esto, esas celdas saldrían
    # con un número —el 0 con que se rellenó, o lo que MinT le reparta— y **la cobertura de
    # los contendientes dejaría de ser igual**: el reconciliado aparecería cubriendo 12.700
    # filas que el champion no cubre, y en `metricas.wape` una predicción de 0 contra un real
    # positivo suma error mientras que una ausente no. La comparación se volvería injusta en
    # las dos direcciones a la vez (§6.7 punto 3).
    sin_base = resultado[columna_modelo].isna()
    for metodo in metodos:
        resultado.loc[sin_base, f"pred_{metodo}"] = np.nan
    return resultado


def _nombre_de_salida(columna_modelo: str, metodo: str) -> str:
    """Cómo nombra `hierarchicalforecast` cada columna reconciliada: `<modelo>/<Reconciler>`.

    `BottomUp` no lleva sufijo de método; `MinTrace` sí, con el `method` entre paréntesis.
    Está acá y no inline porque es la convención de una librería externa: si cambia, cambia
    en un solo lugar y el `RuntimeError` de arriba dice exactamente qué pasó.
    """
    if metodo == "bottom_up":
        return f"{columna_modelo}/BottomUp"
    return f"{columna_modelo}/MinTrace_method-{metodo}"
