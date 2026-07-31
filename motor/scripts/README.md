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
| `--desde` / `--hasta` | Default 2018-07 → último mes **completo**. El mes en curso se excluye siempre: está contablemente abierto y su caída se leería como demanda real |
| `--verificar-mes` | Mes del cross-check. `ninguno` lo saltea (no lo saltees) |

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
- Toda tabla lleva la advertencia de que la selección por serie es **retrospectiva**, así
  que el piso que produce es optimista (`roadmap-motor.md` §12.5).
