# `motor/scripts/` — operación del track

Scripts que **corren** el motor para producir entregables del roadmap. No son parte del
paquete `motor` ni los importa el job batch: toda la lógica vive en el paquete, acá solo
hay orquestación y argumentos de línea de comandos.

Diferencia con [`../ejemplos/`](../ejemplos/): los ejemplos son documentación ejecutable
para explorar piezas sueltas y su salida va a `salida/` (gitignorada). Estos scripts
producen artefactos que **se commitean**, como las tablas de `../backtests/`.

> **Excepción, y es la importante:** `extraer_snap.py` produce datos reales del cliente.
> Su salida no se commitea nunca. Ver la sección de abajo.

## `extraer_snap.py` — el extract real (M1.8)

Lee el snap MySQL del cliente y escribe los dos parquets que `RepositorioArchivos`
necesita: `hecho_venta_mensual_producto.parquet` y `catalogo_producto.parquet`.

**Solo corre en la máquina autorizada.** Requiere el extra opcional:

```bash
motor/.venv/Scripts/pip install -e "motor[extract]"
```

### Credenciales: las mismas que cotizaciones, cargadas en la sesión

El script lee `DB_SNAP_URL`, o el conjunto `DB_DFV_PROD_SNAP_HOST / PORT / NAME / USER /
PASS` — exactamente las variables de `cotizaciones/backend/src/core/database_snap.py`.
Es a propósito: el secreto sigue viviendo en un solo lugar y este repo no lo duplica.

```bash
set -a; . /c/ariel/dfv/cotizaciones/.env; set +a
motor/.venv/Scripts/python motor/scripts/extraer_snap.py --salida D:/dfv/extract
```

Si falta la configuración el script corta con el nombre de las variables. **Nunca las
escribas en un archivo dentro de este repo**, ni siquiera en uno gitignoreado.

### ⚠️ La salida son datos reales del cliente

Filas producto × mes del ERP: cae de lleno en la regla de oro de CLAUDE.md §4. El
script **se niega a escribir en una ruta versionada** (lo comprueba con `git
check-ignore`), pero lo correcto es apuntar `--salida` fuera del repo.

Lo único publicable de todo este camino es la tabla agregada de [`../backtests/`](../backtests/).

### Lo que valida antes de darte nada

Un extract mal hecho no falla: produce un piso equivocado. Por eso hay dos redes.

1. **Cross-check pandas vs SQL** (`--verificar-mes`, activo por defecto sobre el último
   mes). Trae los renglones crudos de un mes, los netea con `netear_renglones()` —que sí
   está bajo test— y compara contra lo que devolvió la agregación del servidor. Un join
   mal escrito o un signo invertido se ven acá y no ocho horas después.
2. **Validación contra el EDA** (`../eda/eda-2026-07-15.md`): primer mes 2018-07, meses
   sin huecos, las 12 categorías de `categoria_producto`, y ~2.189 productos activos en
   36m. Lo estructural es fatal; lo cuantitativo es aviso, porque el EDA se corrió en
   otra fecha.

### Argumentos

| Argumento | Por qué |
|---|---|
| `--salida` | Obligatorio. Directorio de los parquets, fuera del repo |
| `--meses-actividad` | Ventana de "producto activo", default 36. Con `0` extrae las ~10.500 entradas del catálogo: cuadruplica el backtest y mete series todo-ceros que **bajan el WAPE sin que nadie prediga mejor** |
| `--desde` / `--hasta` | Default 2018-07 → último mes **completo de calendario**. El mes en curso se excluye siempre: está contablemente abierto y su caída se leería como demanda real. **Ojo: completo de calendario ≠ completo de datos** — ver abajo |
| `--verificar-mes` | Mes del cross-check. `ninguno` lo saltea (no lo saltees) |

### La réplica se atrasa, y el default no lo sabe

`--hasta` mira el calendario, no los datos. El 2026-08-02 la réplica del snap tenía
facturas hasta el 17-07 pero solo **6.410 comprobantes en 2026-06 contra ~14.000
típicos**. Un mes a medio cargar no falla: se lee como derrumbe de demanda, entra al ancla
de deflación (que mira los últimos 3 meses) y es el mes contra el que se evalúa el último
corte del backtest. El extract del 2026-07-31 se lo comió entero.

`detectar_meses_incompletos()` lo corta —es control fatal— y te dice con qué `--hasta`
re-extraer. Mide en **unidades**, no en filas ni revenue: las filas casi no se mueven
(2026-06 dio 0,908 de lo normal) porque siguen apareciendo los mismos productos con menos
transacciones, y el revenue arrastra inflación.

