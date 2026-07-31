# Roadmap del Motor — Track del ML Specialist

**Fecha:** 2026-07-25
**Autor:** ML Specialist (Ariel Habib)
**Prerequisito de lectura:** [`viabilidad.md`](viabilidad.md) (por qué es viable) y [`plan-diseno.md`](plan-diseno.md) (qué se construye).
**Qué agrega este doc:** el *cuándo* y el *en qué orden*. `plan-diseno.md` define los hitos M0–M4 y el protocolo de backtesting; acá cada hito se desglosa en unidades de trabajo con entregable, gate de salida y dependencia, y se ordena en un cronograma.
**Alcance:** `motor/` y `datasets/`. No planifica trabajo de módulos ajenos; donde el motor toca una frontera (backend, DER, contrato de ingesta) se marca como acuerdo pendiente, no como tarea propia.

> **Este doc es el punto de control del módulo (regla de CLAUDE.md §6).** Todo desarrollo en `motor/` y `datasets/` se contrasta con él antes y después: la tarea tiene que corresponder a una unidad de trabajo existente (`T0.x`, `M1.x`, …) o la unidad se agrega acá primero, con entregable y gate; no se empieza un hito con el gate del anterior sin cumplir; y al terminar se actualiza el estado en la tabla de **§9** en la misma unidad de trabajo. Reordenar, recortar o partir unidades se escribe acá con su motivo antes de seguir — y si mueve un gate o una frontera, va ADR.

---

## 1. Convención de tiempo

- El cronograma está en **semanas relativas**: **S0 = semana del lunes 2026-07-27**, S1 la siguiente, y así.
- Una "semana" es **una unidad de esfuerzo**, no un compromiso de fecha. El supuesto de capacidad es dedicación de estudiante part-time; si la capacidad real difiere, el cronograma se escala proporcionalmente en vez de recortar alcance en silencio.
- Las fechas absolutas se pegan cuando el PM confirme el calendario de entregas UTN. **No se inventan acá.**
- Al cerrar cada unidad de trabajo: actualizar su fila en **§5–§8** y la tabla de seguimiento de **§9**, más `planning/roadmap.md` + `CLAUDE.md` §7 según la regla de CLAUDE.md §6.

## 2. Punto de partida (2026-07-25)

| Hito | Estado |
|---|---|
| **M0 — EDA y auditoría de datos** | ✅ 2026-07-15 — [`eda/eda-2026-07-15.md`](eda/eda-2026-07-15.md) |
| Decisiones de diseño del motor (8/8) | ✅ `plan-diseno.md` §Decisiones |
| ADR-007 (unidades) / ADR-008 (WAPE·MASE·sesgo) | ✅ Aceptadas 2026-07-25 |
| Generador de dataset sintético | ✅ 2026-07-27 — ver §9 |
| Código del motor | ✅ 2026-07-27 — S0 (paquete + capa de datos) y M1.0–M1.4 (arnés, métricas, red anti-leakage, clasificador), ver §9 |

> Esta tabla es la foto del **arranque del track**; el estado vigente está en **§9**, que
> es la superficie de seguimiento. Si las dos difieren, gana §9.

**Consecuencia:** el track arranca en S0 con el desbloqueo (generador + esqueleto + capa de datos) y entra en M1 en S1. El EDA ya calibró los parámetros del generador (EDA §8), así que S0 no requiere volver a la máquina autorizada.

## 3. Principio estructural del track: desacople del Release 1

El motor **no espera a R1** para escribir código. Lee y escribe a través de una **interfaz de repositorio** con dos implementaciones: archivos locales (S0) y PostgreSQL (M4). Ver **ADR-009** en [`docs/decisiones.md`](../docs/decisiones.md) — es frontera motor↔backend y está en estado *Propuesta* hasta ratificarla con el Backend Dev.

Por qué importa para el cronograma: si el motor esperara los hechos mensuales de R1, el track quedaría serializado detrás de dos dependencias externas (congelar el contrato v1.0 → construir el ETL) y el **arnés de backtesting —el activo más importante del motor— se escribiría último**. Con el desacople, la única dependencia dura de R1 es M4.2 (implementación PostgreSQL del repositorio).

Las tres fuentes de datos del track, y para qué sirve cada una:

| Fuente | Dónde | Para qué | Qué NO prueba |
|---|---|---|---|
| Sintético (`datasets/sintetico/`) | Cualquier máquina | Desarrollo, tests, CI, que el equipo pueda correr el motor | **La calidad predictiva.** Un modelo que gana en sintético no gana en real: el generador reproduce propiedades, no la señal |
| Extract propio del snap real | Solo máquina autorizada | Validar calidad: baselines reales, gates de promoción, tablas de error | Nada del pipeline productivo (es un extract ad-hoc, no el ETL) |
| PostgreSQL poblado por R1 | Cuando R1 exista | Integración productiva, `<2s`, batch nocturno | — |

**Regla de oro operativa (ADR-006):** de la máquina autorizada al repo entran **solo métricas agregadas**. Las tablas de error van a `motor/backtests/` como Markdown con conteos, ratios y porcentajes; nunca renglones, nombres de cliente ni precios.

---

## 4. S0 — Desbloqueo (cierra mi pendiente de R0)

Objetivo: que en S1 pueda escribir el arnés sin depender de nadie.

| # | Unidad de trabajo | Entregable |
|---|---|---|
| **T0.1** | **Generador de dataset sintético** parametrizado por EDA §8: cuadrantes de intermitencia 48/31/10/11%, 53,5% de pares cliente×producto con ≤2 compras en 36m, 25% de productos sin ancla propia, ~9,5% de comprobantes con cantidad negativa (NC), inflación acumulada en precios nominales, estacionalidad mensual, descuento por cliente. **Determinístico por semilla.** | `datasets/sintetico/generar_sintetico.py` + `README` con parámetros y semilla + manifiesto de la corrida |
| **T0.2** | **Esqueleto del paquete**: `pyproject.toml`, dependencias pinneadas (`statsforecast`, `mlforecast`, `lightgbm`, `hierarchicalforecast`, `utilsforecast`, `pandas`, `pyarrow`), `ruff` + `pytest`, layout `motor/src/motor/` | Paquete instalable en editable; `pytest` verde en vacío |
| **T0.3** | **Capa de datos (ADR-009)**: interfaz `RepositorioHechos` / `RepositorioResultados` + implementación de archivos (parquet) + **diccionario de columnas espejo del DER** (C1/C2/C3) + test de conformidad de esquema | `motor/src/motor/datos/` con test que falla si el esquema local se desvía del diccionario |

**Dos salidas del generador, no una.** El generador emite (a) **renglones de venta en el esquema del contrato de ingesta v0.9** — lo que el equipo necesita para probar el ETL, la validación de garantías y CP-VOL-01 — y (b) los **hechos mensuales agregados** desde su propia verdad de base, que es lo que consume el motor. Beneficio secundario que conviene explotar en R1: como (b) se deriva de (a) por una agregación conocida y sin ambigüedad, **el ETL del backend debe reproducir (b) a partir de (a)** — eso es un test de integración gratis para la ingesta. Coordinar con el Backend Dev cuando arranque R1.

