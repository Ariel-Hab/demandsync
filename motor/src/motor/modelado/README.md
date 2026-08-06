# `motor/src/motor/modelado/` — Baselines, selección y modelo global (M1.5–M1.9, M2.3)

Ver diseño completo en [`../../../plan-diseno.md`](../../../plan-diseno.md) §M1 y
[`../../../roadmap-motor.md`](../../../roadmap-motor.md) §5. Este README es la
referencia rápida de **cómo usar el código**.

## Piezas

| Módulo | Qué hace |
|---|---|
| `baselines.py` | `predecir_baselines(...)` — M1.5: `SeasonalNaive`, `WindowAverage`, `AutoETS`, `AutoTheta`, `AutoARIMA` vía `statsforecast`. |
| `intermitentes.py` | `predecir_intermitentes(...)` — M1.6: `CrostonSBA`, `TSB` vía `statsforecast`. |
| `seleccion.py` | M1.7 + M1.9: `predecir_todos_los_candidatos` (los 7 juntos, un solo pase del arnés), las **dos** selecciones (`elegir_mejor_por_serie` retrospectiva, `elegir_mejor_por_corte` prospectiva) y sus armadores de `pred`. |
| `modelo_global.py` | `predecir_global(...)` — M2.3: LightGBM global con `mlforecast`, multi-horizonte **directo**. El primer modelo del motor. |

Los tres predictores cumplen el contrato `PredictorFn` de `motor.backtesting.arnes`
(ver `backtesting/README.md`): se pasan directo a `ejecutar_backtest`.

**Nada enruta por cuadrante, a propósito.** `baselines.py` e `intermitentes.py` corren
sobre toda serie que reciban, y la selección de M1.7 hace competir a los **7 candidatos
libres en cada serie**: el cuadrante de `motor.clasificacion` (M1.4) se usa para
desagregar el reporte, no para filtrar qué modelos se prueban. Decide el MASE medido, no
una regla de enrutamiento fija — y así, si un candidato nunca gana en un cuadrante, esa
ausencia queda documentada en la tabla congelada en vez de estar oculta de antemano.

```python
from motor.backtesting.arnes import ejecutar_backtest
from motor.datos.archivos import RepositorioArchivos
from motor.modelado.seleccion import (
    armar_reporte_seleccionado, elegir_mejor_por_serie, predecir_todos_los_candidatos,
)

repo = RepositorioArchivos("ruta/a/hechos")
hechos = repo.hecho_venta_mensual_producto()

# un solo pase del arnés con los 7 candidatos
reporte = ejecutar_backtest(hechos, predecir_todos_los_candidatos, n_cortes=18, horizonte_max=12)
corrida = reporte.attrs["corrida"]          # guardala: los merges de abajo descartan .attrs

ganadores = elegir_mejor_por_serie(reporte, train_df=hechos)   # id_producto -> modelo_ganador
seleccionado = armar_reporte_seleccionado(reporte, ganadores)  # agrega la columna `pred`
```

La tabla congelable se genera con
[`../../../scripts/congelar_baselines_sintetico.py`](../../../scripts/congelar_baselines_sintetico.py),
que orquesta exactamente eso más el reporte y sus desagregados.

## Dos criterios de selección, y el que vale para comparar es el prospectivo

`elegir_mejor_por_serie` elige el ganador con el MASE de **todos** los cortes y lo aplica
también a los más viejos: la elección de *qué modelo* usar mira información posterior a
las filas donde se mide. No es el leakage de M1.3 —cada predicción individual sigue viendo
solo historia ≤ corte— pero **no es prospectivo**, y el piso que produce queda más alto que
el de un pipeline real.

**Resuelto en M1.9 (ADR-016).** `elegir_mejor_por_corte` reelige el ganador en cada corte
usando solo el error cuyo mes objetivo ya ocurrió, y `armar_reporte_con_cascada` baja al
siguiente candidato disponible cuando el elegido no cubre una celda. Medido sobre la misma
corrida, sin reajustar un solo modelo:

| | WAPE producto h=1 | cobertura h=12 | sesgo total h=6 |
|---|---|---|---|
| retrospectiva | 0,2870 | 0,8880 | −0,0517 |
| **prospectiva + cascada** | **0,3305** | **0,9104** | **−0,0100** |

Peor WAPE, más cobertura, sesgo dentro del ±5%. El piso viejo reportaba un error **13%
menor** del que un pipeline real puede lograr a grano producto.

**La retrospectiva se conserva** —el piso del 2026-08-03 tiene que seguir siendo
reproducible y varios hallazgos se apoyan en él—, pero **no se comparan entre sí**: son dos
convenciones que dan números distintos sobre los mismos datos.

## Tres gotchas de integración con `statsforecast==1.7.8`

Ninguna está documentada así en la librería; las tres se verificaron corriendo contra
el dataset real antes de escribir el código, no se dedujeron de la documentación.

