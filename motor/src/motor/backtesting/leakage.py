"""Verificador de leakage temporal (M1.3) — la red contra el error más letal del motor.

`viabilidad.md` §5 lo lista como riesgo de probabilidad media y **sutil**, y
`plan-diseno.md` §Protocolo lo declara innegociable: para el corte t, el ancla de
deflación y todos los índices se calculan **solo con datos ≤ t**. El ancla "de hoy" del
backtest es el hoy de *ese corte*, no el actual. Deflactar el histórico con el ancla
presente hace que el modelo vea el futuro por vía de los precios, y el síntoma es un
error de backtest sospechosamente bajo — es decir, se manifiesta como una buena
noticia. Por eso hace falta una red automática y no "prestar atención".

**Este módulo se escribió antes que la deflación (M2.1), a propósito.** No verifica una
implementación: verifica una **propiedad**, así que sirve para cualquier candidata,
presente o futura.

La propiedad, en una línea: *si dos datasets coinciden en todo lo anterior o igual al
corte, tienen que producir el mismo resultado en ese corte* — sin importar qué pase
después. De ahí salen las dos variantes que se prueban: **truncar** el futuro (detecta
que se usó la *existencia* de filas futuras) y **perturbar** el futuro (detecta que se
usaron sus *valores*, aunque la selección de filas estuviera bien filtrada). La segunda
es la que atrapa el caso realista: un fallback que resuelve el 25,4% de productos sin
ancla propia (EDA §4) usando un promedio global calculado sobre toda la historia.

Uso, cuando exista el transformador de M2.1:

```python
from motor.backtesting.leakage import verificar_sin_leakage

verificar_sin_leakage(
    lambda datos, corte: TransformadorDeflacion().ajustar(datos, corte).ancla_,
    datos=hecho_producto,
    cortes=generar_cortes(hecho_producto["anio_mes"]),
)
```
"""

from collections.abc import Callable, Sequence

import pandas as pd

FACTOR_PERTURBACION = 7.3
"""Multiplicador aplicado al futuro. Cualquier valor distinto de 1 sirve; se eligió uno
grande y no redondo para que un resultado contaminado sea inconfundible y no se pueda
confundir con ruido de punto flotante."""


class LeakageTemporal(AssertionError):
    """El cálculo miró datos posteriores al corte. Hereda de `AssertionError` para que
    un test que lo deje escapar falle igual."""


def _sin_futuro(datos: pd.DataFrame, corte: pd.Timestamp, columna_fecha: str) -> pd.DataFrame:
    return datos[datos[columna_fecha] <= corte].copy()


def _con_futuro_perturbado(
    datos: pd.DataFrame,
    corte: pd.Timestamp,
    columna_fecha: str,
    columnas_valor: Sequence[str],
    factor: float,
) -> pd.DataFrame:
    perturbado = datos.copy()
    futuro = perturbado[columna_fecha] > corte
    for columna in columnas_valor:
        perturbado.loc[futuro, columna] = perturbado.loc[futuro, columna] * factor
    return perturbado


def _normalizar(resultado) -> pd.DataFrame:
    """Acepta Series o DataFrame y devuelve algo comparable de forma estable."""
    df = resultado.to_frame() if isinstance(resultado, pd.Series) else resultado.copy()
    df = df.sort_index(axis=1)
    return df.sort_values(list(df.columns)).reset_index(drop=True)


def _columnas_valor_por_defecto(datos: pd.DataFrame) -> list[str]:
    """Las columnas de punto flotante.

    En el diccionario del motor los identificadores son `int64` y las magnitudes
    (`unidades`, `revenue`, `precio_prom`) son `float64`, así que esto perturba
    justamente los valores sin tocar las claves. Si un esquema no cumple eso, pasá
    `columnas_valor` explícitamente.
    """
    return list(datos.select_dtypes(include="float").columns)


def verificar_sin_leakage(
    calcular: Callable[[pd.DataFrame, pd.Timestamp], pd.DataFrame | pd.Series],
    datos: pd.DataFrame,
    cortes: Sequence[pd.Timestamp],
    columna_fecha: str = "anio_mes",
    columnas_valor: Sequence[str] | None = None,
    factor_perturbacion: float = FACTOR_PERTURBACION,
) -> None:
    """Verifica que `calcular(datos, corte)` no dependa de nada posterior a `corte`.

    Args:
        calcular: la candidata. Recibe `(datos, corte)` y devuelve el ancla, la tabla
            de índices, las features o lo que sea que deba respetar el corte.
        cortes: se verifica **en todos**. Un leakage puede no manifestarse en algunos
            (por ejemplo si el último corte casi no tiene futuro por delante).

    Raises:
        LeakageTemporal: con el corte y la variante que lo delató.
    """
    if columnas_valor is None:
        columnas_valor = _columnas_valor_por_defecto(datos)
    if not columnas_valor:
        raise ValueError(
            "No hay columnas de valor para perturbar: pasá `columnas_valor` "
            "explícitamente, si no la verificación solo detectaría leakage por "
            "existencia de filas y no por sus valores"
        )

    for corte in cortes:
        referencia = _normalizar(calcular(datos, corte))
        variantes = {
            "truncando el futuro": _sin_futuro(datos, corte, columna_fecha),
            "perturbando los valores del futuro": _con_futuro_perturbado(
                datos, corte, columna_fecha, columnas_valor, factor_perturbacion
            ),
        }

        # Se prueban las dos variantes antes de cortar, en vez de fallar en la primera:
        # *cuáles* fallan es el diagnóstico. Si falla solo el truncado, el cálculo usa la
        # existencia de filas futuras (un conteo, un rango, un reindex) pero no sus
        # valores; si además falla la perturbación, está leyendo los valores.
        fallas: dict[str, AssertionError] = {}
        for descripcion, variante in variantes.items():
            try:
                pd.testing.assert_frame_equal(
                    referencia, _normalizar(calcular(variante, corte)), check_dtype=False
                )
            except AssertionError as error:
                fallas[descripcion] = error

        if fallas:
            raise LeakageTemporal(_mensaje(corte, fallas)) from next(iter(fallas.values()))


def _mensaje(corte, fallas: dict[str, AssertionError]) -> str:
    uso = (
        "está leyendo los valores del futuro"
        if any("perturbando" in d for d in fallas)
        else "usa la existencia de filas futuras (un conteo, un rango, un reindex) "
        "aunque no lea sus valores"
    )
    detalle = "\n".join(f"  - al {d}: {e}" for d, e in fallas.items())
    return (
        f"LEAKAGE TEMPORAL en el corte {pd.Timestamp(corte).date()}: el resultado cambia "
        f"{' y '.join(fallas)}, así que el cálculo {uso}. Para el corte t solo se pueden "
        f"usar filas con fecha <= t (plan-diseno.md §Protocolo, ADR-002).\n{detalle}"
    )