**Gate de salida de S0:** `generar_sintetico.py` corre con una semilla fija y produce un dataset cuyo perfil de intermitencia, recalculado con el mismo código del EDA, cae dentro de ±3 puntos de los cuadrantes reales. Si no, el generador no está calibrado y M1 mediría contra un mundo que no existe.

**Nota de repo (resolver en S0):** `.gitignore` tiene un patrón `modelos/` sin anclar (pensado para artefactos entrenados) que también silenciaría cualquier subpaquete llamado `modelos/`. Por eso el subpaquete de modelos se llama **`modelado/`**. Además, los archivos *generados* por T0.1 no se commitean (se regeneran por semilla): agregar `datasets/sintetico/salida/` al `.gitignore` — es un endurecimiento de la regla de datos, no una excepción.

## 5. M1 — Baselines y arnés de evaluación · S1–S4

> Regla de `plan-diseno.md`: **el arnés antes que cualquier modelo.** Un modelo sin arnés es una opinión.

| # | Unidad de trabajo | Semana | Entregable / gate |
|---|---|---|---|
| **M1.1** | Arnés de backtesting rolling-origin: cortes mensuales sobre los últimos 18 meses, entrenar ≤ t → predecir t+1..t+12, sin shuffle ni k-fold | S1 | Arnés reproducible con un solo punto de entrada; corridas identificadas. **✅ 2026-07-27** — `ejecutar_backtest` + `corrida.py`: el `id` es hash de configuración + huella de datos, así que dos corridas equivalentes son comparables y cualquier cambio de config o de datos lo mueve |
| **M1.2** | Métricas ADR-008 con `utilsforecast`: WAPE por nivel, MASE vs `SeasonalNaive` por serie, sesgo (%over/under). Cortes de reporte por horizonte (1/3/6/12), **por cuadrante de intermitencia** y por categoría | S1 | Reporte tabular; ningún número global suelto sin desagregar. **✅ 2026-07-27** — `backtesting/metricas.py` + `backtesting/reporte.py`: WAPE/sesgo por nivel de agregación (producto/categoría/total) y MASE por serie, con `n` y `cobertura` en toda salida; cortes por horizonte (1/3/6/12), categoría y **cuadrante de intermitencia** (vía `motor.clasificacion`, M1.4). El corte por cuadrante es el que más aporta: mismo predictor, WAPE h=1 de **0,51 en suaves a 1,63 en lumpy** — el número global de 0,80 escondía 3x |
| **M1.3** | **Test anti-leakage de deflación**: verifica que para el corte t, ancla e índices se computan solo con datos ≤ t. Se escribe como test que *falla* si se introduce el leakage | S2 | Test en `tests/` marcado como innegociable; es la red contra el error más letal del motor (viabilidad §5). **✅ 2026-07-27** — `backtesting/leakage.py` + `tests/test_leakage_deflacion.py`, corribles con `pytest -m innegociable`. Como M2.1 no existe todavía, **no verifica una implementación sino una propiedad**: si dos datasets coinciden hasta el corte, el resultado en ese corte tiene que ser idéntico. Prueba dos variantes (truncar el futuro → detecta uso de su *existencia*; perturbar sus valores → detecta que se *leyeron*) y reporta cuál falló como diagnóstico. Se valida contra **tres implementaciones deliberadamente contaminadas**, entre ellas el fallback con promedio global — el camino del 25,4% de productos sin ancla propia (EDA §4) |
| **M1.4** | Clasificador ADI/CV² por serie (Syntetos-Boylan) para enrutar método por cuadrante | S2 | Etiqueta por serie, reproducible; contrastada contra los % del EDA. **✅ 2026-07-27** — `motor/src/motor/clasificacion.py`, con la **dependencia invertida corregida**: vivía en `datasets/sintetico/` y el motor no podía importarlo (`ModuleNotFoundError`, `datasets/` no es paquete instalable); ahora el generador importa del motor, así el gate de calibración se mide con el mismo criterio que usa el motor. Refactor verificado equivalente a escala real (0 de 2.300 productos cambian de cuadrante) y `datasets/sintetico/manifiesto.json` **idéntico byte a byte**, así que el gate de S0 no se movió. Aplica la regla de calendario de ADR-010 (ventana desde la primera venta histórica de cada serie) y pasa la red anti-leakage de M1.3 con `hasta=corte` |
| **M1.5** | Baselines `statsforecast`: `SeasonalNaive`, media móvil, `AutoETS`, `AutoTheta`, `AutoARIMA` | S2–S3 | Corren sobre sintético dentro del arnés. **✅ 2026-07-29** — `motor/src/motor/modelado/baselines.py`, predictor conforme al contrato `PredictorFn`. Tres gotchas de integración con `statsforecast==1.7.8` encontradas contra el dataset real y resueltas: (1) columnas además de id/fecha/objetivo se interpretan como regresores exógenos obligatorios — se recorta antes de llamar; (2) el id vuelve como índice, no columna — `reset_index()`; (3) `AutoETS`/`AutoTheta` explotan (`IndexError`/`ZeroDivisionError`) con 1-3 meses de historia, el caso real de un producto recién entrado al catálogo en un corte temprano — resuelto con `fallback_model=SeasonalNaive(season_length=1)`, verificado que no rompe la corrida completa. Riesgo medido, no resuelto acá: `AutoARIMA` cuesta ~2,9s/producto y `AutoTheta` ~1,6s/producto en serie — a escala real (2.300 × 18 cortes) es inviable sin paralelizar (`n_jobs`), preocupación de M1.7/M1.8. 4 tests, `ruff` limpio |
| **M1.6** | Rama intermitente: `CrostonSBA`, `TSB` (~42% de las series lo requiere — EDA §3) | S3 | Idem, con métricas separadas por cuadrante. **✅ 2026-07-29** — `motor/src/motor/modelado/intermitentes.py`, mismo contrato y mismas gotchas de columnas/índice que M1.5. Verificado además: predicciones nunca negativas, planas en el horizonte (comportamiento esperado del método, no bug), una serie sin ninguna venta no rompe la corrida, y el reporte se desagrega por cuadrante de punta a punta (`etiquetar` + `construir_reporte`) sobre una muestra real de las cuatro categorías — con este predictor sin enrutar, WAPE h=1 va de 0,14 en suave a 4,53 en lumpy, la brecha que motiva la selección de M1.7. 4 tests, `ruff` limpio |
| **M1.7** | Selección **por serie** (mejor baseline por MASE) + **tabla de referencia congelada** sobre sintético | S3 | **✅ 2026-07-30** — `modelado/seleccion.py` + `scripts/congelar_baselines_sintetico.py`; tabla en [`backtests/baselines-sintetico-2026-07-30.md`](backtests/baselines-sintetico-2026-07-30.md) (corrida `f993bc6ae12e`, muestra estratificada de 400 productos según §5.2, cobertura 1,0). **Los 7 candidatos ganan alguna serie** — ver el hallazgo de §5.3 |
| **M1.7a** | **Checkpointing del arnés por corte** (precondición de M1.8) | S3 | `ejecutar_backtest(directorio_checkpoint=...)`: cada corte se persiste al terminar y una corrida interrumpida se reanuda. Con guarda de `id` de corrida para no mezclar checkpoints de configuraciones distintas |
| **M1.8a** | **Extract propio del snap** (precondición de M1.8, no estaba planificada — ver §5.4) | S4 | `motor/scripts/extraer_snap.py`: los dos parquets del diccionario desde MySQL, con cross-check pandas vs SQL y validación contra el EDA. **La salida son datos reales: nunca al repo.** 21 tests sobre la transformación |
| **M1.8** | **Corrida de validación real** en la máquina autorizada: extract propio desde el snap 2018→, mismo arnés, misma tabla | S4 | `motor/backtests/baselines-real-<fecha>.md` — **solo métricas agregadas**. Este es el piso a batir; se congela |

