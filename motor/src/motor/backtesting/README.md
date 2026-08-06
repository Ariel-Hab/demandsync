# `motor/src/motor/backtesting/` — Arnés de backtesting (M1.1–M1.2, EN CURSO)

Ver diseño completo en [`../../../plan-diseno.md`](../../../plan-diseno.md) §Protocolo de
backtesting y [`../../../roadmap-motor.md`](../../../roadmap-motor.md) §5 (M1). Este README
es la referencia rápida de **cómo usar el código**, no repite el diseño.

> ## Estado: M1.0, M1.1, M1.2 y M1.3 cerrados
>
> El relevamiento del 2026-07-27 (`roadmap-motor.md` §5.1) encontró 9 defectos de
> medición; **los 9 están arreglados**, cada uno con su test de regresión. Están
> entregados también la identificación de corridas, el reporte tabular con todos sus
> cortes —incluido el de cuadrante, vía `motor.clasificacion`— y la red anti-leakage.
> 82 tests verdes, ningún `xfail`.
>
> **M1.5/M1.6/M1.7 (2026-07-29):** los baselines de verdad ya corren dentro del arnés
> —`motor.modelado.baselines` (statsforecast) y `motor.modelado.intermitentes`
> (Croston/TSB)— y `motor.modelado.seleccion` elige el mejor por serie vía MASE. Ver su
> propio [README](../modelado/README.md). El arnés sumó además **checkpointing por corte**
> (M1.7a, ver abajo) para que las corridas largas de M1.7/M1.8 sean reanudables.

## Piezas

| Módulo | Qué hace |
|---|---|
| `panel.py` | `densificar(datos, ...)` — **ADR-010**: rellena con cero los meses sin venta, desde la primera venta de cada serie. Paso previo obligatorio a medir. |
| `cortes.py` | `generar_cortes(fechas, n_cortes)` — los puntos de corte rolling-origin, sobre el **calendario**. Sin shuffle, sin k-fold. |
| `arnes.py` | `ejecutar_backtest(datos, predecir, ...)` — el punto de entrada único. Densifica, orquesta cortes y llama a un predictor pluggable. Con `directorio_checkpoint` la corrida es reanudable (M1.7a). |
| `metricas.py` | `wape()`, `sesgo()` (implementación propia) y `mase()` (wrapper de `utilsforecast`; densifica su `train_df`). |
| `intervalos.py` | **M2.4**: `cobertura_empirica()`, `pinball()` y `tasa_de_cruce()` — la calibración del P10–P90, que ADR-015 punto 2 convierte en el compromiso del producto para h=6/h=12. |
| `checkpoints.py` | **M2.5**: `cargar_desde_checkpoints()` relee una corrida ya ejecutada sin predecir nada, y `cruzar_reportes()` cruza dos que compartan `id` (el hash no incluye el predictor). Es lo que hace que comparar el global contra los 7 baselines cueste 45 s en vez de 294 min. |
| `comparacion.py` | **M2.5**: `cabeza_a_cabeza()` y `cabeza_a_cabeza_desagregado()` (el veredicto, con `peso_%`), `wape_por_serie()` y `distribucion_de_mejora()` — **en qué series** gana cada predictor, que es otra pregunta que "cuánto error tiene". |
| `corrida.py` | `Corrida` + `identificar_corrida()` — trazabilidad: `id` = hash de configuración + huella de los datos. |
| `reporte.py` | `construir_reporte()` (juego de tablas por horizonte × nivel × categoría) y `a_markdown()` (lo que se congela en `motor/backtests/`). |
| `leakage.py` | `verificar_sin_leakage()` — **red innegociable** (M1.3) contra el leakage temporal de la deflación. Verifica una propiedad, no una implementación. |

## El contrato del predictor

`ejecutar_backtest` no sabe nada de `statsforecast`, LightGBM ni Croston — eso es
responsabilidad de M1.5/M1.6/M2. Lo único que exige es una función:

```python
def predictor(historia: pd.DataFrame, corte: pd.Timestamp, horizonte_max: int) -> pd.DataFrame:
    ...  # devuelve columnas_id + columna_fecha + al menos una columna de predicción
```

`historia` es **todo** lo que hay en `datos` con fecha ≤ `corte` — nunca más. Ese es el
mecanismo anti-leakage del arnés; las tablas auxiliares se recortan con
`tablas_auxiliares` (ver abajo). Es complementario, no equivalente, a la red de
`leakage.py`: el arnés controla **qué se le entrega** al predictor, y la red controla
**qué usa** un cálculo cuando se le entrega todo.