### Universo: qué queda afuera y por qué (ADR-012)

- **Obsequios**, por renglón: `precio > $0,05`. El ERP exige `precio > 0`, así que un
  obsequio se factura con un centinela de $0,01 — 3.638 renglones desde 2018-07. **No se
  corta por producto**: el flag `producto.obsequio` marca 48 en el universo que cargan
  0,92% del revenue, y 12 de ellos venden a precio real.
- **Descontinuados: no se excluyen.** `producto.disabled` es estado de hoy y no tiene
  fecha, así que aplicarlo a cortes históricos sería sesgo de supervivencia. El "." de la
  convención del cliente vive en `descripcion`, no en `id`, y es subconjunto exacto de
  `disabled` — por eso no hay regla propia para él.

### De dónde sale la SQL, y qué NO se copió

La agregación viene de `obtener_ventas_por_periodo()` en
`cotizaciones/backend/src/modules/snap/ventas/repository.py`, que ya corre en producción
contra esta base con los filtros que documenta el EDA. Tres diferencias deliberadas:

1. **Agrupa por producto**, no por cliente × producto. No alcanza con sumar la salida de
   aquélla: su `HAVING cantidad_total != 0` filtra a nivel cliente × producto, así que un
   cliente con neto cero en el mes desaparece y se lleva su revenue puesto.
2. **Sin `HAVING`**: los meses de neto cero se conservan — son demanda cero explícita
   (ADR-010), no ausencia de dato.
3. **El revenue conserva el signo.** Cotizaciones lo anula cuando no es positivo; acá es
   el numerador del índice implícito de precio (ADR-002).

Acoplamiento declarado: un cambio de esquema del ERP rompe dos repos. Es aceptable
porque este extract es **ad-hoc y no el ETL de R1** — el pipeline productivo lo construye
Backend desde el contrato de ingesta, y cualquier diferencia entre ambos es un hallazgo a
documentar, no algo a emparchar acá.

## `congelar_baselines_sintetico.py`

Genera la tabla de referencia de baselines con selección por serie (M1.7 sobre sintético,
M1.8 sobre el extract real).

```bash
# M1.7 — muestra estratificada por cuadrante (lo que decidió roadmap-motor.md §5.2)
motor/.venv/Scripts/python motor/scripts/congelar_baselines_sintetico.py \
    --estratificado 100 --n-jobs 8 --checkpoint-dir /ruta/a/checkpoints

# smoke test rápido antes de una corrida larga
motor/.venv/Scripts/python motor/scripts/congelar_baselines_sintetico.py \
    --n-productos 10 --n-cortes 4 --horizonte-max 3 --n-jobs 1 --salida-dir /tmp

# M1.8 — mismo camino, apuntando al extract real (SOLO en la máquina autorizada)
motor/.venv/Scripts/python motor/scripts/congelar_baselines_sintetico.py \
    --hechos /ruta/al/extract --etiqueta real --n-jobs 8 --checkpoint-dir /ruta/a/checkpoints
```

**Que M1.8 sea el mismo script no es casualidad, es el diseño:** la única diferencia entre
el ensayo y el piso real debe ser `--hechos` y `--etiqueta`. Si al correrlo sobre el
extract hiciera falta cambiar algo más, eso mismo es un hallazgo que va al roadmap.

### Los tres argumentos que importan

| Argumento | Por qué |
|---|---|
| `--n-jobs` | El overhead de paralelizar se paga **por corte**, así que con pocos productos `n_jobs>1` es más lento que serie, y `n_jobs` muy alto mata la corrida por archivo de paginación. Regla y mediciones en [`../src/motor/modelado/README.md`](../src/motor/modelado/README.md) §Costo y paralelismo. El script avisa si el combo pinta mal. |
| `--checkpoint-dir` | Persiste cada corte y permite reanudar (M1.7a). Para cualquier corrida de más de unos minutos, usalo: el pool de procesos corre al límite de memoria y una caída sin checkpoint pierde todo. **Ver la advertencia de datos de abajo.** |
| `--estratificado` | N productos **por cuadrante**, con semilla fija. Da mejores estadísticas por cuadrante que la distribución natural (`lumpy` es ~11%). Distinto de `--n-productos`, que es un recorte arbitrario y queda marcado como no congelable. |

### ⚠️ Los checkpoints NO son publicables