### 5.1 Relevamiento del 2026-07-27 — M1.1/M1.2 vuelven a 🟡 y se agrega M1.0

**Motivo del cambio de plan (CLAUDE.md §6.4).** M1.1 y M1.2 se habían declarado cerradas el 2026-07-27. Un relevamiento posterior —revisión propia + revisión adversarial independiente, todo verificado corriendo contra `datasets/sintetico/`— encontró que **las tres métricas de ADR-008 están mal medidas** y que faltan dos elementos del gate. La declaración de cierre fue incorrecta: se apoyó en una corrida de punta a punta "sin errores" (que sí corre) confundiéndola con "mide bien" (que no). Se revierte el estado y la remediación entra como unidad propia **antes** de M1.5/M1.6, porque un baseline medido con este arnés elegiría el método equivocado.

**Causa raíz común:** el código trata `hecho_venta_mensual_producto` como un panel denso de calendario, y es **dispersa** (un producto-mes sin venta no tiene fila; densidad 72,8%, 0 filas con `unidades == 0`). De ahí salen los defectos 1, 2 y 8.

| # | Unidad de trabajo | Semana | Entregable / gate |
|---|---|---|---|
| **M1.0** | **Remediación del arnés y las métricas.** ✅ (a) densificación de calendario → **ADR-010** + `backtesting/panel.py`; ✅ (b) escala de MASE sobre calendario denso, `train_df` ordenado y guarda de escala 0; ✅ (c) WAPE/sesgo por **nivel de agregación** (`columnas_nivel`: producto/categoría/total); ✅ (d) `n` y `cobertura` en toda salida de métrica + el arnés conserva las celdas no predichas; ✅ (e) validación de grano/unicidad y de nulos en columnas de agrupación; ✅ (f) `generar_cortes` sobre calendario; ✅ (h) `tablas_auxiliares` recortadas al corte; ✅ (g) identificador de corrida (`corrida.py`) + reporte tabular (`reporte.py`) + `motor/backtests/` con sus reglas | S1–S2 | **✅ CERRADO 2026-07-27.** Tests escritos primero, verificados con `--runxfail` para que fallaran por el defecto y no por un error de la prueba; los 9 defectos cerrados con su test de regresión. **51 tests verdes, ningún `xfail`, `ruff` limpio**, y validación a escala real: 345.000 filas comparables, niveles producto/categoría/total 0,804/0,136/0,081 a h=1, cobertura 1,0 vs 0,391 al omitir series, el fan-out de cliente×producto se rechaza, y el reporte markdown se genera con su `id` de corrida. Ver `backtesting/README.md` §Defectos |

### 5.2 Cambio de plan del 2026-07-29 — la tabla de M1.7 va sobre muestra estratificada, y se agrega M1.7a

**Motivo (CLAUDE.md §6.4).** Al implementar M1.7 se midió por primera vez el costo real de
correr los 7 candidatos dentro del arnés, y obliga a decidir dos cosas que el plan no
contemplaba.

**Costo medido** (detalle y tabla completa en `src/motor/modelado/README.md` §Costo y
paralelismo). Ajustando `tiempo_por_corte = A + B × n_productos` sobre dos corridas con
`n_jobs=8`: **A ≈ 105 s/corte** de overhead fijo y **B ≈ 0,58 s/producto/corte** de
cómputo. El catálogo sintético completo (2.300 × 18 cortes) son **≈7 h**, y en serie ≈69 h.
Además `n_jobs=14` **mata la corrida** por archivo de paginación chico, y con `n_jobs=8`
ya aparecen `MemoryError` de workers reemplazados: el paralelismo está al límite de la
máquina.

**Decisión 1 — la tabla de M1.7 se genera sobre una muestra estratificada por cuadrante,
no sobre el catálogo completo.** Motivo: §3 de este roadmap ya establece que el sintético
**no valida calidad predictiva** (reproduce propiedades, no la señal), así que las 7 h de
cómputo no compran evidencia de calidad — compran la verificación de que el pipeline de
selección corre reproducible de punta a punta, y eso lo da igual una muestra. Estratificar
por cuadrante además da **mejores** estadísticas por cuadrante que la distribución natural,
donde `lumpy` es solo el 11%. El presupuesto de cómputo se reserva para M1.8, que es la
corrida cuyos números significan algo.

**Consecuencia sobre el gate, declarada y no escondida:** la tabla de M1.7 queda
etiquetada como muestra estratificada y **no** como piso del catálogo completo. El gate de
M1 no cambia — sigue exigiendo una tabla **sobre datos reales** (M1.8), que es la que se
congela como piso a batir. Lo que M1.7 acredita es el pipeline, no el piso.

**Decisión 2 — se agrega M1.7a (checkpointing del arnés).** Una corrida de horas sin
posibilidad de reanudar, con el pool de procesos al límite de memoria, es una apuesta: si
muere en la hora 6 no queda nada. M1.8 corre a escala real en la máquina autorizada y va a
tener el mismo problema o peor, así que el checkpointing se construye ahora y se usa en
las dos. Es un parámetro opcional del arnés (`directorio_checkpoint`), no un cambio de su
comportamiento por defecto.

### 5.3 Resultado de M1.7 — qué mostró la tabla (2026-07-30)

Corrida `f993bc6ae12e`: 400 productos (100 por cuadrante), 18 cortes, horizonte 12,
cobertura 1,0 en toda la tabla. Tres lecturas que importan para lo que viene.

**1. Los 7 candidatos ganan alguna serie — seleccionar por serie estaba justificado.**

| modelo | erratica | intermitente | lumpy | suave | total |
|---|---|---|---|---|---|
| `AutoARIMA` | 26 | 35 | 50 | 16 | **127** |
| `AutoETS` | 31 | 17 | 8 | 45 | **101** |
| `SeasonalNaive` | 14 | 21 | 19 | 3 | **57** |
| `CrostonSBA` | 15 | 6 | 5 | 24 | **50** |
| `AutoTheta` | 6 | 8 | 6 | 6 | **26** |
| `WindowAverage` | 4 | 10 | 10 | 2 | **26** |
| `TSB` | 4 | 3 | 2 | 4 | **13** |

Ninguno domina: el más ganador se lleva el 32% de las series. Correr un solo modelo para
todo el catálogo habría sido peor para las otras dos terceras partes.

**2. Hallazgo que contradice la premisa de enrutamiento de M1.6.** `CrostonSBA` gana casi
**5x más en `suave` (24) que en `lumpy` (5)**, y en `lumpy` —el cuadrante que motivó la
rama intermitente— gana `AutoARIMA` la mitad de las veces. Es lo contrario de lo que
sugiere la teoría. Explicación plausible: Croston predice un valor **plano** (una tasa de
largo plazo), y contra una serie suave y estable eso es un buen predictor; en `lumpy` la
varianza es tan alta que ningún método anda bien y las diferencias de MASE son ruido.

