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
| **M1.9** | **Selección prospectiva + cascada por disponibilidad**, y re-congelado del piso con ese criterio (unidad agregada el 2026-08-05 para cerrar §12.5 — ver §5.7) | S5 | `motor/backtests/baselines-real-prospectivo-<fecha>.md` + §5.6.2 con la comparación contra el piso retrospectivo sobre los mismos 18 cortes. **Gate:** test marcado `innegociable` que perturba los reales posteriores al corte t y verifica que los ganadores de los cortes ≤ t no se mueven — la idea de M1.3 aplicada a la *elección del modelo*, que es el hueco que M1.3 no cubre |

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
  *(2026-08-03: la magnitud del sintético sigue sin calibrar, pero **la dirección era
  correcta**. §5.6 la dio por refutada con datos reales y se equivocó por el mes
  incompleto; el piso bueno sub-pronostica −5,2%/−6,0% a h=6/h=12 — ver §5.6.1.)*
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
| **Obsequios** (agregado 2026-08-02, **ADR-012**) | se descartan **por renglón**, `precio > $0,05` | El ERP exige `precio > 0`, así que un obsequio se factura con un centinela de $0,01: 3.638 renglones. **No se corta por producto:** el flag `producto.obsequio` marca 48 en el universo que cargan 0,92% del revenue, y 12 venden a precio real |
| **Descontinuados** (agregado 2026-08-02, **ADR-012**) | **no se excluyen del backtest** | `disabled` es estado de hoy y no tiene fecha; aplicarlo hacia atrás es sesgo de supervivencia (184 productos vivos al corte 2024-12, 2,82% del revenue de esa ventana). Para el backtest rige el criterio empírico de §12.1; el flag es para la corrida productiva |

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
mismos. Seis cosas aparecieron en el camino; las dos primeras son del esquema real y
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
con neto negativo** (0,205% de las filas); el sintético tiene cero. Y **4.848 meses de
neto exactamente cero** (3,53%), que quedan sin `precio_prom` — el caso que motivó la
guarda del infinito. Los negativos son **devoluciones, no datos corruptos**: 229 productos
en 88 meses distintos, repartidos parejo en los nueve años (23–51 por año) y de magnitud
chica (mediana −3 unidades). Salen del neteo por producto-mes de `_SQL_HECHOS`, cuando una
nota de crédito cae en un mes sin ventas de ese producto que la compensen.

**6. Veintiuna filas con precio implícito negativo.** Unidades y revenue se netean **por
separado**, así que si la nota de crédito lleva un precio distinto del de la venta (o
`precio` NULL, que la SQL colapsa a 0 con `COALESCE`), los dos netos pueden terminar con
signos distintos: **21 filas con `unidades < 0` y `revenue > 0`**, más 1 con revenue
exactamente 0. El caso inverso (`unidades > 0`, `revenue < 0`) no existe. El panorama
completo del insumo de M2.1: **132.529 filas con precio implícito > 0, 4.848 NaN por
`unidades == 0`, 22 con precio ≤ 0**. Son 0,016%, pero **un ancla de precio negativa
propagada por el fallback categoría → laboratorio contamina bastante más que 22 filas**:
es un caso concreto para el clamp de ratios de M2.1 y necesita test propio.

### 5.5.1 Lo que apareció al re-correr el extract (2026-08-02) — M1.8b

Tres cosas que el relevamiento de arriba no había visto, todas con el túnel arriba y
verificadas contra la fuente. Las dos primeras son **ADR-012**.

**7. Obsequios y descontinuados nunca se filtraron.** El detalle está en ADR-012; lo que
importa acá es que **el universo baja de 2.189 a 2.128 productos** y el extract de 137.399
a 135.409 filas, así que **el piso de M1.8 quedó medido sobre otro universo**. Dos cosas
que conviene tener escritas porque son contraintuitivas: el flag `producto.obsequio` **no
sirve de filtro** (12 de los 48 marcados venden a precio real y los 48 cargan 0,92% del
revenue), y el "." de los descontinuados vive en `descripcion`, no en `id`, así que el
`REGEXP` numérico nunca los tocó — son subconjunto exacto de los `disabled`.

**8. La réplica del snap puede estar atrasada, y el extract no se enteraba.** El 2026-08-02
la réplica tenía facturas hasta el 17-07 pero solo **6.410 comprobantes en 2026-06 contra
~14.000 típicos**, y 1 en 2026-07. `--hasta` toma por defecto el último mes **de calendario**
completo, que no es lo mismo que el último mes **de datos** completo. Un mes a medio cargar
no falla: se lee como un derrumbe de demanda, entra al ancla de deflación (que mira los
últimos 3 meses) y es justo el mes contra el que se evalúa el último corte del backtest.

> **El extract viejo se lo comió**: su último mes, 2026-06, tenía 32% de las unidades
> normales. O sea que el piso congelado no solo mide otro universo — su último corte se
> evalúa contra un mes incompleto.

Cerrado con `detectar_meses_incompletos()`, fatal, que mira la **cola** de la serie. Se mide
en **unidades**: las filas casi no se mueven (2026-06 dio 0,908 del normal, indistinguible
de un mes sano) porque los mismos productos siguen apareciendo con menos transacciones cada
uno, y el revenue arrastra inflación. Sobre 91 meses el ratio en unidades da p5 = 0,757 y
**mínimo legítimo 0,614** (junio es estacionalmente flojo, 0,61-0,81 todos los años);
2026-06 dio 0,321. El corte en **0,5** separa ocho años de meses sanos de la réplica
atrasada, y el mensaje de error dice con qué `--hasta` re-extraer.

**9. Del residuo de precios ínfimos, ver §6.2** — bajó de 1,2 M a 13.821 pero no se cerró,
y la alternativa medida rompe CP-INF-01.

#### Qué quedó abierto al cerrar M1.8b (2026-08-02)

Lo que M1.8b **sí** cerró: el filtro de obsequios, la red contra la réplica atrasada, y el
diagnóstico completo de por qué el deflactor explotaba. Lo que queda, en orden de a quién
bloquea:

| # | Qué falta | Bloquea | Costo |
|---|---|---|---|
| ~~1~~ | ~~**Re-congelar el piso** sobre el universo nuevo~~ | — | **✅ CERRADA 2026-08-03** — corrida `a79a9b23676b`, 294 min, `backtests/baselines-real-2026-08-03.md`. Ver §5.6.1: descompuesto, **el filtro de obsequios no movió el piso; lo movía el mes incompleto**, y el sesgo destapado incumple el ±5% de M2 a h=6/12 |
| ~~2~~ | ~~Decidir el residuo del deflactor~~ | — | **✅ CERRADA 2026-08-02** — `LIMITE_DESVIO_NIVEL = 10` contra categoría/laboratorio, nunca contra el IPC. 0 filas > 1.000, máximo 319. Ver §6.2 y ADR-012 punto 6 |
| ~~3~~ | ~~Ratificar ADR-012 con el Analista~~ | — | **✅ ADR-012 Aceptada 2026-08-02** por el ML Specialist: es regla de universo del extract del motor, no cambia hechos persistidos. El impacto documental queda como pendiente informativo del Analista |
| ~~4~~ | ~~CP-INF-03: cubrir el peldaño laboratorio con datos reales~~ | — | **Diferida por decisión explícita (2026-08-02):** en esta etapa no hace falta cubrir todos los peldaños. El laboratorio lo usa 1 producto de 2.128 y ahora además participa como nivel de contraste, así que la rama se ejercita de costado. Se retoma si algún peldaño pasa a ser relevante |
| **5** | **Borrar los extracts viejos.** El canónico quedó definido de hecho el 2026-08-03: **`C:/dfv-extract-v2`** es contra el que se corrió el piso (§5.6.1). Siguen en disco `C:/dfv-extract` (viejo) y `-v3` (prueba con umbral $1) | Nada hoy, pero es una trampa esperando: correr contra el directorio equivocado **no falla, da otro número** | Borrar dos directorios. **Ojo: no antes de haber cerrado el análisis de la corrida vieja** — los checkpoints de `C:/dfv-checkpoints` fueron los que permitieron descomponer el cambio del piso |

**Lo que NO cambió y sigue pendiente de antes**, para que no se pierda entre lo nuevo: la
decisión de §12.5 (el piso es retrospectivo) y la de §5.6 (comparar a igual cobertura por
las altas de catálogo). Las dos son **antes de M2.5**, no antes de M2.2.

**Un detalle de calibración que quedó anotado y no resuelto:** `EDA_PRODUCTOS_ACTIVOS_36M`
sigue valiendo 2.189, que es el número del EDA **contando obsequios**. El control pasa
porque la tolerancia es ±10% y ahora damos 2.128 (−2,8%), pero ya no es comparación
equivalente. Se dejó el número del EDA a propósito —su valor es la trazabilidad contra M0—
con la aclaración escrita en el propio docstring de la constante.

**Bonus para T0.4:** ya está medida la distribución real de productos por categoría
(`CLINICO` 723, `SIN CATEGORIA` 491, `ANTIPARASITARIO EXTERNO` 359, `HIGIENE Y BELLEZA`
213, `ANTIPARASITARIO INTERNO` 136, `CARDIOLOGICO` 63, `DESCARTABLES` 51, `ALIMENTO` 46,
`BIOLOGICO` 44, `ANTIARTROSICO` 43, `ACCESORIO` 19, `HIGIENE Y BELLEZA (odontologico)`
1). Es lo que faltaba para que corregir las categorías del sintético sea algo más que
renombrar: la distribución es **muy** despareja y el generador hoy reparte uniforme.

### 5.6 M1.8 — el primer piso real (2026-07-31), reemplazado

> ⚠️ **Esta corrida ya no es el piso.** La reemplaza §5.6.1 (corrida `a79a9b23676b`,
> 2026-08-03). Se conserva entera porque tres de sus cuatro conclusiones siguen valiendo y
> porque **la cuarta —el sesgo— resultó ser un artefacto**, que es justamente lo que
> §5.6.1 explica. Leerla sin esa advertencia lleva a la conclusión equivocada.

Corrida `f7af767ca7e6`: **2.189 productos, 18 cortes, horizonte 12, 214 min** con
`n_jobs=4`. Tabla en `backtests/baselines-real-2026-07-31.md`.

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

> ❌ **Este punto es falso y §5.6.1 lo mide.** El −1,4% era un artefacto del mes
> incompleto: 2026-06 entraba como mes evaluado con 32% de las unidades, así que `real`
> quedaba chico y `pred − real` se corría hacia arriba, tapando un sub-pronóstico. Sacando
> solo ese mes, el sesgo total a h=12 pasa de **−1,1% a −8,2%** — **fuera del ±5%**. Lo
> que sigue valiendo del párrafo es que el −10% del sintético tampoco era el número real.

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

> ❌ **El "100,00%" y el "cero filas sin explicar" son falsos; §5.6.1 punto 5 lo mide.** Las
> 13.889 filas son solo aquellas donde **ningún** candidato predijo, pero la columna
> `cobertura` cuenta las que le faltan al **modelo seleccionado**: **20.174 (6,41%)**. Las
> **6.285 restantes (31,15%)** son series jóvenes cuyo ganador retrospectivo no llegaba al
> horizonte pedido, con otros candidatos que sí predijeron. Lo que sigue valiendo es que las
> altas de catálogo son el componente mayoritario (69%) y que ningún baseline las cubre.

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

### 5.6.1 M1.8 re-congelado — EL piso (2026-08-03)

Corrida `a79a9b23676b`: **2.128 productos, 18 cortes (2024-11..2026-04), horizonte 12,
294 min** con `n_jobs=4`, sobre el extract `C:/dfv-extract-v2` (universo de ADR-012).
Tabla en `backtests/baselines-real-2026-08-03.md`. **Este es el piso a batir.**

| nivel | h=1 | h=3 | h=6 | h=12 |
|---|---|---|---|---|
| producto | 0,2870 | 0,2954 | 0,3114 | 0,3034 |
| categoría | 0,1283 | 0,1321 | 0,1691 | 0,1654 |
| total | 0,1029 | 0,1005 | 0,1191 | 0,0954 |

La corrida cambió **dos cosas a la vez** respecto de §5.6 —el universo (2.189 → 2.128) y
la ventana de cortes (2024-12..2026-05 → 2024-11..2026-04, porque el extract ya no llega
al mes incompleto)—, así que las tablas **no se comparan número a número**. Lo que sí se
pudo hacer, porque los checkpoints de las dos corridas sobrevivían, es **descomponer la
diferencia sin reajustar un solo modelo**: recortar subconjuntos de las predicciones ya
calculadas y recalcular las métricas por el mismo camino. Los cuatro escenarios, todos
sobre los **17 cortes compartidos**:

| escenario | WAPE prod h=1 | WAPE prod h=12 | WAPE total h=12 | sesgo total h=12 |
|---|---|---|---|---|
| **A** — viejo, 2.189 productos, con 2026-06 | 0,2939 | 0,3529 | 0,1585 | **−0,0108** |
| **A′** — solo los 2.128 que sobreviven a ADR-012 | 0,2933 | 0,3528 | 0,1586 | −0,0108 |
| **A″** — A′ sin el mes incompleto (2026-06) | 0,2899 | 0,2943 | 0,1002 | **−0,0823** |
| **B** — corrida nueva, historias limpias | 0,2899 | 0,2943 | 0,1002 | −0,0824 |

**1. El filtro de obsequios no movió el piso. Nada.** A → A′ cambia el WAPE en la cuarta
decimal (0,2939 → 0,2933) y el sesgo en ninguna. Es contraintuitivo porque M1.8b se trató
casi enteramente de eso, pero tiene una explicación de una línea: **el WAPE es un cociente
de sumas** (`Σ|real−pred| / Σ|real|`, ver `metricas.py:147`), así que pondera por
magnitud, y los 61 productos que se fueron son series diminutas. En unidades el universo
cambió **0,39%** (31,24 M → 31,12 M). ADR-012 era necesaria —sin ella el deflactor
explotaba— pero **su justificación no es el piso**, y conviene no recordarla como si lo
fuera.

**2. El que invalidaba el piso era el mes incompleto, y solo él.** A′ → A″ es donde se
mueve todo: WAPE producto h=12 **0,3528 → 0,2943** (−17%), total h=12 **0,1586 → 0,1002**
(−37%). Sacar 2026-06 de los meses evaluados es toda la diferencia. Y A″ → B es
**idéntico a cuatro decimales**: limpiar las historias de los productos que sí sobreviven
y reajustar los siete modelos no cambió nada medible. O sea que de los tres hallazgos de
M1.8b, **el que tenía consecuencias sobre el piso era el #8** (la réplica atrasada), no el
#7.

**3. El sesgo estaba tapado, y ahora incumple el gate de M2 en horizonte largo.** Es el
hallazgo que importa. Con 2026-06 adentro el sesgo total a h=12 daba **−1,1%** y §5.6
concluyó que "los baselines ya cumplen el ±5%". Sacando ese mes da **−8,2%**. El mecanismo
es aritmético: `sesgo = Σ(pred−real)/Σ|real|` (`metricas.py:163`), un mes con 32% de las
unidades reales achica el denominador y sobre todo hace `pred − real` menos negativo, así
que **enmascara un sub-pronóstico**. Pegó tanto en h=12 porque a nivel total ese horizonte
tiene **n=7** pares corte-objetivo: uno de los siete se evaluaba contra el mes roto.

El piso nuevo queda así contra el gate de ±5% a nivel total:

| horizonte | sesgo total | ¿dentro de ±5%? |
|---|---|---|
| 1 | −0,0338 | sí |
| 3 | −0,0260 | sí |
| 6 | −0,0517 | **no, apenas** |
| 12 | −0,0597 | **no** |

**Consecuencia para M2:** el gate de sesgo **no es un trámite**. Los baselines
sub-pronostican sistemáticamente en horizonte largo y el global tiene que corregirlo, no
solo empatar el WAPE. Esto no cambia el gate de M1 —que pide una tabla congelada, no que
los baselines cumplan el gate de M2— pero sí borra la tranquilidad que dejó §5.6.