Un checkpoint es el reporte **crudo, fila por fila** (producto × mes × real × predicción
de cada modelo) — no métricas agregadas. En M1.8 eso son datos reales del cliente, así que
cae de lleno en la regla de oro de CLAUDE.md §4: **nunca se commitean**.

Lo único publicable de un backtest es la tabla de [`../backtests/`](../backtests/), que
solo tiene conteos, ratios y porcentajes. El `.gitignore` cubre `motor/checkpoints/`,
`checkpoints/` y `corte_*.parquet`, pero lo más seguro es apuntar `--checkpoint-dir`
**fuera del repo**.

### Al correrlo en background, no lo pipees a `grep`

```bash
# MAL: el exit code que ves es el de grep, no el de python. Una corrida que murió
# con BrokenProcessPool reporta "exit code 0" y parece que salió todo bien.
python scripts/congelar_baselines_sintetico.py ... 2>&1 | grep -v FutureWarning

# BIEN: redirigí a un archivo y revisá el exit code de verdad
python -u scripts/congelar_baselines_sintetico.py ... > corrida.log 2>&1; echo "EXIT=$?"
```

Pasó de verdad al generar la tabla de M1.7. Sumale que `grep` buferiza cuando no escribe
a una terminal, así que además no ves el progreso.

### Lo que el script se niega a hacer en silencio

- Si `--n-cortes <= --horizonte-max`, **corta**: con N cortes el horizonte máximo medible
  es N, así que la tabla no llegaría al h=12 que exige el gate de M1.2 y no avisaría sola
  (trampa de `roadmap-motor.md` §12.2).
- Si la corrida no cubre el catálogo completo, lo **escribe en la tabla** — distinguiendo
  una muestra estratificada deliberada de un recorte arbitrario.
- Toda tabla **declara su criterio de selección** (`--seleccion`, M1.9 / ADR-016) y la
  advertencia **cambia con el flag**: la retrospectiva avisa que el piso es optimista por
  hindsight y que desde M1.9 dejó de ser el piso de M2.5; la prospectiva dice lo contrario
  —que es la tabla comparable— y por qué su WAPE es peor. Dejar el aviso equivocado sería
  afirmar algo falso sobre el propio resultado, que es el modo de falla de §5.6.1.

### Re-congelar el piso sin volver a predecir

Si los checkpoints de la corrida siguen en disco, cambiar el criterio de selección **no
cuesta nada**: el `id` de corrida es hash de configuración + huella de datos y **`n_jobs`
no entra**, así que el mismo comando con `--checkpoint-dir` reusa los 18 cortes y va
derecho a la selección. Es como se produjo el piso de M1.9 — **12 segundos** contra 294 min.

```bash
motor/.venv/Scripts/python motor/scripts/congelar_baselines_sintetico.py \
    --hechos C:/dfv-extract-v2 --etiqueta real-prospectivo \
    --n-cortes 18 --horizonte-max 12 --n-jobs 4 \
    --checkpoint-dir C:/dfv-checkpoints-2026-08-03 --seleccion prospectiva
```

Si el extract cambió, el `id` no coincide y la reanudación **se rechaza**: es la guarda
haciendo su trabajo, no un problema a saltear.

## `ablaciones_global.py` — con qué configuración el global llega a M2.5 (M2.3)

Corre el modelo global de M2.3 en las cuatro combinaciones de sus dos interruptores y emite
la tabla comparativa. **No es un piso ni un champion/challenger**: solo decide con qué
configuración el global se presenta a la comparación de M2.5.

```bash
motor/.venv/Scripts/python motor/scripts/ablaciones_global.py \
    --estratificado 100 --n-cortes 18 --horizonte-max 12 \
    --checkpoint-dir C:/dfv-checkpoints-ablaciones
```

| interruptor | qué aísla |
|---|---|
| `usar_precio` | **qué compró M2.2.** Sin esto, si el global gana no se sabe si fue por las features de precio o a pesar de ellas |
| `escalar_target` | las escalas van de jeringas a vacunas y el modelo es **uno solo**: sin escalar, las series grandes dominan el ajuste |

### El default `--estratificado 100` no es cosmético

Reproduce **la misma muestra** que la tabla de M1.7 (400 productos, semilla 42 —
`roadmap-motor.md` §5.2), usando `motor.clasificacion.muestra_estratificada`, que es la
misma función que llama `congelar_baselines_sintetico.py`. Esa función vive en el paquete y
no en los scripts justamente por esto: dos implementaciones equivalentes que sortean
distinto producen tablas que **parecen** comparables y no lo son.