**Consecuencia de diseño, ya aplicada:** la decisión de M1.7 de hacer competir a los 7
candidatos **libres en toda serie**, en vez de enrutar por cuadrante, queda validada por
el dato. La regla "obvia" (intermitentes → Croston/TSB, resto → los normales) habría
perdido las 24 series suaves donde Croston es el mejor y habría forzado Croston en 100
series lumpy donde pierde. **No enrutar por cuadrante en M2/M3 sin volver a medir esto.**

**3. Dos números para tener presentes en M2:**
- **El sesgo a nivel total es ≈ −10%** (−0,1049 a h=1), o sea que los baselines
  **sub-pronostican** de forma sistemática. El gate de M2 exige ±5% a nivel total, así que
  esto no lo cumple — es una vara que el modelo global tiene que mejorar, no igualar.
- **El efecto de nivel es de ~5x**, más fuerte que el 3-4x medido en M1.2: WAPE 0,81 a
  grano producto contra 0,24 en categoría y 0,16 en total (h=1). Refuerza que un WAPE sin
  nivel declarado no significa nada.

### 5.4 Preparación de M1.8 — el extract y las decisiones de universo (2026-07-30)

M1.8 se venía describiendo como "el mismo script cambiando `--hechos` y `--etiqueta`".
Eso es cierto para el backtest, pero **el extract que produce esos `--hechos` no existía**:
en disco solo estaba el sintético, y el EDA de M0 fueron consultas SQL ad-hoc que no
quedaron guardadas. El entregable de software que faltaba es
`motor/scripts/extraer_snap.py`.

**La SQL se reusa, no se reconstruye.** `cotizaciones/backend/src/modules/snap/ventas/
repository.py::obtener_ventas_por_periodo` ya hace esta agregación mensual en producción
contra la misma base, con los filtros que el EDA documentó (`producto_id` numérico,
`estadistica NOT IN ('P','N')`, `precio > 0`, NC con signo, unión factura+remito). Se
parte de ahí en vez de reescribirla desde el markdown del EDA. **Tres diferencias
deliberadas**, todas anotadas en el script y en `scripts/README.md`: se agrupa por
producto y no por cliente × producto (sumar su salida perdería revenue por su `HAVING`),
se conservan los meses de neto cero (ADR-010) y el revenue mantiene el signo (ADR-002).

Acoplamiento aceptado y declarado: un cambio de esquema del ERP rompe dos repos. Es
tolerable porque este extract es **ad-hoc y no el ETL de R1** (§3); la divergencia entre
ambas definiciones de "venta mensual" ya está en la tabla de riesgos y se paga en M4.2.

**Decisiones de universo tomadas con el ML Specialist:**

| Decisión | Valor | Motivo |
|---|---|---|
| Productos | con venta en los **últimos 36 meses** (~2.189) | El catálogo tiene ~10.500 entradas; las ~8.000 sin venta cuadruplican el cómputo y meten series todo-ceros que **bajan el WAPE del piso sin que nadie prediga mejor** |
| Categorías | **las 12 de `categoria_producto`**, incluidas `DESCARTABLES`, `ACCESORIO` y `SIN CATEGORIA` | Son productos que el cliente efectivamente vende. La segunda columna del listado del ERP es un `version` de fila, no un flag de negocio: no hay señal ahí para excluir nada |
| Ventana | 2018-07 → último mes **completo** | El mes en curso está contablemente abierto; su caída se leería como demanda real |
| Máquina | la autorizada (única con acceso a la réplica) | Se descartó correrlo en otra máquina. Vale entonces el `n_jobs=4` ya medido acá |

**Dos redes contra un extract silenciosamente mal.** Un extract equivocado no falla:
produce un piso equivocado. (1) Cross-check pandas vs SQL sobre un mes, activo por
defecto: netea los renglones crudos con la regla que sí está bajo test y compara contra
lo que devolvió el servidor. (2) Validación contra el EDA — primer mes, meses sin huecos,
las 12 categorías, ~2.189 productos ±10%. Lo estructural corta la corrida.

**Queda por resolver en la corrida, no antes:** el nombre de la FK `producto` →
`categoria_producto`. Cotizaciones nunca joinea esas dos tablas desde el snap (categoriza
con su propio Postgres), así que el script lo descubre contra `information_schema` y corta
con la lista de columnas si no encuentra candidata.

### 5.5 Lo que apareció al correr el extract (2026-07-31)

El extract corrió y validó: **137.399 filas, 2.189 series, 96 meses sin huecos desde
2018-07, las 12 categorías, cross-check pandas vs SQL en verde**. El conteo de productos
activos dio **2.189, el número exacto del EDA** — confirma que los filtros son los
mismos. Cinco cosas aparecieron en el camino; las dos primeras son del esquema real y
**exceden al motor**.

**1. `producto.id` es `varchar(255)`, no un entero.** Conviven `'2'`, `'02'` y `'0002'`
como productos **distintos** —con proveedor y estado distintos— que colapsan al mismo
`int64` que exige el diccionario: **23 colisiones** sobre 9.486 códigos numéricos. No
falla: el `merge` que arma el reporte es un left join, así que multiplicaba por tres cada
fila de predicción de esos productos, inflando `n` y corrompiendo todos los WAPE.
Mitigado con `resolver_variantes()`, que recorta el catálogo por el **código de texto que
efectivamente vendió** y corta si dos variantes del mismo número tienen ventas (hoy
ninguna, pero colapsarlas fusionaría dos productos reales en una serie). Se detectó
porque el catálogo salía con 2.195 filas para 2.189 series.

**2. `nota_credito` es `BIT(1)`** y el driver lo devuelve como bytes (`b'\x01'`). Del
lado SQL no molesta —MySQL evalúa `= 1` sobre el BIT— pero cualquier comparación laxa en
Python da `False` para **toda** nota de crédito: las devoluciones sumarían en vez de
restar. **Lo atrapó el cross-check pandas vs SQL**, que es exactamente para lo que se
construyó.

> Las dos son trampas del esquema real, no del motor, y **el ETL de R1 se las va a comer
> igual**. Quedaron anotadas como pendiente del Analista Funcional en
> `planning/roadmap.md` (impacto a evaluar en DER, contrato §1/§3 y Plan de Pruebas). No
> se editan esos documentos desde acá: son de otro módulo (CLAUDE.md §2).

**3. El catálogo tiene ids no numéricos** (servicios y conceptos, como anticipa el EDA
§1). La query de ventas ya los filtraba con `REGEXP '^[0-9]+$'`; la de catálogo no, y
moría al castear después de haberse traído todas las ventas.

**4. `host.docker.internal` no resuelve fuera de un contenedor.** Cotizaciones corre
dockerizada y llega así al túnel SSH; nativo hay que ir a `127.0.0.1`, donde
`docker-compose.override.yml` publica el 3306. Sin remapeo la corrida muere recién a los
~60 s con un timeout opaco. El script lo remapea y lo avisa. **Precondición operativa:**
el túnel tiene que estar levantado (`docker compose --profile dev up`).