El predictor puede predecir de más (ej. 12 meses siempre) sin saber cuántos meses
de real van a existir en verdad: `ejecutar_backtest` trunca contra el fin de la
historia. **Ojo:** el mecanismo con que lo hace hoy (inner join contra `datos`)
también borra los meses de demanda cero, que es un defecto grave y no el
comportamiento buscado — ver *Defectos conocidos*.

## Uso mínimo

```python
from motor.datos.archivos import RepositorioArchivos
from motor.backtesting.arnes import ejecutar_backtest
from motor.backtesting.metricas import wape, sesgo, mase

repo = RepositorioArchivos("ruta/a/hechos")
hecho_producto = repo.hecho_venta_mensual_producto()

reporte = ejecutar_backtest(hecho_producto, mi_predictor, n_cortes=18, horizonte_max=12)
# reporte: id_producto, anio_mes, corte, horizonte, real, <col_pred_por_modelo>

# error del grano de las filas (producto), cortado por horizonte
wape(reporte, ["horizonte"], columna_pred="mi_modelo")

# error DEL NIVEL categoría: agrega unidades a categoría×mes y después mide
wape(reporte, ["horizonte"], columna_pred="mi_modelo", columnas_nivel=["categoria"])

# nivel total — la métrica del gate "sesgo global ±5%"
sesgo(reporte, ["horizonte"], columna_pred="mi_modelo", columnas_nivel=[])

mase(reporte, modelos=["mi_modelo"], train_df=hecho_producto)
```

## Checkpointing para corridas largas (M1.7a)

Las corridas de M1.7/M1.8 con los 7 baselines son de horas (medido: el catálogo real
son ~7 h con `n_jobs=8`) y el pool de procesos corre al límite de memoria de la máquina.
Sin checkpoint, morir en la hora 6 significa perder todo.

```python
reporte = ejecutar_backtest(
    hecho_producto, mi_predictor, n_cortes=18, horizonte_max=12,
    directorio_checkpoint="ruta/a/checkpoints",   # apagado por defecto
)
```

Cada corte se persiste a `corte_<AAAA-MM>.parquet` apenas termina; volver a llamar con el
mismo directorio saltea los cortes ya hechos y solo predice los que faltan. El reporte
resultante es idéntico al de una corrida de una sola pasada
(`test_reanudar_a_medias_solo_predice_los_cortes_que_faltan` lo fija).

**La guarda que lo hace seguro:** el directorio lleva un `corrida.json` con el `id` de
corrida —hash de configuración + huella de los datos—, y reanudar con otra configuración o
con otros datos **falla** en vez de mezclar checkpoints ajenos. Ese es el modo en que este
tipo de caché arruina un resultado sin avisar, así que se rechaza explícitamente. Para
rehacer desde cero, borrá el directorio.

Un corte que no produce filas comparables no deja checkpoint: recalcularlo no cuesta nada
y evita un parquet vacío dando vueltas.

Para la tabla completa —la que se congela en `motor/backtests/`— no se llaman las
métricas una por una:

```python
from motor.backtesting.reporte import construir_reporte, a_markdown

tablas = construir_reporte(reporte, columna_pred="mi_modelo", train_df=hecho_producto)
md = a_markdown(tablas, titulo="Piso de baselines — sintético")
```

**Trazabilidad:** el reporte trae la columna `id_corrida` y los metadatos completos en
`reporte.attrs["corrida"]`. Ojo con `.attrs`: pandas lo descarta en varias operaciones
—un `merge` con el catálogo alcanza, verificado— mientras que la columna sobrevive. Si
vas a cruzar el reporte antes de armar las tablas, guardate la `Corrida` y reponela:

```python
corrida = reporte.attrs["corrida"]
reporte = reporte.merge(catalogo, on="id_producto", how="left")
reporte.attrs["corrida"] = corrida    # si no, el reporte sale sin identificar
```

`a_markdown()` avisa arriba del archivo cuando el reporte perdió la trazabilidad, para
que no se congele una tabla anónima por accidente.

Toda métrica devuelve además `n` (filas agregadas) y `cobertura` (fracción con
predicción). **Mirá siempre la cobertura antes de comparar dos tablas:** un
predictor que omite las series difíciles saca mejor WAPE, y sin cobertura las dos
tablas son indistinguibles.