Con `--estratificado 0` corre el catálogo completo, que es más productos pero **no se
compara** contra la tabla de M1.7.

### ⚠️ Un directorio de checkpoints por variante — no lo unifiques

El `id` de corrida es hash de configuración + datos y **no incluye el predictor**, así que
las cuatro variantes generan el **mismo `id`**. Compartir directorio haría que la segunda
"reanude" los checkpoints de la primera y devuelva el reporte de otra configuración sin
avisar — la guarda de `id` no puede detectarlo porque el `id` coincide de verdad. El script
arma un subdirectorio por variante.

Es la contracara del mismo hecho que abarata M2.5: como el `id` no depende del predictor,
una corrida del global sobre los mismos datos y cortes es **mergeable fila a fila** contra
el reporte de baselines ya congelado, sin re-correr los 7.

## `global_vs_baselines.py` — champion/challenger contra el piso (M2.5)

Cruza dos corridas **ya ejecutadas** y emite el reporte comparativo. **No reajusta ningún
modelo**: la corrida real completa son **45 segundos**.

```bash
motor/.venv/Scripts/python motor/scripts/global_vs_baselines.py \
    --hechos C:/dfv-extract-v2 --etiqueta real --estratificado 0 \
    --checkpoints-baselines C:/dfv-checkpoints-2026-08-03 \
    --checkpoints-global    C:/dfv-checkpoints-intervalos
```

Los tres contendientes: `piso` (7 baselines, selección prospectiva + cascada), `global`
(`GlobalLGBM` en todas las series, sin selección) y `champion` (los 9 candidatos
compitiendo). `global_P50` va de cuarto, para contrastar. **El champion se elige con la
misma regla que el piso** —por corte, con lo ya observado— porque darle trato retrospectivo
inclinaría la cancha a su favor (ADR-016 punto 4).

### Por qué cuesta 45 segundos

El `id` de corrida es hash de configuración + datos y **no incluye el predictor**, así que
dos corridas sobre los mismos datos y cortes tienen exactamente las mismas filas y se cruzan
por `(producto, mes, corte, horizonte)`. Es la contracara del hecho que obliga a un
directorio por variante en `ablaciones_global.py`. Rehacer las corridas costaría 294 min de
baselines más 19 de global.

La relectura pasa por `ejecutar_backtest` con un **predictor prohibido**: si el arnés lo
invoca es que a los checkpoints les falta un corte, y ahí corta. Completar en silencio
daría un reporte mitad checkpoint mitad recalculado, indistinguible del completo.

### Para el sintético hay que producir los checkpoints primero

El script solo cruza; no corre modelos. Sobre sintético eso significa tres pasos, y **el
`--estratificado` tiene que ser el mismo en los tres** o el `id` no coincide:

```bash
motor/.venv/Scripts/python motor/scripts/congelar_baselines_sintetico.py \
    --estratificado 100 --n-jobs 4 --seleccion prospectiva \
    --checkpoint-dir C:/dfv-checkpoints-m25-sint-baselines          # ~90 min
motor/.venv/Scripts/python motor/scripts/intervalos_global.py \
    --estratificado 100 --checkpoint-dir C:/dfv-checkpoints-m25-sint-global
motor/.venv/Scripts/python motor/scripts/global_vs_baselines.py \
    --etiqueta sintetico \
    --checkpoints-baselines C:/dfv-checkpoints-m25-sint-baselines \
    --checkpoints-global    C:/dfv-checkpoints-m25-sint-global
```

⚠️ **No sirve reusar `baselines-sintetico-2026-07-30.md` ni sus checkpoints**: se congelaron
antes de que T0.4 reescribiera el generador, así que son de otro dataset (§6.4).

### Lo que el script se niega a hacer en silencio

- **Cruzar corridas con `id` distinto** — son otros datos u otros cortes, y las filas
  cruzarían por casualidad de nombre.
- **Cruzar sobre la intersección.** Si una clave no está en los dos reportes, corta: comparar
  sobre lo común premia al que predijo menos filas, que es el sesgo por omisión de §5.6.1.
- **Aceptar un `real` distinto** para la misma clave, aunque el `id` coincida.
- **Sufijar columnas de modelo repetidas.** Un `pred` en los dos lados saldría `pred_x`/
  `pred_y` y la selección tomaría una sola sin avisar.