> **Cerrado como decisión de proyecto el 2026-08-05: ADR-015.** El compromiso de precisión
> del *producto* se acota por horizonte (punto en h=1/h=3, **intervalo calibrado** en
> h=6/h=12), invocando el **Riesgo 5 del Acta**, que ya pre-autorizaba esta mitigación
> ("si a largo plazo la varianza es insalvable, se acotarán las métricas de éxito dándole
> mayor peso operativo al horizonte de 1 mes"). Se decidió **antes de M2.3**, a propósito:
> fijar el criterio después de ver si el modelo lo pasa es elegir la vara según el
> resultado. **El gate de M2 no se relajó** — ver §6.

**4. Lo que se replicó sin cambios.** Ningún candidato domina: el más ganador
(`SeasonalNaive`) baja de 678 a **481 de 2.106 series (23%)**, y **`CrostonSBA` vuelve a
ganar mucho más en `suave` (315) que en `lumpy` (20)**. Tercera medición del mismo
hallazgo contraintuitivo de §5.3 — no enrutar por cuadrante sin volver a medirlo.

**5. La cobertura tiene DOS causas, no una, y la de §5.6 estaba mal contada.** La cobertura
vuelve a bajar (0,9920 → 0,8880) pero el diagnóstico anterior —"el 100% son altas de
catálogo, cero filas sin explicar"— **era un artefacto del denominador**. Contaba las filas
donde **ningún** candidato predijo; la columna `cobertura` mide las que le faltan al
**modelo seleccionado**, que son más:

| corrida | sin pred. del seleccionado | altas de catálogo | horizonte truncado |
|---|---|---|---|
| `f7af767ca7e6` (2026-07-31) | 20.174 (6,41%) — se reportaron 13.889 | 13.889 (68,85%) | **6.285 (31,15%)** |
| `a79a9b23676b` (2026-08-03) | 18.355 (6,01%) | 12.700 (69,19%) | **5.655 (30,81%)** |

- **Altas de catálogo (69%)**: primera venta posterior al corte, historia 0, ningún
  candidato puede predecir. 262 productos; **221 de ellos (84,4%) son `SIN CATEGORIA`**, y
  eso es lo que hunde esa fila a 0,4953 de cobertura a h=12. Las **22 series sin ganador**
  (2.106 de 2.128) son el caso extremo: las 22 venden por primera vez en 2026-05, después
  del último corte. *(Los "275 productos nuevos / 226 sin categoría" que circularon son
  incorrectos: con el borde estricto son 262 y 221; con `>= 2024-11`, 274 y 231.)*
- **Horizonte truncado por historia corta (31%)**: 5.655 filas de 241 productos que **sí
  existían** al corte, con 1 a 11 meses de historia (mediana 2). Ahí otros 5 o 6 candidatos
  predijeron y el que no llegó fue el ganador retrospectivo: `SeasonalNaive` (5.355) o
  `WindowAverage` (300). **El naive estacional solo proyecta tantos meses como historia
  tiene** — en el **100%** de sus 5.355 filas se cumple `horizonte > meses de historia`; las
  38 de `WindowAverage` que no la cumplen son series más cortas que su propia ventana. Es lo
  que explica que la cobertura **caiga con el horizonte**: 25 filas a h=1, 682 a h=6.

**Por qué la distinción decide M2.5.** El primer componente es arranque en frío genuino: un
hueco que **ningún baseline puede llenar** y donde el global podría ganar con features de
categoría/laboratorio. El segundo es **reparable dentro de los baselines** — un pipeline
prospectivo que eligiera en cada corte un modelo capaz de cubrir el horizonte no tendría esa
brecha. O sea que **un tercio de la cobertura que le falta al piso es artefacto de la
selección retrospectiva de §12.5**, no un límite de los baselines, y comparar contra el piso
a valor nominal lo favorece. Medido: rellenando con `WindowAverage` donde está disponible
(2.613 de 5.655 filas; 0,71% de las unidades) el WAPE producto **empeora** +0,0060 a h=6 y
+0,0036 a h=12, y el sesgo total mejora a −0,0464 (h=6, entra al ±5%) y −0,0530 (h=12, sigue
afuera). O sea que **el incumplimiento del gate de sesgo a h=12 no es un efecto de la
cobertura**, pero el de h=6 sí es de borde.

**Lección de método:** la advertencia genérica que emite el script decía "sin predicción de
ningún candidato" —una causa que el script no puede conocer— y eso guió el conteo equivocado
las dos veces. Se corrigió la redacción y quedó un test que falla con la vieja
(`test_scripts_congelar.py::test_la_nota_no_afirma_que_ningun_candidato_predijo`). Vale como
caso general: **una plantilla que afirma una causa la instala**, aunque el dato no la
respalde.

**Lección de método, que es la misma de siempre en otra forma:** el piso viejo no estaba
mal por un error de código, sino porque **un mes de datos entró incompleto y nada avisaba**.
Se pudo separar la causa de la casualidad únicamente porque los checkpoints de las dos
corridas seguían en disco. Vale la pena no borrarlos hasta haber cerrado el análisis de la
corrida que los produjo.

**Gate de salida de M1:** existe una tabla de error de baselines, sobre datos reales, desagregada por horizonte × nivel × cuadrante, congelada y commiteada. A partir de acá **ningún modelo se promociona sin batirla** (disciplina baselines-first, CLAUDE.md §6).

**Precondición agregada al gate de M1 por el relevamiento:** ninguna tabla de referencia se congela (M1.7/M1.8) con M1.0 abierto. Las cifras que produce el arnés hoy no son piso de nada.

**No depende de:** contrato v1.0, R1, ni de trabajo de otros. M1.8 usa extract propio del snap (decisión #4 de `plan-diseno.md`), no el ETL.

### 5.6.2 M1.9 — el piso prospectivo, y por qué el sesgo del piso viejo era del criterio (2026-08-05)

Misma corrida `a79a9b23676b`, mismos 18 cortes, mismo universo: **se reusaron los
checkpoints y no se reajustó un solo modelo**. Cambia únicamente cómo se elige el modelo de
cada serie. Costo: **12 segundos** contra los 294 min de la corrida original.

Los tres escenarios, todos sobre los mismos datos ya predichos:

| | Selección | Cascada |
|---|---|---|
| **A** | retrospectiva (una por serie, con todos los cortes) | no |
| **B** | prospectiva (una por serie y corte, con lo ya observado) | no |
| **C** | prospectiva | **sí** ← **el piso nuevo** |

**Sesgo a nivel total, que es donde vive el gate de ±5% de ADR-008:**

| escenario | h=1 | h=3 | h=6 | h=12 |
|---|---|---|---|---|
| **A** — el piso congelado | −0,0338 | −0,0260 | **−0,0517** ❌ | **−0,0597** ❌ |
| **B** — solo cambia el criterio | +0,0077 | +0,0153 | −0,0233 ✅ | −0,0311 ✅ |
| **C** — más la cascada | +0,0077 | +0,0203 | −0,0100 ✅ | −0,0090 ✅ |

**1. El sub-pronóstico sistemático de horizonte largo era, en su mayor parte, del criterio
de selección — no de los baselines.** Los dos incumplimientos del ±5% desaparecen **ya en
B**, antes de tocar la cobertura: más de la mitad del movimiento (−0,0517 → −0,0233 en h=6)
lo produce elegir el modelo con lo observado en vez de con todo el backtest. El mecanismo es
el que la tabla de estabilidad hace visible (punto 4): el ganador retrospectivo se aplica
también a los tramos donde ya no era el mejor, y en horizonte largo eso arrastra un sesgo en
una dirección. **Esto tiene consecuencias fuera de M1.9 — ver ADR-016 y la actualización de
ADR-015.**

**2. El piso empeora en WAPE, y esa es exactamente la idea.** A grano producto:

| nivel | h | A | B | C | Δ (C−A) |
|---|---|---|---|---|---|
| producto | 1 | 0,2870 | 0,3305 | **0,3305** | +0,0435 |
| producto | 3 | 0,2954 | 0,3721 | **0,3767** | +0,0813 |
| producto | 6 | 0,3114 | 0,3844 | **0,4001** | +0,0887 |
| producto | 12 | 0,3034 | 0,3457 | **0,3699** | +0,0665 |
| categoría | 1 | 0,1283 | — | **0,1509** | +0,0226 |
| total | 1 | 0,1029 | 0,1205 | **0,1205** | +0,0176 |
| total | 12 | 0,0954 | 0,0907 | **0,0867** | **−0,0087** |

El piso retrospectivo reportaba un WAPE **13% menor** del que un pipeline puede lograr a
grano producto (0,287 contra 0,331 en h=1). Curiosidad que conviene no sobreinterpretar: a nivel
**total** y h=12 el prospectivo es **mejor** (0,0867 vs 0,0954) — los errores de modelos
distintos se cancelan al agregar.

**3. La cascada no era un adorno: sin ella la cobertura habría EMPEORADO.** Es el resultado
que más sorprendió.

| escenario | cobertura h=1 | h=3 | h=6 | h=12 |
|---|---|---|---|---|
| **A** | 0,9920 | 0,9653 | 0,9288 | 0,8880 |
| **B** | 0,9927 | 0,9638 | 0,9216 | **0,8651** ← peor que A |
| **C** | 0,9927 | 0,9786 | 0,9546 | **0,9104** |

Reelegir por corte hace que *más* series queden con un ganador incapaz de cubrir el
horizonte, no menos. La cascada revierte eso y algo más. Y el número final cierra el
diagnóstico de §5.6.1 punto 5 **exactamente**:

| origen de cada predicción | filas | % |
|---|---|---|
| ganador del corte | 284.574 | 93,21% |
| **cascada** | 8.035 | 2,63% |
| **sin predicción (ningún candidato)** | **12.700** | 4,16% |

Las 12.700 son, al número, las que §5.6.1 había atribuido a **altas de catálogo**. O sea:
**la cascada cerró el 100% del componente reparable** y lo que queda es el arranque en frío
genuino, que es el hueco donde M2 puede ganar con features de categoría/laboratorio. Esa
separación es la que le permite a M2.5 comparar a igual cobertura.

**4. El hindsight compraba mucho, y no se agota con el tiempo.** Solo el **15,7%** de las
series conserva el mismo ganador en los 18 cortes; la mitad cambia 6 veces o más (máximo
16 de 17 posibles). Y el WAPE por corte muestra que la brecha **no se cierra a medida que se
acumula evidencia**: en el último corte (2026-04, con 17 cortes de historia) sigue siendo
0,3426 contra 0,2907. No es un problema de arranque — es que el mejor método de una serie
cambia de verdad, y saberlo de antemano no es reproducible.

**5. El arranque sin evidencia costó poco, y se midió antes de darlo por bueno.** La
decisión 2 de M1.9 fue no exigir un mínimo (el primer corte cae entero al fallback). El
primer corte es efectivamente el peor de los 18 (WAPE 0,3947 contra 0,2543 del
retrospectivo), pero descartarlo mueve el h=1 de 0,3305 a **0,3259**, y descartar más cortes
**no mejora** (0,3317 con 3 fuera, 0,3466 con 6). Un burn-in habría costado cortes de
evaluación sin comprar precisión, además de romper la comparación fila a fila contra el piso
congelado.

**6. El hallazgo replicado tres veces sigue en pie** con selección por corte: ningún
candidato domina y la distribución de ganadores por cuadrante mantiene la forma de §5.3 y
§5.6.1 punto 4. No enrutar por cuadrante sigue siendo lo correcto.

**Gate de M1.9:** `test_la_seleccion_no_mira_el_futuro`, marcado `innegociable` — perturbar
los reales posteriores al corte no mueve los ganadores anteriores. Verificado por mutación:
**9/9 mutaciones caen**, incluidas las tres formas de aflojar la regla de observabilidad
(`< corte`, "cortes anteriores enteros", y sacar el filtro).

**Lección de método, que es la de siempre en otra forma:** el piso viejo no tenía un error
de código ni de datos. Tenía un **criterio de medición** que nadie había cuestionado hasta
que se escribió por qué era optimista, y ese criterio explicaba un hallazgo —el
sub-pronóstico de horizonte largo— que ya se había convertido en decisión de proyecto. Una
convención heredada ("cada producto queda con su mejor baseline") puede fabricar un hecho.

### 5.7 Cambio de plan del 2026-08-05 — se agrega M1.9 y se ejecuta antes que M2.3

**Motivo (CLAUDE.md §6.4).** §12.5 quedó desde el 2026-07-29 como *decisión pendiente* sin
unidad de trabajo asignada, con la nota de que había que resolverla "antes de M2.5". Se
adelanta a **antes de M2.3** y se le da unidad propia (**M1.9**) por tres razones, una de
ellas nueva:

1. **Los checkpoints la hacen barata hoy y cara mañana.** `C:/dfv-checkpoints-2026-08-03`
   (18 parquets, 7,6 MB) guarda las predicciones de **los 7 candidatos**, no solo la del
   ganador, así que la re-selección es un recálculo sobre datos ya calculados — el mismo
   truco con el que §5.6.1 separó obsequios de mes incompleto. Sin ellos son **294 min** de
   re-corrida. La higiene pendiente de `CLAUDE.md` §7 (borrar `C:/dfv-extract` y `-v3`) **no
   los incluye**, y no se borran hasta cerrar esta unidad.
2. **M2.3 se afinaría contra un número que después se mueve.** El piso es la vara del gate
   de M2; cambiarla después de entrenar el global es elegir la vara viendo el resultado —
   el mismo argumento con el que ADR-015 se decidió antes de M2.3 y no después.
3. **El costo dejó de ser solo cualitativo** (§12.5, actualización del 2026-08-03): un
   tercio de la cobertura que le falta al piso es artefacto de la selección retrospectiva,
   no un límite de los baselines, y eso **no se arregla dándole al global el mismo trato**.

**No es un hito nuevo ni mueve el gate de M1**, que ya está cumplido: exige una tabla
congelada, no que se haya congelado con un criterio en particular. Lo que M1.9 cambia es
**qué tabla es el piso de M2.5**, y por eso va ADR (§12.5 lo exigía explícitamente).

## 6. M2 — Deflación y modelo global · S5–S8

| # | Unidad de trabajo | Semana | Entregable / gate |
|---|---|---|---|
| **M2.1** | **Transformador de deflación (ADR-002)**: ancla por producto + índices de nivel (media geométrica ponderada) + fallback categoría → laboratorio → IPC + clamp de ratios. Los casos CP-INF-01..05 se escriben como tests unitarios del transformador | S5 | Componente reutilizable + tests CP-INF-*; el fallback se testea con la misma prioridad que el ancla directa (lo necesita el 25,4% de los productos — EDA §4); **test propio del precio implícito no utilizable** — 4.848 filas reales NaN por `unidades == 0` y 22 con precio ≤ 0 por signos cruzados (§5.5 #6). **CERRADA** ✅ 2026-07-31 — `motor.deflacion`, 67 tests, cobertura de ancla 73,2% contra el 74,6% del EDA §4 (§6.1, §6.2) |
| **M2.2** | Features: lags (1,2,3,6,12), rolling means (3,6,12), mes del año, categoría/laboratorio, escala de precio (ancla) y **precio relativo al nivel** con su variación. *(Tres correcciones a la lista original, medidas: ver §6.3 y ADR-013)* | S5–S6 | **✅ CERRADA 2026-08-04** — `motor/src/motor/features/`: `especificacion.py` (lo que ejecuta `mlforecast`) + `precio.py` + `construccion.py`. Pasa la red de M1.3 (`pytest -m innegociable`). **274 tests**, `ruff` limpio; las **7 mutaciones caen**. Validado a escala real en 3 cortes: cobertura 0,9899 sobre filas con precio propio, CV intra-producto 0,1511, **2,5 s** sobre 116k filas |
| **M2.3** | LightGBM global con `mlforecast`, **multi-horizonte directo** (`max_horizon=12`: un modelo por horizonte) | S6–S7 | Corre dentro del arnés, comparable 1:1 con el piso. **✅ 2026-08-06** — ver §6.5. Se cumple en sentido literal: los dos reportes se mergean fila a fila y las filas sin cubrir son las mismas |
| **M2.4** | Intervalos: quantile regression P10/P50/P90 | S7 | Cobertura empírica de los intervalos reportada (¿el P10–P90 cubre ~80%?). **✅ CERRADA 2026-08-06** — `backtests/intervalos-global-real-2026-08-06.md`: **0,7798 / 0,8199 / 0,8130 / 0,8085** contra el 0,80 nominal. Ver §6.6 |
| **M2.5** | **Champion/challenger por serie** + reporte comparativo contra el piso congelado, sobre sintético **y** real | S8 | `motor/backtests/global-vs-baselines-<fecha>.md`. **✅ CERRADA 2026-08-06 — ADR-017: lo promocionable es el champion, no el global solo.** El global solo **no cumple el gate** (a h=12 producto da 0,3746 contra 0,3699 del piso) y en `intermitente`/`lumpy` —31% de los productos, 0,6% del peso del WAPE— es **2 a 3 veces peor que el baseline**. El champion gana los cuatro horizontes: **0,3230 / 0,3667 / 0,3928 / 0,3644**. **Corrida sintética también hecha** (`-sintetico-2026-08-07.md`): replica que el champion le gana al piso, y **contradice** el resto — ahí el global gana 3 de 4 horizontes porque el generador no reproduce las ráfagas, así que validar solo en sintético habría promocionado el global (§6.7 punto 6). Ver §6.7 |

**Gate de salida de M2** (= puntos 2–4 de la Definición de listo de `plan-diseno.md`), **precisado por horizonte en ADR-015 (2026-08-05)** porque el piso real incumple el ±5% en h=6/h=12 (§5.6.1):

- **h=1 y h=3:** el global gana en WAPE a niveles **producto y categoría**, y el sesgo a nivel total queda dentro de **±5%**.
- **h=6 y h=12:** alcanza **empatar** el WAPE del piso, **y además** reportar la **cobertura empírica** del intervalo P10–P90 (M2.4). El sesgo se mide y se publica con su signo, y **se compara contra el del piso**: el gate exige que el global *corrija* el sub-pronóstico largo (−5,2% / −6,0%), no que se le perdone.

**ADR-015 acota lo que el producto le promete al usuario, no la vara del modelo** — no leerlo al revés. Donde no gana, **manda el baseline**: el resultado legítimo de M2 puede ser "el baseline se queda con el 30% de las series", y eso se documenta, no se esconde.

> **✅ Gate cumplido el 2026-08-06, por el champion y no por el global solo** (§6.7, ADR-017). h=1/h=3: gana WAPE a producto y categoría, sesgo total dentro del ±5%. h=6/h=12: **gana**, no solo empata, a producto y categoría; la cobertura del intervalo la reportó M2.4. El global aplicado a todas las series **no lo cumple** —pierde a h=12 contra el piso—, así que el "donde no gana manda el baseline" no era una salida de emergencia: era el resultado. Y el reparto real fue **84%** para los baselines, no 30%.

**Riesgo específico:** validar solo en sintético haría ver al modelo mejor de lo que es (el generador no tiene la irregularidad del mundo real). Por eso M2.5 exige la corrida real.

### 6.1 El IPC del INDEC, insumo de M2.1 (2026-07-31)

`motor/src/motor/datos/ipc_indec.csv` + `motor.datos.ipc.cargar_ipc()`. Serie
`148.3_INIVELNAL_DICI_M_26` de `apis.datos.gob.ar` (IPC Nivel General Nacional, base
dic-2016), **115 meses de 2016-12 a 2026-06, sin huecos ni nulos**, CC-BY 4.0. Cubre con
holgura los 96 meses del extract. Acumulada en esa ventana: **×79,2**, que es el tamaño
del problema que M2.1 viene a resolver.

Tres cosas para no tropezar después:

- **Es el único insumo externo del motor, y es dato público.** No lo alcanza ADR-006: no
  dice nada de DFV. Viaja *dentro* del paquete (`[tool.setuptools.package-data]`), porque
  si la rueda se construye sin él la cascada de ADR-002 se queda sin fondo.
- **El archivo se vence.** Un corte posterior a 2026-06 no tiene deflactor, y devolver el
  último dato disponible subestimaría la inflación **en silencio**, achicando los montos
  deflactados de todo el tramo faltante. `cargar_ipc()` levanta `IpcDesactualizado` en vez
  de eso. Actualizarlo es re-correr un `curl` (comando en el docstring del módulo).
- **La base dic-2016 = 100 no importa**: la deflación usa cocientes y la base se cancela.
  Se dejó el índice tal como lo publica la fuente para que sea verificable contra el
  original.

**9 tests** (`tests/test_datos_ipc.py`), verificados por mutación. El riesgo acá no es que
el código falle sino que el *archivo* sea el equivocado: la misma API publica la variación
mensual, la interanual y otras bases, y todas cargan sin error. La equivocada daría
deflactores cercanos a 1 para toda la historia —la deflación parecería andar y no haría
nada—; sustituyendo el CSV por la serie de variaciones caen 2 tests, y sacando la guarda
de vencimiento cae 1.

### 6.2 M2.1 cerrada — el transformador de deflación (2026-07-31)

`motor/src/motor/deflacion/`: `precios` (qué precio implícito es utilizable y qué
relativos salen de él) → `indices` (clamp, media geométrica ponderada, encadenado por
nivel) → `transformador` (cascada, ancla, matriz de deflactores). **67 tests**, `ruff`
limpio. La API la había fijado M1.3, no se eligió acá:
`TransformadorDeflacion().ajustar(datos, corte).ancla_`.

**La idea que ordena todo:** el objeto real no es el ancla sino un **deflactor por
(producto, mes)**, `d = ancla / P̂`. `P̂` es el precio propio cuando es utilizable y, si no,
el precio utilizable más cercano trasladado con el índice del nivel — cuando el mes es
utilizable el traslado vale 1, así que hay una fórmula sola. El ancla es el caso
`d(corte) = 1`.

#### Las constantes se midieron, no se eligieron a ojo

`LIMITE_RELATIVO = 3`, sobre las 125.078 muestras apareadas del extract:

| clamp | pares recortados | **en el peor mes** |
|---|---|---|
| 1,5 | 1,841% | **31,35%** |
| 2 | 0,613% | 3,05% |
| **3** | **0,325%** | **0,77%** |
| 5 | 0,221% | 0,63% |

Decide la última columna: con 1,5 y con 2 el clamp reacciona a la devaluación de dic-2023
(IPC +25,47% ese mes), o sea que recorta inflación real. En 3 el peor mes cae al nivel del
promedio — dejó de ser sensible a eventos. Que la cola sea basura está verificado: de los
276 pares con `r > 5`, **167 tienen algún precio bajo $5** y su revenue mediano es $1.148
contra $53.335 del par típico.

`MUESTRA_MINIMA = 3` pares para que un nivel tenga índice en un mes. El valor exacto no es
crítico (con 2 el IPC atendería 0,22% y con 5 el 0,40%); lo que importa es que exista, para
que un "índice" no sea el ruido de un solo producto.

**Las constantes son fijas a propósito.** Derivarlas de cuantiles de cada corte sería
leakage: el umbral dependería del futuro. Se midieron una vez, offline, sobre todo el
histórico.

#### Cuánto usa cada peldaño de la cascada (extract real, corte 2026-06)

| peldaño | productos | |
|---|---|---|
| producto (ancla propia) | 1.602 | **73,2%** — el EDA §4 esperaba 74,6% |
| categoría | 574 | 26,2% |
| IPC | 12 | 0,5% |
| laboratorio | **1** | 0,0% |

**El peldaño laboratorio lo usa un producto.** Es más granular que la categoría (82
valores contra 12), así que tiene menos muestra justo cuando se lo necesita. No es inútil
—es el peldaño de los productos en categorías diminutas— pero **los datos reales no lo
ejercitan: CP-INF-03 lo cubre con un caso construido a mano o esa rama queda sin testear**.

#### La validación que más convence

Deflactando el extract completo, el revenue anual **en pesos del corte** queda entre 36.000
y 40.700 millones de 2019 a 2025, mientras el nominal se multiplica por 29 en el mismo
tramo. Una distribuidora en marcha tiene que verse plana en términos reales, y se ve plana.
Corre en **2,1 s** sobre 137.399 filas.

#### Decisión abierta: el clamp no cubre el deflactor directo

El clamp protege el índice *de nivel*. Cuando el producto **sí** tiene precio propio ese
mes, el deflactor es `ancla / precio_propio` y un precio basura de $0,01 lo hace explotar:
sobre el extract son **93 filas de 7 productos** (0,068%) con deflactor de hasta 1,2
millones.

No mueve nada monetario —aportan 1,3 M sobre 294.733 M de revenue real, 0,000%, porque su
revenue también es ≈ 0— y por eso no se tocó dentro de M2.1: arreglarlo bien exige elegir
**otro** umbral con su propia medición, y no se inventa una constante para corregir un
0,000%. Pero la columna `deflactor` queda con valores sin sentido, y **eso sí importa para
las features de M2.2**. Está fijado en un test (`test_un_precio_propio_basura_infla_su_
deflactor_pero_no_mueve_el_agregado`) para que ninguna de las dos mitades cambie sin que se
note. **Decidir antes de M2.2.**

#### Estado de esa decisión al 2026-08-02 (M1.8b): la causa era el universo, y sigue abierta

Se investigó y **la causa raíz no era del transformador**: eran obsequios facturados con un
centinela de $0,01 que el extract nunca filtró (**ADR-012**). Sacándolos, el deflactor
máximo baja de **1.227.361 a 13.821**.

Pero **no lo cierra**: quedan **55 filas en 7 productos** con deflactor > 1000 (0,0031% del
revenue real), por precios de $0,07–$0,10 que son otro centinela apenas arriba del umbral.
Subir el umbral a $1 lo deja en 7 filas y tampoco lo cierra. Y el umbral no puede seguir
subiendo indefinidamente: llega un punto en que recorta precios reales.

**La alternativa está medida y funciona, y aun así se descartó.** Acotar el desvío del
deflactor contra el de su nivel, `q = d / d_nivel`, a `[1/10, 10]`:

| límite | recorta | peor mes | deflactor máx | Δ revenue real |
|---|---|---|---|---|
| 3 | 1,877% | 17,21% | 246,8 | +1,106% |
| 5 | 1,123% | 8,81% | 308,6 | −0,164% |
| **10** | **0,775%** | **2,51%** | **319,3** | **−0,322%** |
| 20 | 0,626% | 2,34% | 421,1 | −0,135% |

Mismo criterio que eligió `LIMITE_RELATIVO` (la columna del peor mes) y `q` tiene la ventaja
de ser **inmune a los eventos macro**: una devaluación mueve numerador y denominador juntos.
No se puede acotar `d` directo porque su magnitud legítima crece con la distancia al corte
(mediana 1,02 en el año en curso, 54,4 a ocho años, máximos legítimos ~560).

**El primer intento rompía CP-INF-01.** Aplicado contra *cualquier* nivel, el recorte hace
que el índice le gane al **precio propio observado**, que es lo contrario de la prioridad de
ADR-002. Verificado corriéndolo: fallaba
`test_la_misma_venta_en_2019_y_en_2025_vale_lo_mismo_deflactada`.

#### Cerrada el 2026-08-02: se acota contra categoría/laboratorio, nunca contra el IPC

`LIMITE_DESVIO_NIVEL = 10` con `NIVELES_CONTRASTE = ("categoria", "laboratorio")`. La
distinción no es un parche para que pase el test, y es lo que resuelve la tensión con
ADR-002:

- **Categoría y laboratorio se construyen con los relativos de los propios productos del
  cliente.** Un producto que se despega 10× de su categoría se despega de un espejo de sí
  mismo: eso es señal.
- **El IPC es un índice macro externo** sin ninguna obligación de seguir precios
  veterinarios. Despegarse de él es normal y no prueba nada.
- **No contradice a ADR-002** porque son dos operaciones distintas: la cascada de ADR-002
  *estima un precio que falta*; esto *valida uno que se observó*. Por eso acá el orden de
  peldaños no aplica y el fondo de la cascada no sirve de contraste.

Y es exactamente lo que salva CP-INF-01, cuyo fixture usa la rama IPC.

**Resultado sobre el extract:** **0 filas con deflactor > 1.000** (eran 55), máximo **319**
(era 13.821), mínimo 2,7e-3 (era 8,5e-5), revenue real total **−0,32%** y la serie anual sin
cambios de 2021 en adelante. **2 tests nuevos**, uno verificado por mutación; el que fijaba
la limitación vieja se reescribió para fijar la nueva.

**La contracara, declarada:** en la rama sin categoría ni laboratorio el deflactor sigue sin
cota. Sobre el extract es el 1,4% de las filas, y ninguna de las que explotaban cae ahí.

#### Una corrección al propio código, encontrada por mutación

La primera versión documentaba la base del encadenado en el primer mes como protección
anti-leakage. **Es falso con el cableado actual** y la mutación lo mostró: el transformador
recorta en el corte antes de encadenar y después solo usa cocientes, así que una constante
por corrida se cancela y `verificar_sin_leakage` no detecta el cambio de base (lo detecta
un test de `indices`). La base en el primer mes sigue siendo lo correcto, pero por otra
razón: mantiene pura a `indice_de_nivel` frente a quien la llame sin recortar antes. El
motivo escrito en el código se corrigió.

Lo que **sí** sostiene el anti-leakage es el recorte único en `ajustar`: sacándolo fallan
las tres salidas verificadas (`ancla_`, `indices_`, `deflactor_`). El fixture de la red se
amplió de 3 a 8 productos porque con 3 y muestra mínima 3 el índice de categoría se moría
en el mes 10 y la variante `indices_` comparaba dos tablas casi vacías — pasaba sin probar
nada, y también eso salió de la mutación.

### 6.3 M2.2 cerrada — y tres correcciones a la lista de features (2026-08-04)

`motor/src/motor/features/`, **274 tests**, `ruff` limpio. El gate —que la construcción pase
la red anti-leakage de M1.3— está cubierto por `test_construir_features_no_mira_el_futuro`,
marcado `innegociable`.

**El cambio de plan (CLAUDE.md §6.4).** Antes de escribir una línea se midió la lista de
features de `plan-diseno.md` §M2 sobre el extract real, y **tres de sus ítems no
sobrevivieron la medición**. Los dos primeros son **ADR-013**.

| # | Qué decía la lista | Qué se midió | Qué quedó |
|---|---|---|---|
| 1 | "precio real deflactado **y su variación**" | `precio_prom × deflactor = ancla` en el **99,15%** de las filas con precio propio; CV intra-producto **0,0000** contra 1,2809 del nominal | Es una identidad, no una medición: `d = ancla/P̂` y con precio propio `P̂ = precio_prom`. Se reemplaza por el **precio relativo al nivel** |
| 2 | (implícito) montos deflactados como features | `revenue_real = unidades × ancla` en el **99,13%** | El target reescalado por una constante por serie. **Ninguna feature monetaria deflactada entra a grano producto** |
| 3 | `mismo_mes_año_anterior` | A grano mensual **es** `lag 12` | Se saca: estaba duplicado |
| 4 | `CLIENTE_FEATURE` | El extract real **no tiene** cliente×producto ni `cliente_feature` — solo el sintético | **Diferida a M3.2** |

**Por qué el #4 se difiere y no se construye igual.** Se podría agregar a grano producto y
cumplir la letra de M2.2, pero entonces la corrida real de M2.5 tendría **una feature menos
que la sintética** y el champion/challenger compararía dos configuraciones distintas. M3.2 ya
es el hito a grano cliente×producto, que es donde la feature es nativa. El hook
`tablas_auxiliares` del arnés (construido en M1.0 (9) justamente para esto) queda como está,
con su test: espera a M3.2. **Anotado en M3.2, no como pendiente suelto.**

**La feature que reemplaza al precio deflactado, medida antes de elegirla:**
`precio_rel_nivel_t = precio_prom_t × I_nivel(corte)/I_nivel(t) / ancla`, o sea el precio del
producto llevado a pesos del corte **con el índice de su nivel** y no con el suyo. CV
intra-producto **0,1511** (p25 0,1056, p90 0,5098) sobre 1.680 productos con ≥12 meses, y la
variación a 3 meses reparte entre −0,216 (p5) y +0,237 (p95) **sin una sola fila en cero**.

**Es feature de forma, no de nivel**, y conviene tenerlo escrito porque el signo se lee al
revés: el nivel arrastra una constante por producto (el ancla es promedio de 3 meses, no el
precio del corte), así que "vale 1" es aproximado; lo exacto es que un producto que se movió
**igual que su categoría** tiene la serie **plana**, y uno que se **encareció** contra ella la
tiene **creciente** — porque en el pasado estaba relativamente más barato de lo que está hoy.

**Decisión de arquitectura: los lags los ejecuta `mlforecast`, M2.2 los especifica.**
Verificado contra `mlforecast 0.15.1`: `lags`/`lag_transforms`/`date_features` en el
constructor, `static_features` y `max_horizon` (multi-horizonte directo) en `fit`. Como las
features de este paquete son **estado en el origen del pronóstico** —constantes por serie
dentro de un corte— entran como `static_features` y **ninguna feature exógena necesita valor
futuro**, que es el problema que hunde a los modelos con exógenas dinámicas: el precio de
`corte+h` no se conoce.

**Cobertura medida (3 cortes, extract real):**

| corte | filas | `precio_rel_nivel` | `var_3m` | `var_12m` | `precio_ancla` |
|---|---|---|---|---|---|
| 2024-11 | 107.294 | 0,9567 | 0,8674 | 0,7379 | 0,9996 |
| 2025-05 | 116.492 | 0,9569 | 0,8702 | 0,7461 | 0,9995 |
| 2026-04 | 133.833 | 0,9563 | 0,8724 | 0,7578 | 1,0000 |

Corre en **2,5 s** sobre 116k filas. Sobre las filas con precio propio utilizable la
cobertura es **0,9899**; el resto del hueco son los meses de neto cero (3,53% real), donde no
hay precio observado. **`var_12m` pierde un cuarto del panel** y es esperable: pide el mismo
mes del año anterior, que las series jóvenes y las intermitentes no tienen. Nada se imputa.

**Dos propiedades que salieron de la implementación y hay que conocer antes de M2.3:**

- **El primer mes de cada panel nunca tiene `precio_rel_nivel`.** El índice de un nivel se
  construye con pares de meses *consecutivos*, así que el primer mes no tiene relativo y no
  hay contra qué medirse. Es propiedad, no defecto, y está fijada en un test.
- **Reusar un `TransformadorDeflacion` ajustado a otro corte es leakage que la red de M1.3
  NO vería**, porque llegaría contaminado desde afuera. Por eso `construir_features` corta si
  el corte no coincide.

**Verificación por mutación — las 7 caen.** Rompiendo a propósito: el recorte al corte (cae
la red de M1.3), el contraste contra `NIVELES_CONTRASTE` (aparece el IPC), el alineado por
calendario (pasa a `shift` por filas), la guarda del transformador ajeno, la máscara
`es_utilizable`, la guarda de ancla ≤ 0 y la validación de grano.

> **Dos de los tests no cazaban nada en su primera versión, y la mutación lo mostró** — vale
> anotarlo porque es la misma lección de siempre en otra forma. (a) El del alineado por
> calendario usaba un producto que crecía **igual que su categoría**, así que su
> `precio_rel_nivel` era 1,0 en todos los meses y alinear por filas o por calendario daba el
> mismo número; encima el mes de comparación era el primero del panel, que es nulo por la
> propiedad de arriba. (b) El de precios negativos usaba un producto **sin ancla**, así que
> el `NaN` venía de ahí y no de la máscara que decía probar. Los dos pasaban en verde. Un
> fixture mal armado no falla: **confirma**.

**Deuda anotada, no bloqueante:** `datasets/` sigue fuera del gate de `ruff` (§12.1), y el
sintético no tiene aún altas de cliente, que es lo que M3.2 va a necesitar junto con
`CLIENTE_FEATURE`.

### 6.4 Cambio de plan del 2026-08-06 — la ablación de precio se mide sobre real, no sobre sintético

**Motivo (CLAUDE.md §6.4).** M2.3 se planificó como "sintético completo + una corrida real
corta", con la comparación 1:1 contra `baselines-sintetico-2026-07-30.md`. Al ejecutarlo
aparecieron dos cosas que invalidan esa forma:

**1. La tabla sintética de M1.7 ya no es comparable con nada de hoy.** Se congeló el
2026-07-30 y **T0.4 reescribió el generador el 2026-07-31** (cliente_feature, meses de neto
negativo, altas y bajas correlacionadas, las 12 categorías reales). Sobre la misma muestra
estratificada, misma semilla:

| | filas | suma de unidades | `id` de corrida |
|---|---|---|---|
| tabla de M1.7 | 38.095 | 564.266,78 | `f993bc6ae12e` |
| sintético de hoy | 27.683 | 517.206,84 | `be8823f67f16` |

Es otro dataset. El `id` de corrida lo detecta —para eso existe—, pero **nadie lo iba a
mirar** si el número salía plausible. Vale como aviso general: una tabla congelada sobre el
sintético caduca cuando cambia el generador, cosa que no pasa con las de datos reales.

**2. La ablación de precio no puede medirse sobre el sintético, por construcción.**
`datasets/sintetico/demanda.py` no menciona el precio: el generador produce la demanda
independientemente de él. O sea que las features de precio de M2.2 son **ruido exacto** en
ese dataset, y la ablación solo puede confirmar que agregar ruido a LightGBM empeora un
poco — que es lo que dio (WAPE producto h=1: 0,8858 sin precio contra 0,9360 con precio).
**Leer eso como "M2.2 no aportó" sería un error de método**, del mismo tipo que los fixtures
que pasaban en verde sin probar nada.

**Qué se hace en lugar de eso.** Las cuatro ablaciones se corren sobre el **extract real
completo**, 18 cortes, misma configuración que la corrida `a79a9b23676b` del piso. Se puede
porque el costo real resultó ser **otro orden de magnitud del previsto**: ~14 s por corte,
o sea ~4 min por variante, contra las horas que costaron los baselines (ahí el caro era
`AutoARIMA`, ~2,9 s por producto). Y como el `id` de corrida **no incluye el predictor**,
el reporte del global es mergeable fila a fila contra el del piso, sin re-correr los 7.

La corrida sintética se conserva: acredita que el pipeline corre de punta a punta y que las
cuatro variantes se distinguen entre sí, que era el gate. Lo que no acredita es cuál
conviene.

### 6.5 M2.3 cerrada — el global corre, y le gana al piso en 11 de 12 celdas (2026-08-06)

`backtests/ablaciones-global-real-2026-08-06.md`, corrida `a79a9b23676b`: **el mismo `id`
que el piso**, porque el hash no incluye el predictor. Los 2.128 productos × 18 cortes ×
h=12, ~4 min por variante.

**Las ablaciones, sobre datos reales (WAPE a grano producto):**

| variante | h=1 | h=3 | h=6 | h=12 |
|---|---|---|---|---|
| **`precio+crudo`** ← elegida | **0,2953** | **0,3435** | **0,3834** | **0,3746** |
| `sin_precio+crudo` | 0,2969 | 0,3445 | 0,3879 | 0,3979 |
| `precio+escalado` | 0,2982 | 0,3748 | 0,4390 | 0,4949 |
| `sin_precio+escalado` | 0,3009 | 0,3788 | 0,4457 | 0,4988 |

**1. Las features de precio de M2.2 sí compran algo, y lo que compran crece con el
horizonte.** A h=1 la diferencia es despreciable (0,0016) porque ahí mandan los lags; a
**h=12 vale 0,0233, un 6% relativo**. Tiene sentido: a doce meses los lags ya no dicen casi
nada y el estado de precio del origen es de lo poco que queda con información.

**2. `LocalStandardScaler` empeora, y bastante:** h=12 pasa de 0,3746 a 0,4949 (**+32%**).
Normalizar por serie le saca al modelo global justamente la escala que usa para agrupar
productos parecidos, y como el WAPE pondera por magnitud, degradar las series grandes se
paga caro. La intuición de "normalizá antes de un modelo global" no sobrevivió a medirla.

**3. Sobre el sintético el signo de la ablación de precio era el OPUESTO** (0,8858 sin
precio contra 0,9360 con precio). No es contradicción: §6.4 explica que el generador no
vincula precio con demanda, así que ahí esas features son ruido exacto. **La confirmación
de que la advertencia metodológica era correcta y no una excusa.**

**Contra el piso prospectivo de M1.9**, misma corrida, **cobertura idéntica fila a fila**:

| nivel | h | piso (M1.9) | global | Δ |
|---|---|---|---|---|
| producto | 1 | 0,3305 | **0,2953** | −0,0352 |
| producto | 3 | 0,3767 | **0,3435** | −0,0332 |
| producto | 6 | 0,4001 | **0,3834** | −0,0167 |
| producto | 12 | **0,3699** | 0,3746 | +0,0047 ← la única que pierde |
| categoría | 1 | 0,1509 | **0,1208** | −0,0301 |
| categoría | 3 | 0,1701 | **0,1428** | −0,0273 |
| categoría | 6 | 0,2063 | **0,1831** | −0,0232 |
| categoría | 12 | 0,1787 | **0,1503** | −0,0284 |
| total | 1 | 0,1205 | **0,0934** | −0,0271 |
| total | 3 | 0,1390 | **0,0906** | −0,0484 |
| total | 6 | 0,1575 | **0,1164** | −0,0411 |
| total | 12 | 0,0867 | **0,0811** | −0,0056 |

**4. La comparación es a igual cobertura, y está verificado, no supuesto.** El merge de los
dos reportes por `(producto, mes, corte, horizonte)` da **305.309 filas, todas en ambos**, y
las filas sin predicción son **exactamente las mismas 12.700** en los dos: cero donde uno
cubre y el otro no. Son las altas de catálogo de §5.6.1 — productos cuya primera venta es
posterior al corte, que ni los baselines ni el global pueden predecir porque no existen al
momento de entrenar. O sea que **el requisito que §5.6.1 le ponía a M2.5 ya está cumplido
por construcción.**

**5. El sesgo del global entra al ±5% en los cuatro horizontes:** −0,62% · +0,11% · −0,65% ·
−1,83% (nivel total). No hay que leerlo como que "corrigió" el sub-pronóstico de horizonte
largo: ese ya había desaparecido al arreglar el criterio de selección en M1.9 (§5.6.2).

> **Lo que esto NO es.** No es el champion/challenger: eso es **M2.5**, que elige por serie
> y con la regla prospectiva de ADR-016. Estos son agregados, y un agregado mejor puede
> convivir con series donde el baseline gana — de hecho el `producto h=12` ya avisa que las
> hay. Tampoco es una promoción: ningún modelo se promociona sin M2.5.

**Gate de M2, para tenerlo a la vista** (`plan-diseno.md`, punto 3): pide ganar en WAPE a
nivel **producto y categoría en h=1 y h=3**. Las cuatro celdas dan a favor del global. El
punto 4 (sesgo dentro de ±5% en h=1/h=3) también. **Con los agregados el gate está**; falta
que M2.5 lo confirme por serie.

**Gate de salida de M2.3:** el predictor corre dentro del arnés y su reporte es **mergeable
fila a fila** contra el del piso — demostrado arriba, no afirmado. **307 tests**, `ruff`
limpio, red de M1.3 sobre `predecir_global` cubierta, **8/8 mutaciones caen**.

#### Tres cosas que la mutación destapó, y que valen más que el número

- **La red de M1.3 encontró un defecto real:** `predecir_global` no recortaba `historia` al
  corte. Con meses posteriores presentes, el merge de features los dejaba sin catálogo y
  `mlforecast` cortaba diciendo que `categoria` "cambia en el tiempo" — un mensaje que
  apunta a cualquier lado menos a la causa.
- **El clip de negativos parecía código muerto y no lo es, pero por otro motivo del que
  dice la intuición.** Un ensamble de árboles predice promedios de targets observados, así
  que **no puede salirse del rango de entrenamiento**: con toda la historia en positivo, una
  serie "en descenso" nunca da negativo y el test no prueba nada. Lo que sí lo ejercita son
  los **meses de neto negativo** (notas de crédito grandes), que son reales — T0.4 los
  siembra y §5.5 #6 los encontró en el extract.
- **Una mutación que sobrevive no siempre acusa al test.** La de "la ablación no apaga nada"
  era un no-op: sacaba el `usar_precio` de un filtro que igual no encontraba las columnas.
  El selector estaba mal, no el test. Conviene mirar la mutación antes de tocar el test.

### 6.6 M2.4 cerrada — el intervalo P10–P90 calibra, y el promedio esconde por qué (2026-08-06)

`backtests/intervalos-global-real-2026-08-06.md`, corrida `a79a9b23676b` — **el mismo `id`
que el piso y que las ablaciones**, porque el hash no incluye el predictor. 2.128 productos ×
18 cortes × h=12, **19,4 min**, 305.309 filas.

**De dónde partía la unidad.** M2.3 dejó el global produciendo **un solo número por celda**.
A h=6 el WAPE a grano producto es 0,3834 y a h=12 0,3746: presentar eso como precisión es
prometer lo que no hay, y **ADR-015 punto 2 ya había decidido que en esos horizontes el
entregable del producto es el intervalo P10–P90 calibrado** (y su punto 4 lo puso como
reemplazo del badge de MAPE de CU-03, que ADR-008 dejó sin dueño). O sea que había un
compromiso escrito con el usuario y el motor **no producía el objeto que lo cumple**.

**El número del gate — cobertura empírica contra el 0,80 nominal:**

| horizonte | cobertura | desvío | amplitud relativa | WAPE del punto |
|---|---|---|---|---|
| 1 | 0,7798 | −0,0202 | 0,8197 | 0,2953 |
| 3 | 0,8199 | +0,0199 | 1,1111 | 0,3435 |
| 6 | 0,8130 | +0,0130 | 1,2046 | 0,3834 |
| 12 | 0,8085 | +0,0085 | 1,2655 | 0,3746 |

**1. Calibra sin recalibrar, y el desvío máximo es de 2 puntos.** No se tuneó nada para
llegar acá: son los mismos hiperparámetros sin tunear de M2.3 con `objective="quantile"`.
Conviene decirlo explícito porque la tentación estaba: ajustar hasta pegarle al 80% habría
sido elegir la vara viendo el resultado, y el gate pedía **reportar** la cobertura, no
alcanzarla. La `amplitud_relativa` usa el mismo denominador que el WAPE (`Σ|real|`) para que
las dos últimas columnas de esa tabla se lean juntas: el intervalo mide entre 0,8 y 1,3 veces
la magnitud del propio real, o sea del orden de 3x el error del punto. Ancho, pero no
absurdo — y ese contraste es el que impide que "cobertura 0,80" se lea como éxito cuando se
consigue con un rango inútil.

**2. El agregado calibra porque dos errores se cancelan, y esa es la lectura que importa.**

| cuadrante | h=1 | h=3 | h=6 | h=12 | amplitud h=12 |
|---|---|---|---|---|---|
| `suave` (20.773 filas) | 0,7820 | 0,8010 | 0,8012 | 0,7990 | 1,19 |
| `erratica` | **0,6790** | **0,6992** | **0,6771** | **0,6700** | 1,37 |
| `intermitente` | 0,8572 | 0,9230 | 0,9111 | 0,9071 | **8,34** |
| `lumpy` | 0,7089 | 0,8537 | 0,8370 | 0,8257 | **13,47** |

`suave` —que es la mayoría de las filas— calibra casi perfecto en los cuatro horizontes. Lo
que el promedio tapa son las otras tres: **`erratica` sub-cubre ~12 puntos de forma
sistemática** (el intervalo promete menos riesgo del que hay, que es el error peligroso para
un analista de compras) mientras `intermitente` y `lumpy` **sobre-cubren con intervalos de
hasta 13 veces la magnitud del real** — honestos pero inservibles para decidir. Es
exactamente el caso que la regla de M1.2 ("ningún número global suelto sin desagregar")
existe para atrapar: con la tabla por horizonte sola, M2.4 se declaraba cerrada con un
0,80 impecable y el problema quedaba invisible.

**3. El cruce de cuantiles no es un problema, y ahora está medido.** Los tres modelos se
ajustan independientes y nada les impone monotonía, así que había que saber cuán seguido se
cruzan antes de decidir si reordenar. Sobre 105.890 filas completas: `P50 > P90` en 0,486%,
`P10 > P50` en 0,112%, y **`P10 > P90` en 1 sola fila (0,0009%)** — o sea que el intervalo
que se publica prácticamente nunca se invierte. Reordenar (Chernozhukov et al.) mueve la
cobertura en la **cuarta decimal** (0,7798 → 0,7799). **Consecuencia para M4.1:** se puede
escribir `limite_inferior/superior` sin paso de reordenamiento; alcanza con una guarda de una
línea para esa fila entre cien mil, y ya se sabe que no cambia ningún número.

**4. El P50 le gana a la media como pronóstico puntual, pero solo a h=12 — y es justo la
celda que M2.3 perdía.**

| | h=1 | h=3 | h=6 | h=12 |
|---|---|---|---|---|
| media (el punto de M2.3) | **0,2953** | **0,3435** | **0,3834** | 0,3746 |
| P50 | 0,3055 | 0,3529 | 0,3868 | **0,3627** |

El piso prospectivo da 0,3699 a h=12 producto: la media pierde por +0,0047 (la **única** de
las 12 celdas que M2.3 no ganaba, §6.5) y **el P50 le ganaría por −0,0072**. Tiene sentido —
a 12 meses la distribución está muy sesgada y la media se corre con la cola. **No se cambia
nada acá:** elegir el estimador por horizonte mirando esta tabla es hindsight, el mismo
problema que ADR-016 cerró para la selección de baselines. Entra a **M2.5 como candidato**, y
si se adopta tiene que ser con la regla prospectiva (por corte, con lo ya observado).

**5. El control cruzado que valida toda la corrida.** El WAPE del pronóstico puntual
reproduce **exacto** el de las ablaciones de M2.3 —0,2953 / 0,3435 / 0,3834 / 0,3746 a grano
producto, y todas las celdas de categoría y total dígito a dígito— porque los cuantiles se
suman al mismo `MLForecast` sin tocar el modelo de media. Es lo que garantiza que M2.4 no
movió el número con el que M2.5 va a comparar, y está fijado además por un test de igualdad
exacta (`test_los_cuantiles_no_mueven_el_pronostico_puntual`).

**Costo:** 94 s por corte contra 21,6 s del punto solo (4,3x, consistente con 4x los
modelos: `max_horizon=12` × 4 estimadores = 48 ajustes por corte). **Directorio de
checkpoints propio, obligatorio:** el `id` de corrida no incluye el predictor, así que esta
corrida comparte `id` con las ablaciones de M2.3 y habría "reanudado" sus checkpoints —que no
tienen columnas de cuantil— sin avisar.

**Gate de salida de M2.4:** cobertura empírica del P10–P90 reportada, desagregada por
horizonte, cuadrante y categoría, en tabla congelada con `id` de corrida. **Cumplido.**
**329 tests**, `ruff` limpio, red de M1.3 extendida a los cuantiles, **9/9 mutaciones caen**.

#### Lo que esto le deja al PM y al Analista, y no lo decide el motor

ADR-015 punto 2 fijó la cobertura del P10–P90 como **el** compromiso del producto en h=6/h=12
— un número único. Los datos dicen que ese compromiso **no se cumple parejo**: se cumple en
`suave`, se sobre-cumple caro en `intermitente`/`lumpy` y **no se cumple en `erratica`**,
donde falta ~12 puntos en los cuatro horizontes. Hay que decidir si el compromiso se expresa
por cuadrante, si se acota a los cuadrantes donde se cumple, o si la advertencia de varianza
de CU-03 cambia según la serie. Se suma a que **ADR-015 ya venía pendiente de revisión** por
la evidencia que le corrigió ADR-016. Registrado en `planning/roadmap.md`.

#### Una nota de método que no es de esta unidad pero salió acá

`Get-Process().CPU` (y `Win32_Process` por CIM) reportaron **~0 s de CPU y 11 MB** para el
proceso de esta corrida mientras estaba entrenando LightGBM normalmente. Sobre esa lectura se
diagnosticó un cuelgue que no existía y se bajó una corrida sana. **La señal de progreso de
una corrida del arnés son los checkpoints en disco**, que además llevan la marca de tiempo del
corte; el contador de CPU no sirve en esta máquina.

### 6.7 M2.5 cerrada — el champion gana, y el global solo no era promocionable (2026-08-06)

**De dónde parte.** §6.5 cerró M2.3 con "el global le gana al piso en 11 de 12 celdas" y esa
frase, sola, dice *reemplacen los baselines por el global*. §6.5 mismo avisó que no: son
agregados, y "un agregado mejor puede convivir con series donde el baseline gana". M2.5 es
la unidad que va a mirar eso. Entregable: `backtests/global-vs-baselines-real-2026-08-06.md`
(corrida `a79a9b23676b`) y `-sintetico-`.

**Costó 45 segundos y no reajustó un solo modelo.** Los checkpoints de las dos corridas
comparten `id` —el hash es de configuración + datos y **no incluye el predictor**— así que se
cruzan fila a fila por `(producto, mes, corte, horizonte)`: 305.309 filas, todas en ambos.
Es la contracara del mismo hecho que obliga a un directorio por variante en las ablaciones.
Rehacer las dos corridas costaba 294 min + 19 min.

#### 1. El veredicto, y por qué el titular de §6.5 estaba incompleto

WAPE a grano producto, contra el piso prospectivo, **a cobertura idéntica en las 12 celdas**:

| | h=1 | h=3 | h=6 | h=12 |
|---|---|---|---|---|
| piso (7 baselines, prospectivo) | 0,3305 | 0,3767 | 0,4001 | 0,3699 |
| global solo | **0,2953** | **0,3435** | **0,3834** | 0,3746 ❌ |
| champion (9 candidatos) | 0,3230 | 0,3667 | 0,3928 | **0,3644** |

**El global solo no cumple el gate de M2**: a h=12 pierde contra el piso (el gate pedía al
menos empatar). El champion gana los cuatro horizontes a grano producto, los cuatro a
categoría, y tres de cuatro a nivel total —pierde h=12 por 0,0014—, con **sesgo dentro del
±5% en los cuatro** (−0,31% / +0,77% / −1,49% / −0,82%). **El gate de M2 está cumplido, y lo
cumple el champion.** Ver ADR-017.

> **Una cláusula del gate quedó sin objeto, y conviene decirlo antes de que alguien la lea
> como incumplida.** El gate pedía además que el global *"corrija el sub-pronóstico largo
> (−5,2% / −6,0%)"*. Ese sub-pronóstico **ya no existe**: era del criterio de selección
> retrospectivo y desapareció en M1.9 (§5.6.2) — el piso prospectivo da **−1,00% (h=6)** y
> **−0,90% (h=12)**. No hay nada que corregir, y el champion queda en −1,49% y −0,82%, del
> mismo orden y adentro del ±5%. La cláusula se escribió sobre la evidencia vieja, igual que
> ADR-015.

#### 2. Lo que el agregado tapaba: el WAPE es 86% `suave`

El WAPE pondera por magnitud y las magnitudes van de jeringas a vacunas. Participación en la
suma de `|real|`, y WAPE a grano producto por cuadrante:

| cuadrante | peso_% | productos | piso h=12 | global h=12 | champion h=12 |
|---|---|---|---|---|---|
| `suave` | **85,6** | 1.224 | 0,3310 | **0,3149** | 0,3229 |
| `erratica` | 13,8 | 239 | 0,5535 | 0,5789 | 0,5575 |
| `intermitente` | **0,4** | 488 | 1,2254 | **3,4260** | 1,3426 |
| `lumpy` | **0,2** | 177 | 2,5491 | **5,6294** | 2,7709 |

**El global es 2 a 3 veces peor que el baseline en el 31% de los productos, y el agregado no
lo ve porque esas series cargan el 0,6% del peso.** El modo de falla es sobre-pronóstico y
**empeora con el horizonte**: el sesgo del global en `lumpy` va de +0,59 (h=1) a **+5,11**
(h=12). Es coherente con lo que un modelo global hace —predice la media condicional de
productos parecidos, y en una serie que vende a ráfagas esa media está muy por encima del mes
típico— pero produce sugerencias de compra inservibles justo donde el usuario más las
necesita.

**El champion paga por arreglarlo:** en `suave` es peor que el global solo (0,2954 contra
0,2654 a h=1). Es varianza de selección — reelegir por corte con evidencia limitada a veces
elige mal. El intercambio es perder ~0,03 de WAPE en el 86% del peso para ganar entre 1,5 y
2,9 en el 31% de los productos, y se acepta porque el producto sugiere órdenes **por
producto** (ADR-017).

#### 3. El reparto: los baselines se quedan con el 84%

Pares (serie, corte) ganados, de 38.014:

| | pares | % |
|---|---|---|
| 7 baselines | 31.804 | **83,7** |
| `GlobalLGBM_P50` | 3.512 | 9,2 |
| `GlobalLGBM` | 2.698 | 7,1 |

`plan-diseno.md` §M2 anticipaba "el baseline se queda con el 30% de las series" como
resultado legítimo. El número real es **84%**, y no cambia la conclusión: el global aporta
donde aporta, que es donde está el volumen. `SeasonalNaive` sigue siendo el que más gana
(13.039), igual que en el piso.

#### 4. El P50 competía mucho y aportaba casi nada — y el sesgo lo descalifica

§6.6 punto 4 lo había dejado abierto: la mediana le ganaba a la media a h=12 (0,3627 contra
0,3746), justo en la celda que M2.3 perdía. M2.5 lo hizo competir por corte con la regla
prospectiva, que era la forma limpia de resolverlo, y dio dos respuestas:

- **Gana 3.512 turnos de selección —más que `GlobalLGBM`— y mueve el WAPE del champion entre
  0,0008 y 0,0018.** La variante `--sin-p50` da 0,3242 / 0,3674 / 0,3946 / 0,3652: cuarta
  decimal. Que sea elegido tanto tiene explicación: **la selección usa MASE, que es error
  absoluto, y la mediana es el minimizador del error absoluto**. Compite con ventaja en el
  criterio de selección y esa ventaja no se traduce al WAPE.
- **Su sesgo viola ADR-008:** a nivel total va de **−8,4% a −13,4%**, fuera del ±5% en todos
  los horizontes, porque la mediana de una distribución sesgada a derecha está
  sistemáticamente por debajo de la media. Esto solo ya lo descalifica como estimador
  puntual, y §6.6 no podía verlo porque miró WAPE.

**Queda como candidato del champion, no como estimador puntual** (ADR-017 punto 3). Donde sí
es notablemente mejor que los dos es en `intermitente`/`lumpy` a h=1 (0,586 contra 0,960 del
global) — coherente con que la mediana de una serie intermitente es baja o cero.

#### 5. Sumar candidatos no compró cobertura ni estabilidad

- **Cobertura: 12.700 filas sin predicción**, exactamente las mismas del piso y del global.
  Nueve candidatos no cubren una fila más: son las altas de catálogo de §5.6.1, productos que
  no existían al corte. La comparación es a igual cobertura **por construcción**.
- **Estabilidad: idéntica.** 335 series (15,7%) conservan ganador en los 18 cortes con 7
  candidatos y **las mismas 335** con 9; la mediana de cambios sube de 6 a 7. Agregar
  candidatos no estabiliza la selección, la agita un poco más.

#### 6. El sintético habría promocionado el global — y esa es la mejor evidencia de por qué el gate lo pedía

El gate de M2.5 exige la corrida sobre sintético **y** sobre real, con este motivo escrito en §6:
*"validar solo en sintético haría ver al modelo mejor de lo que es"*. La corrida sintética
(`backtests/global-vs-baselines-sintetico-2026-08-07.md`, corrida `be8823f67f16`, 400 productos
estratificados, **8,9 s**) lo confirma de la forma más útil posible: **contradiciendo la
conclusión.**

WAPE a grano producto, sintético:

| | h=1 | h=3 | h=6 | h=12 |
|---|---|---|---|---|
| piso | 0,9819 | 0,9366 | 0,9380 | 0,9465 |
| global solo | **0,9360** | **0,8736** | 0,9122 | **0,8883** |
| champion | 0,9657 | 0,9000 | **0,8817** | 0,9340 |

**Sobre el sintético el global gana 3 de 4 horizontes, incluido h=12 — que es exactamente la
celda donde sobre datos reales pierde.** Un equipo que hubiera validado solo acá habría
promocionado el global sin ver el problema.

**Qué replica y qué no**, que es lo que hay que leer:

- **Replica:** el champion le gana al piso en los cuatro horizontes. La conclusión central de
  M2.5 —seleccionar por serie contra un piso prospectivo mejora— se sostiene en los dos datasets.
- **No replica, y es el motivo de ADR-017:** el derrumbe del global en `intermitente`/`lumpy`. En
  sintético, `lumpy` h=12 da **1,455 del global contra 1,368 del piso** (6% peor); en real da
  **5,63 contra 2,55** (121% peor). El generador no reproduce la estructura de ráfagas del
  catálogo real, así que el modo de falla que decide la promoción **no existe en el sintético**.
- **Y la composición es otra por diseño:** la muestra estratificada fuerza `suave` al 32% del peso
  cuando en real es el 86%, y `lumpy` al 14,6% cuando en real es el 0,33%. Eso solo ya hace que
  los dos agregados **no sean comparables entre sí** — se leen por separado, como dice §5.6.

> **La regla que esto deja:** el sintético sirve para verificar que el pipeline corre y que las
> métricas se calculan, y **es bueno en eso** — encontró cero problemas nuevos acá, que es
> justamente lo que se espera de un smoke. Lo que no puede hacer es decidir **qué modelo se
> promociona**, porque el generador no tiene los modos de falla que deciden. Es la misma lección
> que ADR-013 dejó con las ablaciones de precio, ahora con un caso donde la conclusión equivocada
> era plausible y accionable.

#### Lo que le deja al PM y al Analista

El punto 4 de ADR-017: **decidir con el desagregado por cuadrante en la mano es lo que evitó
promocionar el global**, y eso implica que la precisión que el producto promete se cumple de
forma muy distinta según la serie. Es la misma forma del hallazgo de M2.4 con la cobertura del
intervalo, y **se suma a las dos revisiones que ADR-015 ya tenía pendientes**. Registrado en
`planning/roadmap.md`.

#### Una trampa del método que esta unidad convirtió en guarda

**Una serie que un modelo no predijo saca WAPE 0,0 — perfecto.** En `metricas.wape` la
predicción nula aporta 0 al numerador, y lo único que lo delata es la columna `cobertura`. Es
la convención documentada del módulo, no un defecto, pero significa que comparar dos modelos
"donde los dos tienen WAPE definido" **corona ganador al que no predijo**. La primera versión
de `distribucion_de_mejora` hacía exactamente eso; lo cazó un test, y ahora la comparabilidad
exige cobertura **mayor que cero e igual** entre los dos. Vale para cualquier comparación
futura entre predictores, no solo para esta.

**Gate de salida de M2.5:** reporte comparativo contra el piso congelado, sobre sintético y
real, con el reparto por serie. **Cumplido con las dos tablas** —
`global-vs-baselines-real-2026-08-06.md` y `-sintetico-2026-08-07.md`. **367 tests**, `ruff`
limpio, **13/13 mutaciones caen**.

### 6.8 Evaluación de cierre de M2 (2026-08-06)

M2 está completo: las cinco unidades cerradas con evidencia ejecutada y el gate cumplido
(§6.7, ADR-017). Esta sección es la evaluación de la fase, no un resumen — dice **cuánto
compró de verdad**, qué costó, qué se aprendió que sobrevive a M2, y dónde está la palanca
que queda sin usar. Se escribe ahora y no en M3 porque el número que importa se lee una sola
vez: **la comparación contra el piso deja de ser posible en cuanto el motor promueva un
modelo.**

#### 1. Lo que compró, medido en lo promocionable y no en el titular

El titular de M2.3 —"el global le gana al piso en 11 de 12 celdas"— es cierto y **no es lo
que se entrega**, porque el global solo no resultó promocionable. Lo que se entrega es el
champion. La diferencia es grande:

| | h=1 | h=3 | h=6 | h=12 |
|---|---|---|---|---|
| ganancia del **champion** sobre el piso (grano producto) | **2,26%** | **2,64%** | **1,82%** | **1,49%** |
| ganancia que mostraba el **global solo** | 10,66% | 8,79% | 4,17% | −1,27% |
| ganancia del champion a nivel **total** | 9,72% | 6,93% | 7,45% | −1,57% |

**M2 compró entre 1,5% y 2,6% de WAPE a grano producto, sobre siete baselines clásicos.**
Ese es el número honesto de la fase, y conviene decirlo así antes de que circule el 10,66%.
A nivel total la ganancia es mayor (7–10%) porque los errores por producto se cancelan al
agregar, pero el producto sugiere órdenes **por producto**: el grano que manda es el primero.

**No es un mal resultado, es un resultado caro.** El piso ya era fuerte —siete candidatos
compitiendo con selección prospectiva y cascada— y ganarle 2% con un modelo global,
features de precio y deflación es consistente con lo que la literatura de M0 anticipaba
para series de este tipo. Lo que sí obliga es a no vender M2 como un salto.

#### 2. Lo que costó

En cómputo, M2 es barata; lo caro fue el piso de M1:

| unidad | costo medido |
|---|---|
| M2.1 deflación | 2,1 s sobre 137.399 filas |
| M2.2 features | 2,5 s sobre 116k filas |
| M2.3 modelo global | ~4 min las 18 cortes |
| M2.4 intervalos | 19,4 min (48 ajustes por corte) |
| M2.5 champion | **45 s**, cero modelos reajustados |
| *(referencia: el piso de M1)* | *294 min* |

La decisión de M1.7a —checkpointing reanudable— es la que hace que M2.5 cueste 45 segundos y
que M1.9 costara 12. **Se pagó dos veces y devolvió cuatro.** El corolario para M3: ninguna
corrida larga sin `--checkpoint-dir`, y los checkpoints no se borran hasta cerrar el análisis
que dependa de ellos.

#### 3. Las siete decisiones que M2 dejó registradas

ADR-011 (IPC empaquetado, *Propuesta*), **ADR-013** (la mitad de las features de precio eran
identidades algebraicas), ADR-014 (clima: comprometido en el Acta, no modelado — y el dato
del MVP es mock por contrato), ADR-015 (compromiso de precisión por horizonte, *Propuesta*,
con dos revisiones pendientes), **ADR-017** (lo promocionable es el champion). Más dos que son
de M1 pero se ejecutaron dentro de la ventana de M2 y sin las cuales M2 habría medido mal:
ADR-012 (universo) y **ADR-016** (selección prospectiva).

**Tres de esas siete se abrieron porque un número no cerraba, no porque estuvieran
planificadas.** Es el patrón de la fase: el plan describía qué construir y la medición
decidió qué de eso servía.

#### 4. Lo que se aprendió y sobrevive a M2

- **Un promedio esconde de qué está hecho, y pasó dos veces en dos unidades seguidas.** M2.4:
  el intervalo calibra en agregado (0,80) porque `suave` es la mayoría, mientras `erratica`
  sub-cubre 12 puntos. M2.5: el WAPE agregado es 86% `suave`, y ahí el global escondía errores
  de 2 a 3x en el 31% de los productos. **Ninguna decisión del motor se toma con un agregado
  solo**; va con su desagregado y con la columna de peso.
- **Una identidad algebraica se disfraza de feature** (ADR-013). `precio_prom × deflactor =
  ancla` en el 99,15% de las filas: a grano producto el monto deflactado *es* el target
  reescalado. Antes de gastar una feature, verificar que no sea el target con otro nombre.
- **El sintético no responde preguntas de negocio.** La ablación de precio da el signo opuesto
  ahí, y no es contradicción: `demanda.py` no mira el precio, así que esas features son ruido
  exacto. El sintético prueba que el pipeline corre; el número sale de datos reales.
- **Un fixture mal armado no falla: confirma.** Dos de M2.2 pasaban en verde sin probar nada, y
  uno de M2.5 (el del signo del sesgo) también. Los tres los cazó la mutación. **Un test que no
  cae con el bug puesto es decoración**, y la única forma de saberlo es romper el código a
  propósito.
- **Una tabla congelada sobre el sintético caduca cuando cambia el generador** (§6.4). Las de
  datos reales no. El `id` de corrida lo detecta, pero solo si alguien lo mira.
- **No predecir puntúa perfecto.** Una serie sin predicción da WAPE 0,0 y solo `cobertura` lo
  delata (§6.7). Cualquier comparación entre predictores tiene que exigir cobertura igual, no
  "métrica definida".

#### 5. La palanca que queda sin usar, y es la más grande de M3

El champion elige por `(serie, corte)`: ~2.100 decisiones por corte, cada una con poca
evidencia. Eso tiene un costo medible en varianza de selección — en `suave`, el champion es
**peor que el global solo** (0,2954 contra 0,2654 a h=1). La alternativa natural es elegir con
menos grados de libertad: **por `(cuadrante, corte)`**, que son 4 decisiones en vez de 2.100 y
usa la estructura que las tablas de M2.4 y M2.5 muestran que existe.

Estimación de la cota, **calculada con hindsight** (tomando el mejor de los tres por cuadrante
de la tabla final) y por lo tanto **no un resultado sino un techo**:

| h | champion (medido) | mejor por cuadrante (cota) | lo que el champion deja |
|---|---|---|---|
| 1 | 0,3230 | 0,2951 | **8,66%** |
| 3 | 0,3667 | 0,3377 | **7,91%** |
| 6 | 0,3928 | 0,3738 | 4,85% |
| 12 | 0,3644 | 0,3561 | 2,27% |

Y quién gana cada cuadrante también es informativo: **`suave` siempre el global; los tres
cuadrantes irregulares casi siempre el P50** (piso en `intermitente`/`lumpy` a h=12). O sea que
la estructura no es "un modelo mejor" sino "dos regímenes distintos": series suaves donde la
media condicional del global es el estimador correcto, y series a ráfagas donde lo es la
mediana. ADR-017 punto 3 lo anota: el P50 es en `intermitente`/`lumpy` **más preciso y menos
sesgado** que las otras dos opciones.

**Ojo con leer esto como "M1.7 se equivocó".** M1.7 midió que **enrutar por cuadrante con una
regla fija** (intermitentes → Croston/TSB, por teoría) era peor que dejar competir libre — y
sigue siendo cierto: `CrostonSBA` gana más en `suave` que en `lumpy`. Lo de acá es distinto:
**seleccionar por cuadrante con el error observado**, que es una selección aprendida y más
gruesa, no un ruteo teórico. Antes de adoptarlo hay que medirlo con regla prospectiva
(ADR-016), porque la cota de arriba está calculada mirando el final.

#### 6. Lo que M2 deja abierto

- **Las tres decisiones que estaban abiertas para el PM se consolidaron en una: ADR-018**
  (2026-08-06), que **reemplaza a ADR-015**. Eran la misma pregunta desde tres lados —sesgo por
  horizonte, cobertura del intervalo, precisión del punto— y las tres se contestan igual: **el
  eje de variación no es el horizonte, es el cuadrante** (4 a 9 veces contra 1,1). Antes de
  escalarlas se verificó que no fueran un bug reparable: **no lo son** (§6.9). Queda **una** fila
  de ratificación en `planning/roadmap.md` en vez de cuatro.
- **ADR-011 (IPC) sigue en `Propuesta`** y es la única dependencia externa del motor.
- **El peldaño laboratorio de la deflación lo usa 1 producto de 2.128**: los datos reales no lo
  ejercitan (§6.2).
- **`CLIENTE_FEATURE` diferida a M3.2**, y con ella la decisión de si el extract real se
  extiende a cliente×producto o M3.2 se valida solo en sintético.
- **12.700 filas que nadie cubre** — altas de catálogo. No se reparan con selección: son el
  hueco donde M3 puede ganar con features de categoría/laboratorio, y es lo mismo que §5.6.1
  ya había identificado.

#### 7. Qué habría hecho distinto

- **Congelar el piso antes de M2.3 estuvo bien; congelarlo con selección retrospectiva costó
  dos correcciones.** ADR-016 lo arregló, pero el problema estaba escrito en §12.5 desde el
  2026-07-29 como "decisión pendiente" y se ejecutó recién seis días después, con M2.3 ya
  encima. **Una trampa conocida y no cerrada se cobra sola.**
- **M2.4 midió la cobertura del intervalo solo por horizonte hasta que alguien pidió el
  desagregado.** El hallazgo (la sub-cobertura de `erratica`) apareció por mirar de más, no
  porque el gate lo pidiera. En M2.5 el desagregado por cuadrante fue parte del diseño desde el
  principio, y por eso el resultado se vio antes de congelar nada. **El desagregado no es un
  extra del reporte: es el reporte.**
- **Se escalaron tres decisiones al PM antes de verificar si eran decisiones.** Una de ellas
  —"¿el compromiso de cobertura se expresa por cuadrante?"— podía en principio no ser una
  decisión sino un bug de calibración. Averiguarlo costó **minutos**, porque los checkpoints
  estaban en disco (§6.9). **Se hizo tarde, después de haberla mandado dos veces al roadmap del
  PM.** La regla que queda: antes de escalar, gastar los minutos en comprobar que el problema
  no sea propio.

### 6.9 Se intentó calibrar el intervalo por post-proceso y no alcanza (2026-08-06)

**Por qué se midió.** M2.4 dejó `erratica` sub-cubriendo 10 a 13 puntos y eso quedó como decisión
del PM. Antes de mandarle una decisión, correspondía preguntarse si el motor podía **arreglarlo**
en vez de documentarlo: la sub-cobertura de un intervalo es, en principio, un defecto de
calibración, y la calibración se corrige por post-proceso sin tocar el modelo. Costo de averiguarlo:
minutos, porque los cuantiles ya están en los checkpoints de M2.4 y **no hay que reajustar nada**
— el mismo truco que abarató M2.5.

**Qué se probó.** Calibración conformal CQR (Romano et al. 2019) con la regla de observabilidad de
ADR-016: score de conformidad `s = max(P10 − y, y − P90)`, y para el corte `t` el ajuste
`q` es el cuantil 0,80 de los scores de las filas **cuyo mes objetivo ya ocurrió** (`anio_mes <= t`).
El intervalo calibrado es `[P10 − q, P90 + q]`; con `q` negativo el intervalo **encoge**, que es lo
que necesitan `intermitente` y `lumpy`. Se probaron dos granos de calibración: por `cuadrante` y por
`(cuadrante, horizonte)`.

**Resultado — cobertura empírica contra el 0,80 nominal, calibrando por `(cuadrante, horizonte)`:**

| cuadrante | h=1 | h=3 | h=6 | h=12 |
|---|---|---|---|---|
| `erratica` sin calibrar | 0,679 | 0,699 | 0,677 | 0,670 |
| `erratica` **calibrada** | **0,787** | 0,758 | 0,722 | **0,670** |
| `suave` sin calibrar | 0,782 | **0,801** | **0,801** | 0,799 |
| `suave` **calibrada** | 0,784 | 0,770 | 0,776 | 0,799 |
| `intermitente` calibrada | 0,857 | 0,923 | 0,911 | 0,907 |

**Tres conclusiones, y las tres son negativas para el post-proceso:**

1. **En `erratica` funciona a horizonte corto y se apaga con el horizonte.** +10,8 puntos a h=1,
   +5,9 a h=3, +4,5 a h=6 y **cero a h=12**. La razón es la regla de observabilidad y no la técnica:
   para calibrar el horizonte 12 en el corte `t` hacen falta predicciones emitidas en `t−12` cuyo mes
   ya ocurrió, y de esas hay muy pocas. **Calibrar horizonte largo prospectivamente es un problema de
   datos, no de método** — y aflojar la regla sería mirar el futuro, que es lo que ADR-016 cerró.
2. **En `intermitente` es imposible, y es estructural.** El **81,4%** de sus filas tiene `real == 0`
   **y** `P10 == 0` a la vez, así que su score de conformidad es exactamente `0`. El cuantil 0,80 de
   una distribución con un átomo del 81% en cero **es cero**: `q = 0,0000` y el intervalo no se mueve.
   No hay ajuste aditivo que encoja un intervalo cuando la mayoría de las observaciones caen justo en
   su borde. Es consecuencia directa de la densificación a ceros de ADR-010 — correcta y necesaria
   para medir — combinada con un P10 que, bien, predice cero.
3. **En `suave`, donde ya calibraba, empeora** (0,801 → 0,770 a h=3). El `q` estimado con la poca
   evidencia observable es ruidoso, y aplicarlo donde no hacía falta mete ese ruido.

**Consecuencia.** La dispersión de cobertura entre cuadrantes **no es un defecto reparable por
post-proceso**: es la señal de que unas series son intrínsecamente menos predecibles que otras. Eso
convierte la pregunta del PM de "¿cómo arreglamos esto?" en "¿cómo lo comunicamos?", y es lo que
resuelve **ADR-018**. Si algún día se quiere cerrar la brecha de `erratica`, hay que atacarla **en el
modelo** —features de volatilidad, o un modelo de dispersión aparte—, no después.

**No se abre unidad de trabajo.** `erratica` es el 11% de los productos y el 13% del volumen, la
mejora disponible a horizonte corto es de ~10 puntos de cobertura, y a horizonte largo —donde el
intervalo es el entregable según ADR-018— **no hay mejora**. Queda anotado en §12 como deuda con su
número, para que la decisión de retomarlo se tome con el costo a la vista y no de memoria.

> **Lo que este experimento vale más allá del resultado:** costó minutos porque los checkpoints
> seguían en disco. Una pregunta de diseño —"¿esto se arregla o se documenta?"— se respondió con
> medición en vez de con opinión, y el "no" quedó con su razón. **Antes de escalar una decisión,
> conviene gastar los minutos en verificar que sea de verdad una decisión y no un bug.**

### 6.10 M3.0 cerrada con resultado negativo — las features de dispersión no eran el problema (2026-08-07)

**La hipótesis, y por qué era buena.** M2.4 dejó `erratica` sub-cubriendo 10 a 13 puntos y §6.9
descartó arreglarlo por post-proceso. Quedaba una explicación estructural y verificable: los
cuadrantes se separan por dos ejes —**ADI** (cada cuánto vende) y **CV²** (cuánto varía cuando
vende)— y la especificación de features de M2.2 no tenía **ninguna** medida de dispersión, solo
`RollingMean`. `erratica` se diferencia de `suave` *únicamente* por el CV². Conclusión aparente:
**el modelo no puede distinguirlas.**

Y la evidencia parecía cerrar: donde el régimen **sí** es visible —el ADI, que se ve como ceros
en los lags— el modelo ensancha el intervalo hasta 13x; a `erratica` le daba la misma anchura
relativa que a `suave`. La falla estaba exactamente donde faltaba la feature.

**Qué se hizo.** `RollingStd` y CV (`std/mean` vía `Combine`) en las ventanas 3/6/12, detrás del
interruptor `usar_dispersion`. Corrida completa sobre el extract real, **21,6 min**, checkpoints
propios, cruzada fila a fila contra la de M2.4 —**305.309 filas, misma corrida `a79a9b23676b`,
misma cobertura de predicción (12.700 filas sin cubrir en las dos)**—, así que los números se
restan de verdad. Tabla congelada: `backtests/intervalos-global-real-dispersion-2026-08-07.md`.

#### El gate no se cumple, por los dos lados

**Gate 1 — cobertura del P10–P90 por cuadrante:**

| cuadrante | h=1 | h=3 | h=6 | h=12 |
|---|---|---|---|---|
| `erratica` M2.4 → M3.0 | 0,679 → 0,680 | 0,699 → 0,717 | 0,677 → 0,700 | 0,670 → 0,678 |
| **ganancia** | **+0,001** | +0,018 | +0,023 | +0,008 |
| `intermitente` | 0,857 → **0,386** | 0,923 → 0,801 | 0,911 → 0,922 | 0,907 → 0,900 |
| `lumpy` | 0,709 → **0,393** | 0,854 → 0,780 | 0,837 → 0,859 | 0,826 → 0,824 |
| `suave` | 0,782 → 0,761 | 0,801 → 0,782 | 0,801 → 0,784 | 0,799 → 0,788 |

**En `erratica` compra entre 0,1 y 2,3 puntos contra una brecha de 10 a 13.** No cierra nada. Y
**derrumba `intermitente` y `lumpy` a h=1** — 47 y 32 puntos de cobertura perdidos.

**Gate 2 — WAPE del punto (no podía empeorar):** empeora en 2 de 4 horizontes a grano producto
(+0,0011 a h=1 y +0,0018 a h=6; mejora 0,0027 a h=3 y 0,0047 a h=12). Marginal en las dos
direcciones —entre 0,4% y 1,3% relativo— pero el gate pedía que no empeorara en ninguno.

#### Por qué se derrumban los intermitentes, medido y no supuesto

No es que el intervalo se haya angostado: la amplitud relativa de `intermitente` a h=1 pasa de
1,648 a 1,662, prácticamente igual. **Lo que cambió es que el P10 se despegó del cero.**

| `intermitente` h=1 (83,7% de las filas tienen `real == 0`) | M2.4 | M3.0 |
|---|---|---|
| filas con `P10 == 0` exacto | **82,1%** | **31,4%** |
| aciertos en las filas de `real == 0` | **91,7%** | **35,5%** |

Con un panel densificado a ceros (ADR-010), la fila más frecuente de una serie intermitente es
`real == 0`, y acertarla exige `P10 <= 0`. El modelo viejo predecía **cero exacto** en el 82% de
esos casos —lo correcto— y el nuevo solo en el 31%. Las features de dispersión le dieron señal
para levantar el piso del intervalo justo donde el piso correcto era cero.

#### Lo que esto dice, que no es lo que yo esperaba

**La sub-cobertura de `erratica` no era un problema de información.** El modelo ya podía inferir
la dispersión: con lags 1, 2, 3, 6 y 12 más tres medias móviles, un árbol puede separar "el lag 1
está muy por encima de su media móvil" sin que nadie le pase un desvío. Darle la feature
explícita agregó casi nada porque **la señal ya estaba disponible en otra forma**.

Queda entonces abierta la pregunta de qué sí la causa. La candidata que este experimento **no**
toca es la que motiva la opción (b): el **pinball loss está en unidades del target**, así que las
series grandes —abrumadoramente `suave`, el 86% del volumen— dominan el ajuste de los modelos de
cuantil igual que dominan el WAPE agregado (§6.7). Ajustar cuantiles **por cuadrante** ataca ese
mecanismo, que es distinto del de información y sigue sin medirse. **Pero ojo con repetir el
error de esta unidad:** ahora hay que probarlo verificando que **no rompa el `P10 == 0` de los
intermitentes**, que es la parte que hoy funciona bien y resultó ser frágil.

**Un dato que no hay que pescar del ruido:** el WAPE a nivel total a h=12 mejora **11,9%** (0,0811
→ 0,0715). Es la celda más grande de mejora de toda la tabla y sería tentador quedársela. **No se
adopta:** la configuración falla el gate en cobertura y empeora el punto en dos horizontes, y
elegir una celda de la tabla final es exactamente el hindsight que ADR-016 sacó del piso. Queda
anotado para que M3.1 lo mire con una regla prospectiva si le sirve.

#### Estado y qué queda en el repo

**`usar_dispersion` queda en `False`, que es como se implementó.** El código, sus 5 tests y la
tabla congelada **se conservan**: sin ellos el resultado negativo no es reproducible y dentro de
seis meses alguien vuelve a proponer lo mismo. La deuda de §12.0 sigue abierta y ahora con una
hipótesis menos.

> **Que el default fuera `False` desde el principio no fue prolijidad, fue lo que salvó M2.** El
> `id` de corrida no incluye las features: con el interruptor encendido por defecto, las tablas
> congeladas de M2.3, M2.4 y M2.5 habrían empezado a dar otros números bajo el mismo `id`, y la
> única señal habría sido que `intermitente` sub-cubre — atribuible a cualquier cosa.

**Gate de salida de M3.0:** cobertura por cuadrante re-medida contra M2.4 a igual cobertura, y
WAPE del punto verificado. **Cumplido como procedimiento, no alcanzado como resultado: la
hipótesis se rechaza.** **372 tests**, `ruff` limpio.

## 7. M3 — Jerarquía, cliente y segmentos · S9–S12

| # | Unidad de trabajo | Semana | Entregable / gate |
|---|---|---|---|
| **M3.0** | **Features de dispersión** (`RollingStd` y CV sobre las ventanas 3/6/12 ya existentes), para cerrar la sub-cobertura del intervalo en `erratica`. **Unidad agregada el 2026-08-07 con su motivo, no estaba en el plan original** (§6.10): el diagnóstico de M2.4/M2.5 es que `erratica` se distingue de `suave` **únicamente por el CV²**, y la especificación de features de M2.2 no tiene **ninguna** medida de dispersión — solo `RollingMean`. El modelo no puede diferenciarlas. La evidencia lo respalda: donde el régimen **sí** es visible (ADI, que se ve como ceros en los lags) el modelo ensancha el intervalo hasta 13x, y a `erratica` le da la **misma anchura relativa que a `suave`**. Va antes de M3.1 porque cambiar features después obliga a rehacer la reconciliación | S9 | **Gate:** re-medir la cobertura empírica **por cuadrante** contra `intervalos-global-real-2026-08-06.md` (misma corrida, comparación fila a fila) **y** verificar que el WAPE del punto **no empeore** a ningún horizonte. Interruptor `usar_dispersion`, apagado por defecto hasta que la tabla decida — así las tablas congeladas de M2 siguen reproduciéndose. Si no cierra la brecha, la alternativa medida es **cuantiles ajustados por cuadrante**, que queda registrada acá y no se hace antes de tener este número. **❌ CERRADA 2026-08-07 con resultado NEGATIVO — la hipótesis se rechaza (§6.10).** En `erratica` compra entre 0,1 y 2,3 puntos contra una brecha de 10 a 13, y **derrumba `intermitente`/`lumpy` a h=1** (cobertura 0,857 → 0,386 y 0,709 → 0,393): las features le dieron señal al modelo para levantar el P10 por encima de cero justo donde cero era lo correcto — el `P10 == 0` exacto cae del 82,1% al 31,4% de las filas. El punto además empeora en 2 de 4 horizontes. **La dispersión ya era inferible de los lags**, así que no era un problema de información. `usar_dispersion` queda en `False`; el código, sus tests y la tabla se conservan para que el resultado negativo sea reproducible |
| **M3.1** | Reconciliación total → categoría → laboratorio → producto con `hierarchicalforecast`; bottom-up vs MinT **elegido por backtest**, no por preferencia | S9 | Forecasts coherentes; ganancia por nivel documentada |
| **M3.2** | Nivel cliente×producto: **P(compra en h)** (clasificación binaria LightGBM, mismas features) + tamaño esperado condicional. Es el output honesto: solo ~12% de los 319k pares tiene ≥12 meses de señal (EDA §5). **Recibe `CLIENTE_FEATURE`, diferida acá desde M2.2** (§6.3) | S10–S11 | Ranking de propensión; alimenta venta cruzada y redistribución (R3). **Dos precondiciones que hay que resolver acá y no antes:** (a) el **extract real no tiene cliente×producto** — o se extiende `extraer_snap.py` (túnel SSH, ~319k pares × 96 meses, mucho más pesado que lo de hoy) o M3.2 se valida solo en sintético, y eso se decide con el número de costo en la mano; (b) el generador **no modela altas ni bajas de cliente** (§12.1, deuda abierta de T0.4), así que hoy no ejercita el arranque en frío de un cliente nuevo — que es justo lo que pide M3.4 |
| **M3.3** | Clustering RFM propio sobre montos **deflactados** (CP-INF-04), versionado por corrida; contraste contra la segmentación operacional DFV (CP-SEG-01); **etiquetado por arquetipos fijos** (ver diseño abajo) + **composición diagnóstica** por cluster | S11 | Matriz de contingencia cluster × `segmento_operacional`; `cluster_id` **no** entra como feature (ADR-005); cada cluster muestra etiqueta legible estable entre corridas y su top categoría/producto/laboratorio |
| **M3.4** | Clientes nuevos (< 6 meses): prior del segmento operacional más cercano | S12 | Regla explícita y testeada |

**Decisión pendiente que hay que registrar en M3.2:** WAPE/MASE/sesgo (ADR-008) son métricas de error de forecast y **no aplican a un modelo de propensión**. Antes de cerrar M3.2 hay que fijar sus métricas (PR-AUC, lift@k, calibración) y registrarlas como ADR nuevo — ADR-008 no las cubre y dejarlo implícito es exactamente el vacío que ADR-008 vino a cerrar.

#### Diseño pendiente de M3.3: etiquetado estable + composición diagnóstica (2026-08-06)

**El problema que resuelve.** `cluster_id` es un número interno, arbitrario y **distinto cada corrida** (ADR-005) — necesario para que nunca sea feature, pero inutilizable tal cual para un operador que espera ver siempre los mismos nombres de segmento. Encadenar cada corrida contra la anterior (buscar a qué cluster de esta corrida se "parece más" el de la corrida pasada) no alcanza: la etiqueta deriva de a poco mes a mes sin que nadie lo decida, y depende de guardar el historial de la corrida previa.

**Diseño propuesto — arquetipos fijos, no encadenamiento:**

1. Se definen **una sola vez** (no en cada corrida) 4-6 puntos de referencia en el espacio R/F/M — ej. "Alto Valor" (R bajo, F alto, M alto), "Ocasional" (R alto, F bajo, M bajo), "En riesgo de fuga" (R alto, F/M históricamente altos), "Nuevo" (R bajo, F bajo, M bajo). Recomendado: calibrarlos con los mismos cortes **P33/P67** que ya usa la segmentación operacional de DFV (`docs/referencias/00_brainstorming.md:139`), porque eso favorece que "Alto Valor" en DemandSync coincida semánticamente con "alto valor" en el oráculo — ayuda directo a CP-SEG-01.
2. Cada corrida, el clustering (Ward o K-Means, ver ADR-005) encuentra sus grupos libremente. Cada centroide resultante se etiqueta con el arquetipo más cercano — no con el cluster de la corrida anterior.
3. Consecuencia: la etiqueta que ve el operador es **determinística por corrida**, sin retag manual en el caso normal. El administrador cura los arquetipos (coherente con CU-04: *"las etiquetas... son configurables por el administrador"*), no los clusters cada mes.
4. Casos borde a resolver en el diseño detallado: dos clusters cercanos al mismo arquetipo (colapsan bajo la misma etiqueta, sin error); un cluster que no se parece a ningún arquetipo (etiqueta de fallback tipo "Sin clasificar" + aviso al administrador — ahí sí interviene, solo cuando aparece un patrón genuinamente nuevo).

**Composición diagnóstica por cluster — no predicción cruzada.** Para cada cluster, mostrar qué categorías/productos/laboratorios están **presentes** en las compras (o predicciones ya calculadas de M3.2) de sus miembros — un `groupby(cluster) → top categorías/productos/laboratorios`, descriptivo. Ya lo piden los CU aprobados: CU-04 pide *"productos más comprados por el segmento"* y CU-05 arma venta cruzada por segmento. Es información que sale gratis de la arquitectura (B): la fila cliente×producto de M3.2 ya trae segmento (M3.3) y categoría/laboratorio (catálogo), así que cruzar es un `groupby` sobre una tabla que ya existe, sin modelo nuevo.

**Explícitamente fuera de alcance por ahora:** una *predicción* reconciliada por segmento×categoría (vs. solo mostrar composición descriptiva). Motivo: M3.1 reconcilia el árbol total→categoría→laboratorio→producto sobre series **agregadas sin cliente**, mientras M3.2 predice cliente×producto con un modelo distinto (propensión). Sumar M3.2 cruzado por segmento y categoría **no está garantizado que cierre** con el número de categoría que sale reconciliado en M3.1 — son dos caminos matemáticos al mismo total. Para composición diagnóstica esto no importa (no se promete que sume exacto); si más adelante se quiere un número de categoría-por-segmento con la misma garantía de coherencia que M3.1, hay que decidir si se reconcilian entre sí — no está resuelto y no bloquea M3.3.

**Nota de ownership:** cómo se **muestra** esto (heatmap, tabla, tarjetas) es diseño de Frontend (`frontend/`, stack sin definir, R4) — lo de acá es el contrato de datos que esa pantalla va a necesitar, no su UI.

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
| S4 | M1 | **Piso real congelado** (máquina autorizada) | M1.8 | ✅ **2026-08-03 — re-congelado** (§5.6.1): `backtests/baselines-real-2026-08-03.md`, corrida `a79a9b23676b`, 2.128 productos × 18 cortes (2024-11..2026-04) × h=12 en 294 min con `n_jobs=4` sobre `C:/dfv-extract-v2`. WAPE **0,287 / 0,128 / 0,103** (producto/categoría/total, h=1). Cobertura < 1 explicada al 100% en **dos** componentes (§5.6.1 punto 5): 69% altas de catálogo + **31% horizonte truncado por historia corta**, que es artefacto de la selección retrospectiva y corrige el "100% altas" que se reportó en §5.6. **Descompuesto contra la corrida anterior** reusando los checkpoints de ambas: el filtro de obsequios de ADR-012 **no movió el piso** (0,2939 → 0,2933), lo movía **el mes incompleto**; y al sacarlo se destapa un **sesgo total de −5,2% a h=6 y −6,0% a h=12, fuera del ±5% de M2** — el −1,4% de la corrida vieja era artefacto. La primera corrida (`f7af767ca7e6`, 2026-07-31) queda como registro histórico, no como referencia |
| S4 | M1 | **Regla de universo: obsequios y descontinuados** (corrección de M1.8a) | M1.8b | ✅ 2026-08-02 — **ADR-012**. `UMBRAL_PRECIO_OBSEQUIO = 0,05` a nivel renglón + `detectar_meses_incompletos()` contra la réplica atrasada. Universo 2.189 → **2.128**, extract 137.399 → **135.409** filas. **248 tests**, `ruff` limpio; los 9 nuevos verificados por mutación. **Deja al piso de M1.8 pendiente de re-congelar** (§5.5.1) |
| S4–S5 | — | Deuda del generador (precondición de M2.2, no bloquea M1) | T0.4 | ✅ 2026-07-31 (23 tests) |
| S5–S6 | M2 | Deflación (CP-INF-*) · features | M2.1–M2.2 | ✅ **M2.1** 2026-07-31 (67 tests) · **M2.2** 2026-08-04 — `motor/src/motor/features/`, gate de M1.3 cubierto (`pytest -m innegociable`), **274 tests**, `ruff` limpio, **7/7 mutaciones caen**. Validada a escala real en 3 cortes (cobertura 0,9899 sobre filas con precio propio; 2,5 s / 116k filas). **Tres correcciones a la lista de features** en §6.3 → **ADR-013**: el precio deflactado a grano producto es el ancla (identidad, CV 0,0000) y `revenue_real` es el target reescalado, así que la señal pasa a ser el **precio relativo al nivel**; `mismo_mes_año_anterior` era `lag 12`; **`CLIENTE_FEATURE` se difiere a M3.2** porque el extract real no tiene cliente×producto |
| S6 | M1 | **Selección prospectiva · re-congelado del piso** (cierra §12.5 — unidad agregada, ver §5.7) | M1.9 | ✅ **2026-08-05 — ADR-016**. `backtests/baselines-real-prospectivo-2026-08-05.md`, misma corrida `a79a9b23676b` reusando los checkpoints: **12 segundos**, cero modelos reajustados. El piso pasa a WAPE producto **0,331** (h=1, contra 0,287 retrospectivo) con cobertura h=12 **0,9104** (contra 0,8880), y lo que queda sin cubrir son **12.700 filas = exactamente las altas de catálogo de §5.6.1**. **Hallazgo que sale del alcance de la unidad:** el sub-pronóstico de horizonte largo era del criterio de selección, no de los baselines — el sesgo total cumple el ±5% en los cuatro horizontes, lo que obliga a revisar **ADR-015** antes de ratificarlo. **289 tests**, `ruff` limpio, gate `innegociable` cubierto, **9/9 mutaciones caen**. Detalle en §5.6.2 |
| S7 | M2 | LightGBM global · cuantiles | M2.3–M2.4 | ✅ **M2.3 2026-08-06** — `modelado/modelo_global.py` + `scripts/ablaciones_global.py`. Corre dentro del arnés y su reporte es **mergeable fila a fila** con el del piso (305.309 filas, mismo `id` `a79a9b23676b`, **las mismas 12.700 sin cubrir**). Configuración elegida por medición: **`precio+crudo`** — las features de M2.2 valen 0,0233 de WAPE a h=12 (6% relativo) y `LocalStandardScaler` **empeora 32%** a ese horizonte. Le gana al piso en **11 de 12** celdas nivel×horizonte. **Bloqueante resuelto:** `lightgbm 4.7.0` crashea con `pyarrow` cargado → pin `<4.7` + test en subproceso. **307 tests**, `ruff` limpio. Detalle en §6.4 (cambio de plan) y §6.5. · ✅ **M2.4 2026-08-06** — `backtesting/intervalos.py` + `modelado/modelo_global.py(cuantiles=)` + `scripts/intervalos_global.py`; tabla en `backtests/intervalos-global-real-2026-08-06.md` (misma corrida, 19,4 min). Cobertura empírica del P10–P90 **0,7798 / 0,8199 / 0,8130 / 0,8085** contra el 0,80 nominal, **sin recalibrar**. **Pero el agregado cancela dos errores opuestos:** `suave` calibra perfecto y `erratica` **sub-cubre 12 puntos** en los cuatro horizontes, mientras `intermitente`/`lumpy` sobre-cubren con amplitudes de hasta 13x el real → **decisión para el PM sobre ADR-015** (§6.6). El intervalo se invierte en **1 fila de 105.890**, así que M4.1 no necesita reordenar. El WAPE del punto reproduce **exacto** el de M2.3. **329 tests**, `ruff` limpio, **9/9 mutaciones caen**. Detalle en §6.6 |
| S8 | M2 | **Champion/challenger vs piso** | M2.5 | ✅ **2026-08-06 — ADR-017**. `backtesting/checkpoints.py` + `backtesting/comparacion.py` + `scripts/global_vs_baselines.py`; tabla en `backtests/global-vs-baselines-real-2026-08-06.md`. **45 s, cero modelos reajustados** (los checkpoints de las dos corridas comparten `id`). **Lo promocionable es el champion, no el global solo:** el global pierde a h=12 contra el piso (0,3746 vs 0,3699) y en `intermitente`/`lumpy` es **2 a 3x peor que el baseline** con sobre-pronóstico que crece con el horizonte (+511% en `lumpy` a h=12) — 31% de los productos, 0,6% del peso del WAPE. El champion gana los cuatro horizontes (**0,3230 / 0,3667 / 0,3928 / 0,3644**) con sesgo dentro del ±5%; los baselines se quedan con el **84%** de los pares. Cierra el P50 de §6.6: gana 3.512 turnos y mueve el WAPE 0,001, con sesgo −8,4%/−13,4% que viola ADR-008. **367 tests**, `ruff` limpio, **13/13 mutaciones caen**. Detalle en §6.7; **evaluación de la fase en §6.8** |
| — | **M2** | **Cierre de fase** | — | ✅ **2026-08-06 — gate cumplido (§6.7).** Evaluación en **§6.8**: la ganancia sobre el piso, medida en lo promocionable, es **1,5% a 2,6%** a grano producto (no el 10,66% del titular de M2.3, que era el global solo). Siete ADRs registrados, tres de ellos abiertos porque un número no cerraba. **La palanca más grande que queda:** seleccionar por `(cuadrante, corte)` en vez de por `(serie, corte)` — cota estimada con hindsight, **4,9% a 8,7%** |
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

### 12.0 La sub-cobertura del intervalo en `erratica` (abierta, con costo medido)

El intervalo P10–P90 sub-cubre **10 a 13 puntos** en el cuadrante `erratica`, en los cuatro
horizontes (M2.4, §6.6). **No se repara por post-proceso: se midió** (§6.9) — la calibración
conformal prospectiva recupera ~10 puntos a h=1 y **cero a h=12**, porque a doce meses vista casi
no hay error ya observado con el que calibrar sin violar ADR-016.

**Por qué no se abrió unidad de trabajo:** `erratica` es el **11% de los productos** y el **13%
del volumen**; la mejora disponible está en horizonte corto, donde el entregable comprometido es
el **punto** y no el intervalo (ADR-018 punto 1), y en horizonte largo —donde el intervalo *sí*
es el entregable— no hay mejora disponible por esta vía.

**Si se retoma, hay que atacarlo en el modelo, no después:** features de volatilidad de la propia
serie, o un modelo de dispersión separado del de nivel. Y antes de invertir, medir cuánto de la
sub-cobertura es irreducible: `erratica` está definida justamente por tener CV alto con demanda
frecuente, así que parte de esa brecha puede ser la varianza real del negocio.

> ⚠️ **Actualización 2026-08-07 — la primera de esas dos vías ya se probó y falló (§6.10).**
> `RollingStd` + CV en las ventanas 3/6/12 compra entre 0,1 y 2,3 puntos contra la brecha de 10 a
> 13, y de paso derrumba `intermitente`/`lumpy` a h=1. **La dispersión ya era inferible de los
> lags**, así que la sub-cobertura de `erratica` **no es un problema de información** y no hay que
> volver a atacarla por ahí. Queda en pie la segunda vía —un modelo de dispersión aparte— y una
> tercera que M3.0 no tocó: **ajustar los cuantiles por cuadrante**, porque el pinball loss está en
> unidades del target y las series grandes (86% `suave`) dominan el ajuste igual que dominan el
> WAPE agregado. Cualquiera de las dos tiene que probar además que **no rompe el `P10 == 0` de los
> intermitentes**, que hoy funciona y resultó frágil.

⚠️ **Lo que NO hay que hacer es ensanchar el intervalo a mano hasta que dé 0,80.** Eso lo pone
lindo en la tabla y le miente al usuario en la dirección contraria: un intervalo inflado sin
sustento no informa riesgo, solo lo simula. ADR-018 punto 2 elige documentar el número real.

### 12.1 Deuda del generador sintético → **T0.4**

> **✅ CERRADA 2026-07-31.** Las cuatro deudas están corregidas y bajo test; el detalle del
> cierre y los números logrados están al final de la sección. Lo que sigue abajo se conserva
> como el diagnóstico original —qué estaba mal y por qué importaba— porque es lo que explica
> las decisiones de calibración que quedaron en `parametros.py`.

Las cuatro se verificaron corriendo contra el dataset generado (semilla 42). Ninguna
bloquea M1, pero **la primera y la cuarta bloquean M2.2** (ambas son features de M2.2) y la
tercera debilita lo que el dataset puede validar.

**Cambio de alcance (2026-07-31):** la deuda #4 estaba anotada como "bonus" en §5.5 y se
incorpora acá como cuarto ítem, con su condición de gate. Motivo: la categoría deja de ser
solo una columna de desagregación del reporte y **pasa a ser feature de entrenamiento en
M2.2**, así que su distribución importa igual que las otras tres.

| # | Qué le falta al generador | Por qué importa |
|---|---|---|
| 1 | **`cliente_feature` es una foto única** — verificado: una sola `fecha_calculo` (2026-06) para las 1.600 filas | **M2.2 la usa como feature.** Un predictor que la consuma en un corte de 2024 estaría viendo el futuro. El arnés ya tiene el hook (`tablas_auxiliares`) pero no hay nada que recortar: el generador tiene que emitir una versión por mes. Hoy la única defensa es que ningún predictor la usa todavía |
| 2 | **Ningún mes con unidades netas negativas** — verificado: 0 filas con `unidades < 0` en las dos tablas de hechos | El ~9,5% de notas de crédito existe solo en el JSON del contrato; al agregar por mes el neto siempre queda positivo. En la realidad un mes puede cerrar negativo (más devoluciones que ventas), y ni el motor ni el ETL de R1 lo ejercitan nunca |
| 3 | **No modela altas ni bajas de producto** — verificado: **0 de 2.300 productos** tienen su primera venta dentro de la ventana de clasificación de 36 meses; la última primera-venta del dataset es de 2020 | La regla de calendario de **ADR-010** (arrancar en la primera venta de la serie) **no la ejercita ningún dato a escala**, solo tests unitarios. En datos reales los productos nuevos existen y son los de mayor incertidumbre. Un ADR-010 mal implementado pasaría toda validación sintética — de hecho pasó: el bug de la clave de `groupby` de M1.4 no lo detectó el sintético. **M1.8 lo ascendió de teórico a urgente**: el **69%** de la cobertura faltante del piso real son altas de catálogo, y el 31% restante son series con historia demasiado corta para el modelo — o sea que el fenómeno es todavía más amplio que "altas" (§5.6.1 punto 5) |
| 4 | **Las 8 categorías no existen** — `parametros.py:63` inventa `antiparasitarios`, `vacunas`, … y `catalogo.py:15` las reparte **uniforme** | Hasta M1 daba igual (la categoría sale del extract y solo desagrega el reporte). **En M2.2 pasa a ser feature.** Las 12 reales tienen distribución brutalmente despareja (`CLINICO` 723 contra `ACCESORIO` 19) e incluyen un bucket **`SIN CATEGORIA` del 22,4%** que no es un error de datos sino una realidad del catálogo: un quinto de los productos no tiene etiqueta, y el sintético le da categoría al 100%. Un `rng.choice` uniforme tampoco puede producir una categoría con **un solo producto** |

**Objetivos de calibración, medidos sobre el extract real (2026-07-31)** — sin esto el
generador inventaría proporciones, que es exactamente el error de la deuda #4:

| magnitud | real | sintético hoy |
|---|---|---|
| productos con primera venta posterior al mes 1 | 51,9% | 0% |
| alta dentro de la ventana de 36m | **20,0%** | 0% |
| **baja** (silencio > 24m que además supera el hueco más largo del propio producto) | **5,8%** | 0% |
| sin venta en los últimos 3m | 25,2% | 25,4% (forzado) |
| vida < 36 meses | 22,0% | 0% |

Dos cosas que la medición desarmó. **Una: el "13,8% sin venta hace más de 12 meses" no son
bajas** — con 42% de series intermitentes, un hueco de 12 meses es comportamiento normal. Por
eso el criterio exige que el silencio supere el hueco histórico del propio producto, y ahí la
tasa cae a 5,8%. **Dos: `sin_ancla_propia` ya reproduce el 25,4% agregado pero por el
mecanismo equivocado** — apaga exactamente los últimos 3 meses de todos, cuando en la realidad
ese 25% es una mezcla (5,8% muerto, más silencio reciente). Las bajas **no se suman** a
`sin_ancla_propia`: lo reemplazan parcialmente, o el 25% se vuelve 31% y se rompe EDA §4.

**Las bajas se correlacionan con el arquetipo** (medido, criterio estricto): `lumpy` 16,1% ·
`intermitente` 11,7% · `erratica` 5,5% · `suave` 3,3% — **lumpy muere 4,9× más que suave**. Se
preservan esos ratios y se escala el nivel al objetivo. Verificado que el gate de S0 aguanta:
con muerte diferencial la mezcla de supervivientes queda 49,3 / 30,0 / 10,3 / 10,5 contra el
objetivo 47,8 / 30,9 / 10,1 / 11,1 — **desvío máximo 1,5 puntos, dentro del ±3**.

**Trampa al implementar las altas:** el bucle de rechazo de `demanda.py:42` clasifica sobre
`serie[-36:]` crudo, sin la regla de ADR-010 que sí aplica `clasificar_series`. Con un producto
nacido hace 10 meses eso mete 26 ceros que nunca existieron, infla el ADI y lo calibra como
intermitente mientras el motor lo clasificaría distinto. **Compartir el clasificador no alcanza
si se lo llama con la ventana equivocada** — hay que recortar a `[mes_alta, mes_baja]`.

| # | Unidad de trabajo | Semana | Entregable / gate |
|---|---|---|---|
| **T0.4** | **Deuda del generador**, cuatro ítems: (1) `cliente_feature` versionada; (2) meses de neto negativo; (3) altas y bajas de producto a mitad de historia; (4) las 12 categorías reales con sus proporciones | S4–S5 (antes de M2.2) | Manifiesto que reporte las cuatro condiciones: nº de `fecha_calculo` distintas > 1; nº de meses con neto negativo > 0; % de productos con alta dentro de la ventana ≈ 20% y tasa de baja ≈ objetivo; desvío de la distribución de categorías dentro de tolerancia. **Más `motor/tests/test_generador_sintetico.py`**: hoy el generador no tiene ni un test, así que las cuatro condiciones tienen que quedar como aserciones ejecutables o T0.4 no tiene evidencia. **No bloquea M1**; sí es precondición de M2.2 |

#### T0.4 cerrado (2026-07-31)

Cinco banderas `gate_ok` en verde en `datasets/sintetico/manifiesto.json` (semilla 42, 2.300
productos, 36 s) y **23 tests** en `motor/tests/test_generador_sintetico.py`, que era el primer
test que el generador tiene en su vida.

| magnitud | objetivo | logrado | real |
|---|---|---|---|
| versiones de `cliente_feature` | > 1 | **32** | — |
| meses con neto negativo | > 0 | 257 (0,225%) | 281 (0,205%) |
| meses con neto cero | > 0 | 4.014 (3,521%) | 4.848 (3,528%) |
| precio implícito negativo | — | 25 | 22 |
| altas dentro de la ventana | 20,0% | **20,8%** | 20,0% |
| tasa de baja (criterio estricto) | 5,0% | **5,4%** | 5,8% |
| categorías presentes | 12 | **12** | 12 |
| desvío máximo de categorías | ±3 pts | 1,19 | — |
| desvío máximo de cuadrantes | ±3 pts | 1,21 | — |

**Los tests se verificaron por mutación**, no solo por estar en verde: rompiendo a propósito
las cuatro correcciones caen 7 tests. La trampa que más importaba —emitir 32 versiones de
`cliente_feature` calculadas todas sobre la historia completa y solo re-etiquetarlas, que deja
el leakage intacto y encima invisible— la cazan dos, uno de ellos por un invariante barato: una
`recency_dias` negativa significa que la versión vio una compra posterior a su propia fecha.

**Un test se borró por no pasar la mutación.** Verificaba que un cliente no apareciera en
versiones anteriores a su primera compra, y seguía verde con el bug puesto: el generador **no
modela altas de cliente**, los 1.600 existen desde el mes 1, así que la aserción no se puede
violar. Queda anotado abajo como deuda; el test vuelve el día que haya altas de cliente.

**Tres efectos medidos que conviene tener a mano:**

1. **`intermitente` se corrió de −1,25 a +1,21 puntos.** Los productos nuevos se clasifican
   sobre ventanas cortas y una ventana de 6 meses con dos ventas da ADI 3, o sea intermitente.
   Es realista —los productos nuevos reales también parecen intermitentes al principio— pero el
   objetivo del EDA ya se midió sobre datos que los incluían, así que el exceso sugiere que los
   nuevos del sintético parecen **más** intermitentes que los reales. Dentro del gate, anotado
   por si M2 encuentra algo raro en ese cuadrante.
2. **`sin_ancla_propia` sigue sobrando ~4 puntos** (29,5% contra el objetivo 25,4%). **Es
   preexistente, no lo introdujo T0.4**: el manifiesto anterior daba 30,0%. Sale de que los
   productos intermitentes se saltean los últimos 3 meses por azar, encima del forzado. Ver
   la deuda diferida abajo.
3. **Asignar 6,4% de bajas produce 5,4% medidas.** No es error de calibración: el criterio
   estricto no cuenta como baja a un producto cuyo silencio final no supera su propio hueco
   histórico, y un `lumpy` que ya tenía huecos de 30 meses puede morir sin ser reconocible. La
   misma brecha existe en los datos reales.

**Deuda diferida — `sin_ancla_propia` al 29,5% contra el 25,4% de EDA §4.** Preexistente, y se
difiere **por decisión explícita (2026-07-31)**: en la etapa académica el sintético no necesita
replicar las proporciones reales al punto, le alcanza con reproducir los *mecanismos*. Se anota
para resolverlo después, no se resuelve ahora. Tres cosas para quien lo levante:

- **Desvía en la dirección segura.** M2.1 ejercita el fallback categoría → laboratorio → IPC un
  poco **más** de lo que le tocaría, no menos. Si el desvío fuera al revés habría que arreglarlo
  antes de M2.1, no después.
- **El arreglo ya está escrito, en las bajas.** Mismo patrón que `_sortear_bajas` +
  `catalogo.py:41-43`: en vez de forzar `round(n × 0,254)` productos, contar primero cuántos se
  quedan sin venta reciente **solos** (los muertos ya se descuentan; faltan los intermitentes que
  se saltean los últimos 3 meses por azar) y forzar únicamente el resto. Requiere simular la serie
  antes de fijar la bandera, o estimar la probabilidad de hueco a partir de `p_occ` del arquetipo.
- **Vale la misma advertencia que las bajas.** Asignado ≠ medido: acá también hay que calibrar
  contra el número que sale del manifiesto, no contra el que se pone en `parametros.py`.

**Deuda nueva que abrió T0.4** (ninguna bloquea M2):

- **No hay altas ni bajas de cliente.** Los 1.600 existen desde el mes 1 y ninguno se va. Es el
  análogo de la deuda #3 a nivel cliente, y pega en **M3.2** (P(compra en h) por cliente×producto),
  no en M2.
- **`datasets/` está fuera del gate de lint.** `ruff check` corre sobre `motor/`; el generador
  tiene 7 líneas largas preexistentes que nadie ve. Es una línea de config, pero es decisión de
  equipo si se amplía el gate.

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
- **"Último mes completo" es calendario, no datos.** La réplica del snap se atrasa: el
  2026-08-02 tenía 2026-06 con 32% de las unidades normales y 2026-07 con una factura.
  El default de `--hasta` no lo sabía y el extract del 2026-07-31 se lo comió entero.
  Ahora `detectar_meses_incompletos()` corta la corrida y dice con qué `--hasta`
  re-extraer, pero **conviene mirar el aviso antes de gastar 214 min de backtest.**
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
- ~~**MAPE comunicacional** (ADR-008: solo en niveles agregados, para la UI) no está
  implementado. Probablemente sea del frontend (R4); acordarlo, no asumirlo.~~
  **Resuelto por ADR-015 punto 4 (2026-08-05):** el indicador de confianza de CU-03 pasa a
  ser el **intervalo P10–P90** de M2.4, que el motor sí produce, en vez de un badge de MAPE
  que nadie implementaba y del que nadie era dueño. Queda como pendiente documental del
  Analista (CU-03), no como deuda de código del motor.

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

**Actualización 2026-08-03: el costo dejó de ser cualitativo y tiene un segundo efecto que
no se había previsto — se paga en cobertura.** Al diagnosticar la cobertura del piso nuevo
(§5.6.1 punto 5) apareció que **5.655 filas, el 31% de las que no tienen predicción**, son
series jóvenes donde el ganador retrospectivo **no podía cubrir el horizonte pedido** aunque
otros 5 o 6 candidatos sí predijeron: `SeasonalNaive` gana la serie mirando todos los cortes
y después se aplica a los cortes donde tenía 2 meses de historia, y el naive estacional solo
proyecta tantos meses como historia tiene. Un procedimiento prospectivo no elegiría ese
modelo en ese corte. O sea que el hindsight no solo **infla el WAPE del piso**: además le
**baja la cobertura**, y como las filas que se caen son las de series nuevas —las más
difíciles— eso le mejora el WAPE otra vez, por omisión. Medido, rellenar esas filas empeora
el WAPE producto +0,0060 a h=6 y +0,0036 a h=12.

Esto refuerza la decisión de abajo y descarta media opción: **"darle al global el mismo
trato retrospectivo" ya no alcanza**, porque el trato retrospectivo no es solo un criterio
de selección más laxo, es una fuente de filas sin predicción. Nivelar hacia el lado
prospectivo es la única variante que hace las dos tablas comparables fila a fila.

**✅ CERRADA el 2026-08-05 — M1.9 / ADR-016.** Se niveló hacia el lado prospectivo, con
cascada por disponibilidad, y el piso se re-congeló con ese criterio
(`backtests/baselines-real-prospectivo-2026-08-05.md`). Los resultados están en **§5.6.2**;
tres cosas que esta sección no había anticipado:

- **La cascada era necesaria, no un complemento.** Sin ella la selección prospectiva
  **empeora** la cobertura (0,8651 contra 0,8880 a h=12): reelegir por corte deja *más*
  series con un ganador incapaz de cubrir el horizonte, no menos.
- **Lo que quedó sin cubrir son 12.700 filas, exactamente el número que §5.6.1 atribuyó a
  altas de catálogo.** El componente reparable se cerró entero.
- **El hindsight compraba más de lo previsto y no se agota con la evidencia:** la brecha
  sigue abierta en el último corte, con 17 cortes de historia acumulada. Solo el 15,7% de
  las series conserva el mismo ganador en los 18 cortes.

Y una consecuencia que caía fuera de lo que esta sección preveía: **el sub-pronóstico de
horizonte largo del piso era en su mayor parte del criterio de selección**, no de los
baselines — lo que obliga a revisar ADR-015 antes de ratificarlo (ADR-016, punto 5).

## 13. Fuera de este track

Deep learning (LSTM/transformers), pronóstico intra-mensual, optimización de precios, demanda censurada por quiebres, clima como driver de precisión (queda como feature explicativa/mock — viabilidad §3.4, formalizado en **ADR-014**: el dato del MVP es mock por contrato §6, así que entrenar sobre él no puede producir señal; la estacionalidad de calendario de M2.2 captura la parte predecible a 12 meses. **Ojo con CU-09:** su plantilla de respuesta hoy cita el clima como causa de una recomendación, y eso hay que corregirlo antes de R4). Tampoco entra: re-deduplicar factura/remito (es del exportador del lado cliente desde 2026-07-15), reglas de abastecimiento (R3, backend), ni dashboard (R4, frontend).