`columnas_nivel` es la distinción que pide ADR-008 ("WAPE por nivel de
agregación"). Sin nivel, se suman errores fila por fila: es el error por SKU, el
que importa para reponer. Con `columnas_nivel=["categoria"]`, se agregan las
unidades y después se mide: es el error de la categoría, el que importa para
planificar. Los dos son correctos y **difieren por un factor de 3 a 4** en este
dataset — no son intercambiables.

Notar que `train_df` de `mase()` es la tabla **cruda** (columna `unidades`), no el
`reporte` del arnés (columna `real`) — son tablas distintas a propósito, `mase()`
tiene un parámetro separado (`columna_objetivo_train`) para no asumir que
comparten nombre. Esto salió de un bug real: al validar contra el dataset
sintético completo, `mase()` fallaba porque asumía `real` en ambos lados.

## Nota de compatibilidad: `utilsforecast.losses.mase` (v0.2.16)

La función acepta `id_col`/`time_col`/`target_col`/`cutoff_col` como parámetros,
pero el join interno contra `train_df` tiene hardcodeado el nombre de columna
`"unique_id"` sin importar qué se pase en `id_col` (ver
`utilsforecast.losses._create_train_with_cutoffs`). Nuestro `mase()` esquiva esto
renombrando a las convenciones nativas (`unique_id`/`ds`/`y`/`cutoff`) antes de
llamar y deshaciendo el rename al volver — no expone el bug hacia afuera. Si se
actualiza `utilsforecast`, vale la pena revisar si esto se corrigió antes de
simplificar el wrapper.

## La red anti-leakage (M1.3) — innegociable

```bash
pytest -m innegociable     # corré esto antes de tocar deflación, features o el arnés
```

El error que cubre es el más sutil del motor (`viabilidad.md` §5): si para el corte t el
ancla de deflación se calcula con datos posteriores a t, el modelo ve el futuro por vía
de los precios. **Su síntoma es un error de backtest bajo**, o sea que se manifiesta
como una buena noticia — de ahí que haga falta una red automática y no buena voluntad.

Se escribió **antes** que la deflación de M2.1, así que no verifica una implementación:
verifica una **propiedad**, y sirve para cualquier candidata futura.

> Si dos datasets coinciden en todo lo anterior o igual al corte, tienen que producir el
> mismo resultado en ese corte.

De ahí las dos variantes que prueba, y por qué prueba las dos antes de cortar: **truncar**
el futuro detecta que se usó la *existencia* de filas futuras (un conteo, un rango, un
reindex), y **perturbar** sus valores detecta que se leyeron. Cuál de las dos falla es el
diagnóstico, así que el mensaje lo dice.

```python
verificar_sin_leakage(
    lambda datos, corte: TransformadorDeflacion().ajustar(datos, corte).ancla_,
    datos=hecho_producto,
    cortes=generar_cortes(hecho_producto["anio_mes"]),
)
```

`tests/test_leakage_deflacion.py` le pasa tres implementaciones **deliberadamente
contaminadas** y verifica que las detecte — un verificador que nunca se probó contra un
caso malo no es una red, es una decoración. La más relevante de las tres es el *fallback
con promedio global*: filtra bien la ventana por producto, pero resuelve los productos
sin ancla propia con un promedio de toda la historia. Importa porque ese camino lo
recorre el 25,4% de los productos activos (EDA §4), no es un caso borde.

Verificada contra el dataset real: el ancla correcta pasa sobre 160.664 filas en 0,11s y
la contaminada se detecta en el primer corte.

## El corte por cuadrante de intermitencia

`construir_reporte()` agrega la tabla en cuanto el reporte traiga una columna
`cuadrante`, y si no la trae `a_markdown()` deja escrita la ausencia. La columna la pone
`motor.clasificacion` (M1.4):

```python
from motor.clasificacion import clasificar_series, etiquetar

reporte = etiquetar(reporte, clasificar_series(hecho_producto))
```

Es la desagregación que más información aporta. Sobre el sintético, con el mismo
predictor, el WAPE a h=1 va de **0,51 en las series suaves a 1,63 en las lumpy** — un
número global de 0,80 esconde una diferencia de 3x. Y es lo que va a decidir el
enrutamiento de método en M1.5/M1.6.

**Cuidado con el corte cuando se use para enrutar** (no para reportar): ahí
`clasificar_series` tiene que recibir `hasta=corte`, si no el modelo elige su método con
información del futuro. La red de `leakage.py` lo verifica, y hay un test que la corre
sobre el clasificador.
- No enruta por cuadrante de intermitencia (Syntetos-Boylan) — eso es **M1.4**.
  Ese corte de reporte lo exige el gate de **M1.2**; moverlo a M1.4 es un cambio
  de alcance que quedó registrado en `roadmap-motor.md` §5.1.
  El clasificador **no es importable** desde el motor hoy: vive en
  `datasets/sintetico/clasificacion.py` y `datasets/` no es un paquete instalable
  (`ModuleNotFoundError: No module named 'datasets'`). Además la dependencia está
  invertida — el código de producción no debe depender de una herramienta de
  desarrollo. M1.4 lo trae al motor y el generador pasa a importarlo de acá.
- No corre ningún baseline real — **M1.5/M1.6**. La evidencia de esta unidad usa
  un predictor "último valor conocido" escrito solo en los tests, no es código
  de producción.
- No valida el anti-leakage del ancla de deflación — **M1.3** (esa deflación ni
  existe todavía, es de M2.1).

## Defectos (relevamiento 2026-07-27)

Todos verificados corriendo contra `datasets/sintetico/salida/hechos/`
(`hecho_venta_mensual_producto`: **160.664** filas, 2.300 productos × 96 meses).
**Causa raíz común de 1, 2, 7-orden y 8: el código trataba la tabla de hechos como
un panel denso de calendario, y es dispersa** — un producto-mes sin venta no tiene
fila (0 filas con `unidades == 0`; densidad 72,8%).

### ✅ Arreglados por ADR-010 (densificación de calendario)

Un solo cambio —`panel.py`, aplicado en `ejecutar_backtest` y en `mase`— cerró
cuatro defectos, porque los cuatro salían de la misma confusión.

| # | Defecto | Antes → después (escala real) |
|---|---|---|
| 1 | El inner join descartaba los meses de demanda cero: WAPE y sesgo quedaban **condicionados a que hubo venta** | Se ignoraba el **30,6%** de los pares producto-mes. Filas comparables 239.512 → **345.000**. WAPE h1 0,528 → **0,804**; sesgo h12 +0,006 → **+0,095** |
| 2 | La escala de MASE es un `shift(seasonality)` **posicional sobre filas**; sobre tabla dispersa no equivale a 12 meses | **68,8%** de las series con el denominador mal por >10% (hasta 9,6x). MASE promedio 1,0550 → **1,0192**, y de 38.166 filas con 74 NaN a **41.400 (= 2.300 × 18) sin NaN ni inf** |
| 7a | `mase()` no ordenaba `train_df` (la lib lo exige): el orden cambiaba el número, y **M4.2 lo habría roto en silencio** | `densificar()` ordena por `(serie, mes)`; verificado invariante ante `train_df` desordenado |
| 8 | `generar_cortes` armaba la grilla con los meses **observados** | Por serie individual (lo que exige M1.7) crasheaba en 19 de 2.300 productos y los "18 cortes mensuales" abarcaban hasta **90 meses**. Ahora salen del calendario |

Verificado además que la densificación respeta ADR-010 al pie: ningún mes anterior
a la primera venta de cada producto, y `precio_prom` **nulo** —no cero— en los
58.745 meses sin venta (un cero contaminaría el índice implícito de la deflación).

### ✅ Arreglados en la segunda pasada

| # | Defecto | Arreglo y evidencia |
|---|---|---|
| 3 | `wape(df, ["categoria"])` no era el WAPE del nivel categoría; sumaba errores de grano producto | Parámetro `columnas_nivel`: agrega cantidades al nivel y después mide. A escala real, mismo predictor: WAPE h1 **producto 0,804 · categoría 0,136 · total 0,081** — el agregado se beneficia de la cancelación, y las tres lecturas son legítimas para usos distintos. `columnas_nivel=[]` habilita el **nivel total**, la métrica del gate "sesgo global ±5%", que antes tiraba `ValueError` |
| 4 | No predecir era gratis, y las métricas no informaban cobertura | El arnés pasó a `left join` desde el real: la celda no predicha queda con predicción nula en vez de desaparecer. Toda métrica devuelve `n` y `cobertura`. Verificado: predictor completo → cobertura 1,0; omitiendo el 60% → **0,391**, ahora visible |
| 5 | No validaba grano ni unicidad: fan-out silencioso | `_validar_grano` sobre `datos` y sobre cada predicción. Verificado con `hecho_venta_mensual_cliente_producto` y el `columnas_id` por defecto: corta con *"tiene grano más fino que ['id_producto', 'anio_mes']: 2.473.321 filas duplicadas"* y sugiere el `columnas_id` correcto |
| 6 | `groupby(dropna=True)` descartaba las filas con NaN de grupo | `_validar_sin_nulos` corta antes de agrupar, señalando la columna y cuántos nulos. Se eligió cortar y no crear un bucket "NaN": el disparador habitual es un cruce que no matcheó, y eso se arregla en el origen |
| 7b | `mase()` no protegía escala 0 | `inf` → NaN. Un solo infinito envenenaba cualquier promedio de la tabla de referencia |
| 9 | Anti-leakage cubría solo `datos` | `tablas_auxiliares` + `columna_fecha_auxiliares`: se recortan a `<= corte` antes de pasárselas al predictor. Las tablas sin columna de fecha (catálogo) pasan enteras. Es prevención para M2.2, que va a usar `cliente_feature` —hoy una foto única de 2026-06— como feature |

Huecos de cobertura que dejaron pasar todo esto: los tres tests originales del
arnés usan **un solo producto con 10 meses densos y consecutivos**. Ninguno tenía
hueco de calendario, varios productos, claves duplicadas, NaN en la columna de
agrupación ni escala de MASE igual a 0. Los defectos 1, 5, 6, 7 y 8 eran
estructuralmente indetectables por esa suite.

### Cómo se arreglaron: tests primero, con marcador estricto

`tests/test_backtesting_defectos_m1_0.py` — un test o más por defecto, cada uno
afirmando el comportamiento **correcto**. Al escribirlos todos fallaban, marcados
`@pytest.mark.xfail(strict=True)`. Ese `strict` es lo que hizo el trabajo: cuando un
fix hacía pasar un test, pytest lo reportaba como FALLO (`XPASS(strict)`) y obligaba
a sacar el marcador junto con el fix. Además, cada test se verificó con
`pytest --runxfail` para confirmar que fallaba **por el defecto** y no por un error de
la prueba — dos fallaban por un bug propio y se corrigieron ahí.

**El mecanismo se pagó solo dos veces.** Al aplicar ADR-010, marcó como FALLO los
tests de los defectos 2, 7-orden y 8, que empezaron a pasar sin que nadie los
tocara: mostró que un cambio arreglaba cuatro defectos, no uno. Y en la misma corrida
dejó a la vista que el test del defecto 1 estaba **mal especificado** — los cortes
pasaron a salir del calendario y el mes de demanda cero que usaba cayó fuera de la
ventana de evaluación. Sin el marcador estricto, ese defecto habría quedado
"arreglado" con un test que no lo probaba.

Hoy no queda ningún marcador: los tests son la suite de regresión. Si aparece un
defecto nuevo, va con su propio test y su propio ciclo rojo→verde, no se agrega un
`xfail` a este archivo.

## Lo que sí quedó verificado

- **El filtro de historia no filtra futuro**: `datos[fecha] <= corte`, comprobado
  producto por corte sobre los 18 cortes del dataset real.
- **El slice de train de MASE no tiene leakage**: `utilsforecast` sí filtra
  `ds <= cutoff` por corte (leído del fuente instalado). El defecto 2 es *cómo*
  calcula la escala, no *con qué datos*.
- **El workaround del bug de `utilsforecast`** (ver abajo) es correcto.
- **Aritmética de `horizonte` y truncado en el borde**: sin off-by-one; el último
  corte deja solo h=1.
- **`wape`/`sesgo` protegen el denominador cero**: 0 infinitos en 239.512 filas.
- **Los cortes rolling-origin sobre la tabla completa** son correctos y ordenados.

## Nota de calendario para cuando se arregle el defecto 1

Densificar hay que hacerlo **desde la primera venta de cada producto**, no desde
el inicio del dataset: un producto que entró al catálogo en 2023 no tuvo "demanda
cero" en 2019. En el sintético da igual (el generador no modela altas de catálogo
a mitad de historia — verificado: las 596 primeras-ventas posteriores al inicio
son todas de 2018, y son intermitencia, no alta), pero en datos reales importa.
Es decisión de diseño: va documentada y probablemente merece ADR.