**5. Confirmada la deuda #2 del generador (T0.4).** Los datos reales traen **281 meses
con neto negativo**; el sintético tiene cero. Y **4.848 meses de neto exactamente cero**,
que quedan sin `precio_prom` — el caso que motivó la guarda del infinito.

**Bonus para T0.4:** ya está medida la distribución real de productos por categoría
(`CLINICO` 723, `SIN CATEGORIA` 491, `ANTIPARASITARIO EXTERNO` 359, `HIGIENE Y BELLEZA`
213, `ANTIPARASITARIO INTERNO` 136, `CARDIOLOGICO` 63, `DESCARTABLES` 51, `ALIMENTO` 46,
`BIOLOGICO` 44, `ANTIARTROSICO` 43, `ACCESORIO` 19, `HIGIENE Y BELLEZA (odontologico)`
1). Es lo que faltaba para que corregir las categorías del sintético sea algo más que
renombrar: la distribución es **muy** despareja y el generador hoy reparte uniforme.

### 5.6 M1.8 cerrado — el piso real (2026-07-31)

Corrida `f7af767ca7e6`: **2.189 productos, 18 cortes, horizonte 12, 214 min** con
`n_jobs=4`. Tabla en `backtests/baselines-real-2026-07-31.md`. **Este es el piso a
batir.**

| nivel | h=1 | h=3 | h=6 | h=12 |
|---|---|---|---|---|
| producto | 0,3241 | 0,3380 | 0,3538 | 0,3470 |
| categoría | 0,1506 | 0,1667 | 0,2096 | 0,2229 |
| total | 0,1223 | 0,1271 | 0,1574 | 0,1544 |

**1. El sesgo real es ≈ −1,4% a nivel total, no −10%.** El sintético había dado −10% y de
ahí salió la advertencia de que el gate de ±5% de M2 era "vara a mejorar". **Sobre datos
reales los baselines ya cumplen ese gate** (−0,0136 a h=1; el peor horizonte es +0,0521 a
h=12, también dentro de ±5%). La conclusión sacada del sintético estaba equivocada, y es
un recordatorio de que ese dataset no calibra magnitudes.

**2. El WAPE real es menos de la mitad del sintético** (0,32 contra 0,81 a grano
producto). No es que el motor mejorara: la composición es otra —el catálogo real es 58%
`suave` contra el 25% forzado de la muestra estratificada de M1.7— y la señal real tiene
estructura que el generador no reproduce. **Las dos tablas no se comparan entre sí**, que
es exactamente lo que §5.2 anticipó.

**3. La cobertura NO es 1,0, y la causa está diagnosticada.** Baja de 0,9918 (h=1) a
0,8794 (h=12) a grano producto. El **100,00%** de las 13.889 filas sin predicción son
productos cuya **primera venta es posterior al corte**: 277 series, de 301 altas de
catálogo desde 2024-12. Cero filas sin explicar. Un baseline univariado no puede predecir
una serie que no existía en el corte; el arnés registra el real (ADR-010) sin predicción
y la cobertura lo expone. **`SIN CATEGORIA` cae a 0,52 a h=12** porque 252 de esos 301
productos nuevos aún no están clasificados — leer esa fila como "se predice mal" sería un
error.

> **Es el caso que T0.4 #3 anticipó y el sintético no puede producir**: cero altas dentro
> de la ventana contra 301 reales. La deuda del generador dejó de ser teórica.

**4. Ninguno de los 7 candidatos domina, otra vez** — el más ganador (`SeasonalNaive`) se
lleva 678 de 2.186 series (31%), casi el mismo techo que en el sintético. Y **`CrostonSBA`
vuelve a ganar mucho más en `suave` (322) que en `lumpy` (16)**: el hallazgo contraintuitivo
de §5.3 se replica sobre datos reales, así que no era un artefacto del generador.

**Consecuencia para M2, a resolver antes de M2.5:** los productos nuevos son el caso de
mayor incertidumbre y **ningún baseline los cubre**. Es un hueco que el modelo global sí
podría llenar con features de categoría/laboratorio (arranque en frío). La comparación
champion/challenger tiene que hacerse **a igual cobertura**, o es injusta en las dos
direcciones. Se suma a la decisión ya abierta de §12.5.

**Mejora al script, ya aplicada:** `_nota_de_cobertura()` hace que toda tabla futura con
cobertura < 1 lleve la advertencia en el encabezado. Dejar el número en una columna al
medio de la tabla es dejarlo donde nadie lo mira.

**Gate de salida de M1:** existe una tabla de error de baselines, sobre datos reales, desagregada por horizonte × nivel × cuadrante, congelada y commiteada. A partir de acá **ningún modelo se promociona sin batirla** (disciplina baselines-first, CLAUDE.md §6).

**Precondición agregada al gate de M1 por el relevamiento:** ninguna tabla de referencia se congela (M1.7/M1.8) con M1.0 abierto. Las cifras que produce el arnés hoy no son piso de nada.