1. **Columnas exógenas fantasma.** `StatsForecast.forecast(df=...)` interpreta
   cualquier columna del `df` además de id/fecha/objetivo como regresor exógeno
   obligatorio. Pasarle la `historia` completa del arnés (que trae `revenue` y
   `precio_prom`, ver `datos/diccionario.py`) explota pidiendo esas columnas por
   `X_df`. Los dos predictores recortan a las tres columnas necesarias antes de
   llamar — `test_no_rompe_con_columnas_extra_como_revenue_y_precio` es el test de
   regresión.
2. **El id vuelve como índice, no como columna** (hay un `FutureWarning` al respecto,
   con una variable de entorno — `NIXTLA_ID_AS_COL` — para adoptar el comportamiento
   nuevo). El contrato del arnés exige `columnas_id` como columna, así que ambos
   predictores hacen `reset_index()` antes de devolver.
3. **`AutoETS` y `AutoTheta` explotan con series muy cortas.** Verificado: una serie
   de 1 mes tira `IndexError` en `AutoETS`; una de 3 meses tira `ZeroDivisionError` en
   `AutoTheta`. Es el caso real de un producto recién entrado al catálogo en un corte
   temprano — no un caso de laboratorio. `baselines.py` pasa
   `fallback_model=SeasonalNaive(season_length=1)` a `StatsForecast`: la serie corta
   cae a ese fallback y el resto del lote sigue con el modelo real.
   `test_producto_recien_entrado_no_rompe_la_corrida` lo prueba con un producto de
   exactamente 1 mes de historia mezclado con uno de 30.

## El modelo global (M2.3) y sus cuatro trampas

`predecir_global` es LightGBM sobre `mlforecast`, multi-horizonte **directo**
(`max_horizon=h`: un modelo por horizonte, sin realimentar predicciones). Las features son
las de M2.2 — `mlforecast` ejecuta lags/rollings/calendario, `motor.features` construye lo
derivado de la deflación.

**1. Antes que nada: el pin de LightGBM.** Con `lightgbm==4.7.0` en Windows,
`LGBMRegressor.fit` muere con `OSError: access violation` si `pyarrow` se cargó antes — o
sea *siempre* acá, porque la capa de datos lee parquet. No es de los datos: falla igual con
arrays contiguos, sin columnas `category` y con `n_jobs=1`, y `KMP_DUPLICATE_LIB_OK` no lo
arregla. `pyproject.toml` topa en `<4.7` y `tests/test_entorno_lightgbm.py` es la red
(corre un subproceso: **es un crash del binding C, no una excepción de Python**).

**2. Con `max_horizon`, las features se calculan una sola vez, en el origen.**
`core.py::TimeSeries._predict_multi` arma un vector de features y le aplica los `h` modelos.
Coincide con la forma del panel de M2.2 (una fila por origen de pronóstico), y es lo que
hace que el precio aporte señal sin necesitar valores futuros.

**3. `X_df` lleva el precio del CORTE, no el de `corte+1`.** Las exógenas dinámicas se
indexan **por posición** (`rows = arange(_h, len(X_df), h)`), así que:

- un `X_df` desordenado le da a un producto el precio de otro, **sin fallar**;
- arrancar en `corte+1` desalinea entrenamiento y predicción por un mes, **sin fallar**.

En entrenamiento la fila del origen `t` lleva el precio de `t`, así que en predicción tiene
que llevar el del corte. Congelado, además, porque el precio futuro no se conoce y no se
inventa. Lo fijan dos tests; sin ellos una versión nueva de `mlforecast` lo rompe en
silencio.

**4. `precio_ancla` no puede ir en `static_features`, aunque sea estática.** `_fit` valida
que una estática no cambie comparando el primer valor contra el último, con `!=`, y
**`NaN != NaN` es `True`** — así que un producto **sin ancla** (nulo en todas sus filas, o
sea que no cambia) aborta la corrida entera con "its values change over time". Medido: 1 o 2
productos por corte en el sintético estratificado. Viaja por `X_df`, donde el `NaN` llega
intacto a LightGBM como *missing* nativo, en vez de imputarse.

> **Costo:** ~14 s por corte sobre 2.128 productos y 96 meses (h=12, o sea 12 modelos).
> Y **usá `n_jobs=1` en fixtures chicos**: medido, sobre 6 productos el paralelismo por
> defecto cuesta 2,07 s contra 0,15 s — es todo overhead de threads.

## Costo y paralelismo — medido en M1.7, leer antes de largar una corrida grande

Costo por modelo (30 productos reales, un corte, `n_jobs=1`):

| Modelo | Tiempo / producto |
|---|---|
| `SeasonalNaive` / `WindowAverage` | ~0 s |
| `AutoETS` | ~0,05 s |
| `AutoTheta` | ~1,6 s |
| `AutoARIMA` | ~2,9 s |

`AutoARIMA` solo es ~44% del costo de los 7 candidatos juntos (~6 s/producto/corte en
serie).

### `n_jobs` se paga por corte, así que con pocos productos EMPEORA

Medido con `predecir_todos_los_candidatos` sobre el sintético:

| Escenario | `n_jobs=1` | `n_jobs=8` |
|---|---|---|
| 8 productos × 3 cortes | 158 s | **329 s** (2x peor) |
| 100 productos × 2 cortes | — | 326 s |
| 14 workers | — | **crashea** (ver abajo) |

El arnés llama al predictor **una vez por corte**, y cada llamada construye un
`StatsForecast` nuevo → un `ProcessPoolExecutor` nuevo → en Windows (spawn, no fork) cada
worker reimporta `pandas`/`scipy`/`statsforecast` de cero. Ese costo es fijo por corte, no
por producto, así que con pocas series domina todo.

Ajustando `tiempo_por_corte = A + B × n_productos` a las dos mediciones de `n_jobs=8`:

- **A ≈ 105 s/corte** de overhead fijo (son dos pools por corte: uno de `baselines.py` y
  otro de `intermitentes.py`).
- **B ≈ 0,58 s/producto/corte** de cómputo paralelo — contra ~6 s en serie, o sea que el
  paralelismo rinde ~10x en la parte de cómputo.

**Regla práctica:** por debajo de ~180 productos, `n_jobs=1`. Por encima, `n_jobs=8`. A
escala del catálogo completo (2.300 × 18 cortes) el overhead es solo ~7% del total, así
que el paralelismo es obligatorio: **≈7 h con `n_jobs=8` vs ≈69 h en serie**.

### `n_jobs` alto agota el archivo de paginación de Windows y **mata la corrida**

No es un riesgo teórico: pasó las dos veces que se intentó.

| Intento | Qué pasó |
|---|---|
| `n_jobs=14`, 100 productos | Muere en el arranque: `ImportError: DLL load failed [...] El archivo de paginación es demasiado pequeño` → `BrokenProcessPool` |
| `n_jobs=8`, 400 productos, 18 cortes | Sobrevivió 4 cortes (~4,6 min cada uno) y **murió en el 5º** con `BrokenProcessPool` |
| `n_jobs=4`, 400 productos | Es el que se usó para completar la tabla de M1.7 |

Causa: cada worker es un proceso nuevo que carga su propia copia de `scipy` +
`statsforecast` (cientos de MB), y el arnés crea un pool nuevo **por corte** (dos, en
realidad: uno de `baselines.py` y otro de `intermitentes.py`). Sobre 18 cortes son 36
pools y cientos de spawns. No es un problema del motor sino del tamaño del archivo de
paginación de la máquina.

**Regla práctica en esta máquina: `n_jobs=4`.** Si hace falta más, agrandar el archivo de
paginación primero y volver a medir — no subirlo a ciegas.

**Consecuencia para M1.8, aprendida a los golpes:** correr a esta escala **sin
checkpointing es una apuesta perdida**. Usá siempre `--checkpoint-dir` (M1.7a): cuando
esta corrida murió en el corte 5, los 4 cortes hechos estaban en disco y reanudar no
recalculó ninguno.

## Por qué las predicciones de Croston/TSB son planas en el horizonte

No es un bug: ambos métodos modelan una **tasa de demanda de largo plazo**
(intervalo entre ventas × tamaño esperado), no un patrón mes a mes, así que el mismo
número se repite para h=1..12. `test_predicciones_planas_en_el_horizonte` lo fija
como comportamiento esperado.

## Qué mostró la tabla de M1.7 (400 productos, 18 cortes)

Tabla completa en [`../../../backtests/baselines-sintetico-2026-07-30.md`](../../../backtests/baselines-sintetico-2026-07-30.md).
Series ganadas por cada candidato:

| modelo | erratica | intermitente | lumpy | suave | total |
|---|---|---|---|---|---|
| `AutoARIMA` | 26 | 35 | 50 | 16 | **127** |
| `AutoETS` | 31 | 17 | 8 | 45 | **101** |
| `SeasonalNaive` | 14 | 21 | 19 | 3 | **57** |
| `CrostonSBA` | 15 | 6 | 5 | 24 | **50** |
| `AutoTheta` | 6 | 8 | 6 | 6 | **26** |
| `WindowAverage` | 4 | 10 | 10 | 2 | **26** |
| `TSB` | 4 | 3 | 2 | 4 | **13** |

**Los 7 ganan alguna serie y ninguno se lleva más del 32%** — correr un solo modelo para
todo el catálogo habría sido peor para las otras dos terceras partes.

### Croston gana más en `suave` que en `lumpy` — al revés de la teoría

`CrostonSBA` se lleva 24 series suaves y solo 5 lumpy; y en `lumpy` gana `AutoARIMA` la
mitad de las veces. Explicación plausible: Croston predice un valor **plano** (una tasa de
largo plazo), y contra una serie suave y estable eso es un buen predictor; en `lumpy` la
varianza es tan alta que ningún método anda bien y las diferencias de MASE son ruido.

**Por eso los candidatos compiten libres y no se enruta por cuadrante.** La regla "obvia"
—intermitentes a Croston/TSB, el resto a los normales— habría perdido las 24 series suaves
donde Croston es el mejor y habría forzado Croston en 100 series lumpy donde pierde. Si
alguna vez se quiere enrutar para ahorrar cómputo, hay que volver a medir esto primero.