**No depende de:** contrato v1.0, R1, ni de trabajo de otros. M1.8 usa extract propio del snap (decisión #4 de `plan-diseno.md`), no el ETL.

## 6. M2 — Deflación y modelo global · S5–S8

| # | Unidad de trabajo | Semana | Entregable / gate |
|---|---|---|---|
| **M2.1** | **Transformador de deflación (ADR-002)**: ancla por producto + índices de nivel (media geométrica ponderada) + fallback categoría → laboratorio → IPC + clamp de ratios. Los casos CP-INF-01..05 se escriben como tests unitarios del transformador | S5 | Componente reutilizable + tests CP-INF-*; el fallback se testea con la misma prioridad que el ancla directa (lo necesita el 25,4% de los productos — EDA §4) |
| **M2.2** | Features: lags (1,2,3,6,12), rolling means (3,6,12), mes del año, `mismo_mes_año_anterior`, categoría/familia/laboratorio, `CLIENTE_FEATURE`, precio real deflactado y su variación | S5–S6 | Construcción de features pasando el test M1.3. **Precondición: T0.4** — `CLIENTE_FEATURE` del sintético es hoy una foto única, así que no se puede consumir sin leakage ni verificar con la red de M1.3 (§12.1) |
| **M2.3** | LightGBM global con `mlforecast`, **multi-horizonte directo** (un modelo por h ∈ {1,3,6,12}) | S6–S7 | Corre dentro del arnés, comparable 1:1 con el piso |
| **M2.4** | Intervalos: quantile regression P10/P50/P90 | S7 | Cobertura empírica de los intervalos reportada (¿el P10–P90 cubre ~80%?) |
| **M2.5** | **Champion/challenger por serie** + reporte comparativo contra el piso congelado, sobre sintético **y** real | S8 | `motor/backtests/global-vs-baselines-<fecha>.md` |

**Gate de salida de M2** (= puntos 2–4 de la Definición de listo de `plan-diseno.md`): el global ML gana en WAPE a niveles **producto y categoría** para **h=1 y h=3** (para h=6/12 alcanza empatar con mejor intervalo), y el sesgo global a nivel total queda dentro de **±5%**. Donde no gana, **manda el baseline** — el resultado legítimo de M2 puede ser "el baseline se queda con el 30% de las series", y eso se documenta, no se esconde.

**Riesgo específico:** validar solo en sintético haría ver al modelo mejor de lo que es (el generador no tiene la irregularidad del mundo real). Por eso M2.5 exige la corrida real.

## 7. M3 — Jerarquía, cliente y segmentos · S9–S12

| # | Unidad de trabajo | Semana | Entregable / gate |
|---|---|---|---|
| **M3.1** | Reconciliación total → categoría → laboratorio → producto con `hierarchicalforecast`; bottom-up vs MinT **elegido por backtest**, no por preferencia | S9 | Forecasts coherentes; ganancia por nivel documentada |
| **M3.2** | Nivel cliente×producto: **P(compra en h)** (clasificación binaria LightGBM, mismas features) + tamaño esperado condicional. Es el output honesto: solo ~12% de los 319k pares tiene ≥12 meses de señal (EDA §5) | S10–S11 | Ranking de propensión; alimenta venta cruzada y redistribución (R3) |
| **M3.3** | Clustering RFM propio sobre montos **deflactados** (CP-INF-04), versionado por corrida; contraste contra la segmentación operacional DFV (CP-SEG-01) | S11 | Matriz de contingencia cluster × `segmento_operacional`; `cluster_id` **no** entra como feature (ADR-005) |
| **M3.4** | Clientes nuevos (< 6 meses): prior del segmento operacional más cercano | S12 | Regla explícita y testeada |

**Decisión pendiente que hay que registrar en M3.2:** WAPE/MASE/sesgo (ADR-008) son métricas de error de forecast y **no aplican a un modelo de propensión**. Antes de cerrar M3.2 hay que fijar sus métricas (PR-AUC, lift@k, calibración) y registrarlas como ADR nuevo — ADR-008 no las cubre y dejarlo implícito es exactamente el vacío que ADR-008 vino a cerrar.

**Gate de salida de M3:** suite completa de predicciones coherentes + propensiones con métricas por nivel; CP-SEG-01 pasa (los segmentos no contradicen el oráculo DFV).

**Orden de recorte si el cronograma aprieta** (declarado ahora, para no improvisarlo bajo presión): primero MinT → bottom-up simple (pierde precisión marginal en niveles agregados); después M3.4 → regla trivial. **No se recortan M3.2 ni M3.3:** son requisitos de casos de uso (venta cruzada, segmentación), no mejoras de precisión.

## 8. M4 — Empaquetado batch e integración · S13–S15

| # | Unidad de trabajo | Semana | Entregable / gate |
|---|---|---|---|
| **M4.1** | Corrida versionada: `EJECUCION_MODELO` (tipo, versión, hiperparámetros JSONB, métricas de backtest) → `PREDICCION_DEMANDA` con `limite_inferior/superior` + segmentos | S13 | Toda salida analítica cuelga de una corrida; reproducible |
| **M4.2** | **Implementación PostgreSQL del repositorio** + swap de la de archivos. **Única dependencia dura de R1** | S13–S14 | El mismo motor corre contra archivos y contra la base, sin cambios en modelos |
| **M4.3** | Punto de entrada `motor.correr(fecha_corte)` para el job batch; contrato de invocación **a acordar con el Backend Dev** (no lo defino unilateralmente) | S14 | Firma acordada + smoke test desde el job |
| **M4.4** | Monitoreo de degradación: error realizado del mes vs backtest, como insumo de detección de drift | S15 | Reporte mensual automático |

**Gate de salida de M4 = Definición de "listo" del Release 2** (`plan-diseno.md`), los 6 puntos: arnés reproducible, baselines congelados, global ganando en producto/categoría a h=1/h=3, sesgo total ±5%, predicciones con intervalos consultables <2s, CP-SEG-01 y CP-INF-01..05 en verde.

---

## 9. Cronograma consolidado y estado

**Esta tabla es la superficie de seguimiento del módulo.** Se actualiza al cerrar cada unidad de trabajo, en la misma unidad de trabajo (no al final del hito). Estados: ⬜ pendiente · 🟡 en curso · ✅ cerrado con evidencia (fecha absoluta).

| Semana | Hito | Foco | Unidades | Estado |
|---|---|---|---|---|
| S0 | Desbloqueo | Generador sintético · esqueleto · capa de datos | T0.1–T0.3 | ✅ 2026-07-27 — T0.2 (paquete instalable, `pytest`+`ruff` verdes), T0.3 (`motor/src/motor/datos/`, 8 tests verdes) y T0.1 (`datasets/sintetico/`: generador top-down con rechazo/resorteo por producto; gate de cuadrantes cumplido con desvíos ≤1,25 pts sobre ±3 de tolerancia — `datasets/sintetico/manifiesto.json`) |
| S1–S2 | M1 | Arnés · métricas · test anti-leakage · clasificador de cuadrantes | M1.0–M1.4 | ✅ 2026-07-27 — **M1.0** (§5.1: los 9 defectos del relevamiento, con test de regresión cada uno), **M1.1** (arnés + corridas identificadas), **M1.2** (métricas por nivel + reporte tabular con todos sus cortes), **M1.3** (red anti-leakage, `pytest -m innegociable`) y **M1.4** (clasificador de cuadrantes, con la dependencia `datasets/`→motor invertida). **82 tests verdes**, ningún `xfail`, `ruff` limpio. El arnés ya puede medir baselines |
| S3 | M1 | Baselines + intermitentes | M1.5–M1.6 | ✅ 2026-07-29 — `modelado/baselines.py` (5 modelos `statsforecast`) y `modelado/intermitentes.py` (`CrostonSBA`/`TSB`), ambos conformes al contrato `PredictorFn`, con `fallback_model` para series de 1-3 meses de historia y verificados por cuadrante sobre datos reales. **90 tests verdes**, `ruff` limpio. Riesgo abierto para M1.7/M1.8: `AutoARIMA`/`AutoTheta` no escalan sin `n_jobs` |
| S3 | M1 | Selección por serie · tabla sintética | M1.7 | ✅ 2026-07-30 — `modelado/seleccion.py` (los 7 candidatos en un solo pase, ganador por MASE, `resumen_de_ganadores`) + `scripts/congelar_baselines_sintetico.py`. Tabla congelada: `backtests/baselines-sintetico-2026-07-30.md` (corrida `f993bc6ae12e`, 400 productos estratificados según §5.2, 18 cortes, cobertura 1,0). **Hallazgo en §5.3:** los 7 ganan alguna serie y Croston gana más en `suave` que en `lumpy` — el enrutamiento por cuadrante habría sido peor. **108 tests verdes**, `ruff` limpio |
| S3 | M1 | Checkpointing del arnés (precondición de M1.8) | M1.7a | ✅ 2026-07-29 — `ejecutar_backtest(directorio_checkpoint=...)`: un parquet por corte, reanudación que solo predice lo que falta, y **guarda por `id` de corrida** que rechaza reanudar con otra configuración o con otros datos en vez de mezclar checkpoints ajenos. 6 tests |
| S4 | M1 | Extract del snap (precondición de M1.8) | M1.8a | ✅ 2026-07-31 — `motor/scripts/extraer_snap.py` **ejecutado**: 137.399 filas, 2.189 series, 96 meses sin huecos, 12 categorías, cross-check en verde y **2.189 productos activos, el número exacto del EDA**. SQL derivada de la que cotizaciones ya corre en producción con tres diferencias deliberadas (§5.4). Cinco hallazgos en §5.5, dos de ellos del esquema real que **también afectan al ETL de R1** (`producto.id` es varchar con colisiones; `nota_credito` es BIT) → pendiente del Analista en `planning/roadmap.md`. **32 tests**; los tres de regresión verificados fallando sin su arreglo |
| S4 | M1 | **Piso real congelado** (máquina autorizada) | M1.8 | ✅ 2026-07-31 — `backtests/baselines-real-2026-07-31.md`, corrida `f7af767ca7e6`: 2.189 productos × 18 cortes × h=12 en 214 min con `n_jobs=4`. **Gate de M1 cumplido.** WAPE 0,32/0,15/0,12 (producto/categoría/total, h=1) y **sesgo total −1,4%, que ya cumple el ±5% de M2** — el −10% del sintético era un artefacto del generador. Cobertura < 1 explicada y diagnosticada al 100%: altas de catálogo (§5.6) |
| S4–S5 | — | Deuda del generador (precondición de M2.2, no bloquea M1) | T0.4 | ⬜ ver §12.1 |
| S5–S6 | M2 | Deflación (CP-INF-*) · features | M2.1–M2.2 | ⬜ |
| S7 | M2 | LightGBM global · cuantiles | M2.3–M2.4 | ⬜ |
| S8 | M2 | **Champion/challenger vs piso** | M2.5 | ⬜ |
| S9 | M3 | Reconciliación jerárquica | M3.1 | ⬜ |
| S10–S11 | M3 | Propensión cliente×producto · RFM deflactado | M3.2–M3.3 | ⬜ |
| S12 | M3 | Clientes nuevos · cierre de métricas por nivel | M3.4 | ⬜ |
| S13–S14 | M4 | Corridas versionadas · swap a PostgreSQL | M4.1–M4.2 | ⬜ |
| S15 | M4 | Invocación batch · monitoreo de degradación | M4.3–M4.4 | ⬜ |

**Hitos ya cerrados:** M0 — EDA y auditoría de datos ✅ 2026-07-15 (`eda/eda-2026-07-15.md`).

## 10. Dependencias externas — qué me bloquea y qué no

| Dependencia | Responsable | Bloquea | No bloquea |
|---|---|---|---|
| Contrato de ingesta v1.0 (P1–P4) | Lado cliente + Analista | El **esquema final** del generador (T0.1 se hace contra v0.9 y se ajusta si v1.0 cambia campos) y todo R1 | M1, M2, M3 — la validación real usa extract propio del snap |
| R1: PostgreSQL + hechos mensuales poblados | Backend Dev | **M4.2** y la corrida productiva | M1–M3 (ADR-009) |
| Ratificación de **ADR-009** | Backend Dev | Nada hoy; si se rechaza, hay que rediseñar la capa de datos antes de M4 | S0–M3 avanzan igual |
| Impacto de ADR-007/008 en DER, CU y Plan de Pruebas | Analista Funcional | La coherencia documental del TP | El código del motor |
| Contrato de invocación del job batch | Backend Dev + yo | **M4.3** | M1–M3 |
| Stack frontend | Frontend Dev | Nada del motor | Todo |
| Imagen Docker del motor (dependencias pesadas: `lightgbm`, `statsforecast`, `mlforecast`...) | Backend Dev (`infra/`) | Nada hoy — no es unidad de trabajo de S0–M3; `pyproject.toml` + venv alcanzan para desarrollo local | Todo hasta que exista una necesidad real: **M4.3** (job batch) o que alguien del equipo necesite correr el motor sin instalar las deps a mano. Se coordina con Backend Dev en ese momento, no se arma unilateralmente antes |

**Lo que yo debo entregarle al equipo, y cuándo:** el dataset sintético en **S0** (lo necesitan backend para el ETL y frontend para mockear); el piso de baselines en **S4** (lo necesita el Analista para fijar criterios de aceptación de R2 en el plan de pruebas); el contrato de invocación en **S14**.

## 11. Riesgos del track

| Riesgo | Señal temprana | Mitigación |
|---|---|---|
| El sintético es "demasiado fácil" y el modelo se ve mejor de lo que es | WAPE en sintético mucho mejor que en real | El gate de M1 y M2 exige corrida real; el sintético calibra propiedades, no valida calidad |
| Divergencia entre el diccionario de columnas del motor y el DER real de R1 | El test de conformidad de T0.3 rompe | Diccionario = espejo del DER; cualquier rename es cambio de contrato, se acuerda con el Backend Dev |
| Leakage temporal vía el ancla de deflación | Error del backtest sospechosamente bajo | Test M1.3, escrito **antes** de la deflación de M2.1 |
| Sobre-ingeniería temprana (deep learning, features exóticas) | Ganas de saltar a M2.3 sin M1 cerrado | Baselines-first: sin piso congelado no hay modelo que promocionar |
| M3 se estira y come M4 | S11 sin propensión andando | Orden de recorte declarado en §7 |
| El extract propio del snap difiere del ETL de R1 (dos definiciones de "venta mensual") | Diferencias al comparar M4.2 contra M1.8 | El cross-check del generador (§4) más el diccionario compartido; documentar toda diferencia como hallazgo, no ajustar a mano |

## 12. Deuda conocida y trampas (para quien siga)

**Cómo levantar el entorno y regenerar el dataset:** `motor/README.md` §Arranque desde cero.
El dataset sintético **no está en el repo**, así que ninguna validación a escala corre en un
clon nuevo hasta regenerarlo.

### 12.1 Deuda del generador sintético → **T0.4**

Las tres se verificaron corriendo contra el dataset generado (semilla 42). Ninguna bloquea
M1, pero **la primera bloquea M2.2** y la tercera debilita lo que el dataset puede validar.

| # | Qué le falta al generador | Por qué importa |
|---|---|---|
| 1 | **`cliente_feature` es una foto única** — verificado: una sola `fecha_calculo` (2026-06) para las 1.600 filas | **M2.2 la usa como feature.** Un predictor que la consuma en un corte de 2024 estaría viendo el futuro. El arnés ya tiene el hook (`tablas_auxiliares`) pero no hay nada que recortar: el generador tiene que emitir una versión por mes. Hoy la única defensa es que ningún predictor la usa todavía |
| 2 | **Ningún mes con unidades netas negativas** — verificado: 0 filas con `unidades < 0` en las dos tablas de hechos | El ~9,5% de notas de crédito existe solo en el JSON del contrato; al agregar por mes el neto siempre queda positivo. En la realidad un mes puede cerrar negativo (más devoluciones que ventas), y ni el motor ni el ETL de R1 lo ejercitan nunca |
| 3 | **No modela altas de producto** — verificado: **0 de 2.300 productos** tienen su primera venta dentro de la ventana de clasificación de 36 meses; la última primera-venta del dataset es de 2020 | La regla de calendario de **ADR-010** (arrancar en la primera venta de la serie) **no la ejercita ningún dato a escala**, solo tests unitarios. En datos reales los productos nuevos existen y son los de mayor incertidumbre. Un ADR-010 mal implementado pasaría toda validación sintética — de hecho pasó: el bug de la clave de `groupby` de M1.4 no lo detectó el sintético |

| # | Unidad de trabajo | Semana | Entregable / gate |
|---|---|---|---|
| **T0.4** | **Deuda del generador**: `cliente_feature` versionada por mes; altas y bajas de producto a mitad de historia; meses de neto negativo | S4–S5 (antes de M2.2) | Manifiesto que reporte: nº de `fecha_calculo` distintas > 1, % de productos con alta dentro de la ventana > 0, y nº de meses con neto negativo > 0. **No bloquea M1**; sí es precondición de M2.2 |

### 12.2 Trampas de configuración

- **Con `n_cortes = N`, el horizonte máximo *medible* es N**, porque el corte más viejo
  queda a N meses del final. Para que el reporte tenga los 1/3/6/12 que exige el gate de
  M1.2 hacen falta **más de 12 cortes**; con el default de 18 está bien, pero una corrida
  con `n_cortes=6` produciría una tabla que llega a h=6 y **no avisa**.
- **`reporte.attrs["corrida"]` se pierde en un `merge`** (pandas lo descarta). La columna
  `id_corrida` sobrevive. Si cruzás el reporte con el catálogo antes de armar las tablas,
  guardate la `Corrida` y reponela, o el reporte sale anónimo y no es congelable.
- **Al clasificar para enrutar método** (M1.5/M1.6) hay que pasar `hasta=corte`. Con el
  default (último mes de los datos) el modelo elige su método viendo el futuro. **Ojo:**
  esto aplica al *enrutamiento*; para desagregar el reporte por cuadrante (uso 2 de
  `clasificacion.py`) el default está bien. La selección de M1.7 no enruta por cuadrante,
  así que ahí no hay nada que recortar.
- **`n_jobs` se paga por corte, no por producto** (medido en M1.7): el arnés llama al
  predictor una vez por corte y cada llamada arma un pool de procesos nuevo que en Windows
  reimporta `scipy`/`statsforecast` en cada worker. Con 8 productos, `n_jobs=8` es **2x más
  lento** que serie; recién por encima de ~180 productos conviene. Y `n_jobs` alto **mata
  la corrida** por archivo de paginación chico: `n_jobs=14` no arranca y `n_jobs=8` murió
  en el 5º corte de la corrida de M1.7. **En esta máquina: `n_jobs=4`.** Tabla completa de
  mediciones en `src/motor/modelado/README.md` §Costo y paralelismo.
- **Corrida larga sin `--checkpoint-dir` es una apuesta perdida.** Lo de arriba no es
  hipotético: la corrida de M1.7 murió a mitad de camino y solo se salvó porque los cortes
  hechos estaban en disco. Para M1.8 (escala real, más horas) es obligatorio.
- **No pipees el script a `grep` al correrlo en background:** el exit code que ves es el de
  `grep`, así que una corrida que murió reporta "exit code 0". Redirigí a un archivo.
- **Los números publicados hasta hoy no dicen nada de calidad predictiva:** salen de un
  predictor de juguete ("último valor conocido") que solo existe en los tests. El primer
  número con significado sale de M1.7, y el que vale es M1.8.

### 12.3 Decisiones abiertas que no son mías

- **ADR-009 sigue en *Propuesta*** — a ratificar con el Backend Dev. No bloquea M1–M3; si
  se rechaza, la capa de datos se rediseña antes de M4.
- **Métricas del modelo de propensión (M3.2)**: WAPE/MASE/sesgo no aplican a una
  clasificación binaria. Hay que fijar PR-AUC / lift@k / calibración **como ADR nuevo**
  antes de cerrar M3.2 (ver la nota de §7).
- **MAPE comunicacional** (ADR-008: solo en niveles agregados, para la UI) no está
  implementado. Probablemente sea del frontend (R4); acordarlo, no asumirlo.

### 12.4 Sensibilidad a clientes de alto volumen — abierta, no desarrollada

**Origen (2026-07-29):** el motor agrega `hecho_venta_mensual_producto` sumando todos los clientes. Unos pocos clientes de volumen muy alto pueden dominar el agregado mensual de un producto y así:

- inflar o deformar el WAPE/MASE de ese producto en el backtest;
- cambiar su cuadrante de intermitencia (M1.4) según si ese cliente compró o no ese mes;
- hacer que la selección por serie de M1.7 (o el piso de M1.8) termine eligiendo el modelo que mejor sigue a ese cliente puntual, no la demanda típica del resto de la cartera.

**Decisión pendiente:** antes de congelar M1.7/M1.8 en definitiva, evaluar si conviene correr el arnés también sobre una base que excluya a esos clientes y comparar contra el agregado completo. **Explícitamente no se desarrolla todavía** — falta definir, cuando se retome:

- **Fuente de datos:** ¿sintético (simular un cliente de volumen desproporcionado) o extract real (solo corre en la máquina autorizada; al repo únicamente entrarían métricas agregadas, nunca los datos ni la identidad de los clientes — regla de oro, CLAUDE.md §4)?
- **Criterio de exclusión:** top-N por volumen acumulado / umbral de participación por producto-mes / lista puntual de clientes — ninguno decidido todavía.

No bloquea M1.7 ni M1.8; queda como nota para retomar una vez que se fije el criterio.

### 12.5 El piso de M1.7/M1.8 es optimista: la selección por serie es retrospectiva

**Hallazgo del 2026-07-29, al implementar M1.7.** `elegir_mejor_por_serie` elige el
ganador de cada serie con el MASE de **todos** los cortes del backtest, y
`armar_reporte_seleccionado` aplica ese ganador también a los cortes más viejos. O sea:
el modelo de cada serie se eligió con información posterior a las filas donde se mide.

Es exactamente lo que especifica `plan-diseno.md` §M1 ("cada producto queda con su mejor
baseline según MASE en backtest") y es la convención habitual para fijar una referencia
fuerte, así que M1.7 se implementó así. Pero hay que tenerlo escrito porque **no es un
procedimiento prospectivo**: un pipeline productivo elegiría el método en cada corte con
datos ≤ corte.

**Qué NO es.** No es el leakage que ataja la red de M1.3. Cada predicción individual
sigue siendo limpia — el arnés garantiza historia ≤ corte y eso no cambió. Lo que usa
información posterior es la elección de *qué modelo* mirar, no lo que cada modelo vio.

**Consecuencia, y por qué importa antes de M2.5.** Este piso está **más alto** que el de
un procedimiento prospectivo: la selección en hindsight le regala al baseline un
privilegio que el modelo global de M2 no tendría. Si M2.5 compara el global (medido
prospectivamente) contra este piso (medido con hindsight), la comparación castiga al
global y el gate de M2 podría rechazar un modelo que en realidad es mejor.

**Decisión pendiente (antes de M2.5, no bloquea M1.7/M1.8):** o se agrega una variante
prospectiva de la selección (elegir el método en cada corte con los cortes anteriores) y
el piso se recalcula con ella, o se le da al global el mismo trato retrospectivo. Lo que
no se puede es comparar los dos criterios entre sí. Si se elige nivelar, **va ADR**:
mueve un criterio de aceptación del gate de M2.

## 13. Fuera de este track

Deep learning (LSTM/transformers), pronóstico intra-mensual, optimización de precios, demanda censurada por quiebres, clima como driver de precisión (queda como feature explicativa/mock — viabilidad §3.4). Tampoco entra: re-deduplicar factura/remito (es del exportador del lado cliente desde 2026-07-15), reglas de abastecimiento (R3, backend), ni dashboard (R4, frontend).
