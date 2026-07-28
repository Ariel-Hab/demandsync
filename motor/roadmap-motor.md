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
| **M1.5** | Baselines `statsforecast`: `SeasonalNaive`, media móvil, `AutoETS`, `AutoTheta`, `AutoARIMA` | S2–S3 | Corren sobre sintético dentro del arnés |
| **M1.6** | Rama intermitente: `CrostonSBA`, `TSB` (~42% de las series lo requiere — EDA §3) | S3 | Idem, con métricas separadas por cuadrante |
| **M1.7** | Selección **por serie** (mejor baseline por MASE) + **tabla de referencia congelada** sobre sintético | S3 | `motor/backtests/baselines-sintetico-<fecha>.md` |
| **M1.8** | **Corrida de validación real** en la máquina autorizada: extract propio desde el snap 2018→, mismo arnés, misma tabla | S4 | `motor/backtests/baselines-real-<fecha>.md` — **solo métricas agregadas**. Este es el piso a batir; se congela |

### 5.1 Relevamiento del 2026-07-27 — M1.1/M1.2 vuelven a 🟡 y se agrega M1.0

**Motivo del cambio de plan (CLAUDE.md §6.4).** M1.1 y M1.2 se habían declarado cerradas el 2026-07-27. Un relevamiento posterior —revisión propia + revisión adversarial independiente, todo verificado corriendo contra `datasets/sintetico/`— encontró que **las tres métricas de ADR-008 están mal medidas** y que faltan dos elementos del gate. La declaración de cierre fue incorrecta: se apoyó en una corrida de punta a punta "sin errores" (que sí corre) confundiéndola con "mide bien" (que no). Se revierte el estado y la remediación entra como unidad propia **antes** de M1.5/M1.6, porque un baseline medido con este arnés elegiría el método equivocado.

**Causa raíz común:** el código trata `hecho_venta_mensual_producto` como un panel denso de calendario, y es **dispersa** (un producto-mes sin venta no tiene fila; densidad 72,8%, 0 filas con `unidades == 0`). De ahí salen los defectos 1, 2 y 8.

| # | Unidad de trabajo | Semana | Entregable / gate |
|---|---|---|---|
| **M1.0** | **Remediación del arnés y las métricas.** ✅ (a) densificación de calendario → **ADR-010** + `backtesting/panel.py`; ✅ (b) escala de MASE sobre calendario denso, `train_df` ordenado y guarda de escala 0; ✅ (c) WAPE/sesgo por **nivel de agregación** (`columnas_nivel`: producto/categoría/total); ✅ (d) `n` y `cobertura` en toda salida de métrica + el arnés conserva las celdas no predichas; ✅ (e) validación de grano/unicidad y de nulos en columnas de agrupación; ✅ (f) `generar_cortes` sobre calendario; ✅ (h) `tablas_auxiliares` recortadas al corte; ✅ (g) identificador de corrida (`corrida.py`) + reporte tabular (`reporte.py`) + `motor/backtests/` con sus reglas | S1–S2 | **✅ CERRADO 2026-07-27.** Tests escritos primero, verificados con `--runxfail` para que fallaran por el defecto y no por un error de la prueba; los 9 defectos cerrados con su test de regresión. **51 tests verdes, ningún `xfail`, `ruff` limpio**, y validación a escala real: 345.000 filas comparables, niveles producto/categoría/total 0,804/0,136/0,081 a h=1, cobertura 1,0 vs 0,391 al omitir series, el fan-out de cliente×producto se rechaza, y el reporte markdown se genera con su `id` de corrida. Ver `backtesting/README.md` §Defectos |

**Gate de salida de M1:** existe una tabla de error de baselines, sobre datos reales, desagregada por horizonte × nivel × cuadrante, congelada y commiteada. A partir de acá **ningún modelo se promociona sin batirla** (disciplina baselines-first, CLAUDE.md §6).

**Precondición agregada al gate de M1 por el relevamiento:** ninguna tabla de referencia se congela (M1.7/M1.8) con M1.0 abierto. Las cifras que produce el arnés hoy no son piso de nada.

**No depende de:** contrato v1.0, R1, ni de trabajo de otros. M1.8 usa extract propio del snap (decisión #4 de `plan-diseno.md`), no el ETL.

## 6. M2 — Deflación y modelo global · S5–S8

| # | Unidad de trabajo | Semana | Entregable / gate |
|---|---|---|---|
| **M2.1** | **Transformador de deflación (ADR-002)**: ancla por producto + índices de nivel (media geométrica ponderada) + fallback categoría → laboratorio → IPC + clamp de ratios. Los casos CP-INF-01..05 se escriben como tests unitarios del transformador | S5 | Componente reutilizable + tests CP-INF-*; el fallback se testea con la misma prioridad que el ancla directa (lo necesita el 25,4% de los productos — EDA §4) |
| **M2.2** | Features: lags (1,2,3,6,12), rolling means (3,6,12), mes del año, `mismo_mes_año_anterior`, categoría/familia/laboratorio, `CLIENTE_FEATURE`, precio real deflactado y su variación | S5–S6 | Construcción de features pasando el test M1.3 |
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
| S3 | M1 | Baselines + intermitentes · tabla sintética | M1.5–M1.7 | ⬜ |
| S4 | M1 | **Piso real congelado** (máquina autorizada) | M1.8 | ⬜ |
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

## 12. Fuera de este track

Deep learning (LSTM/transformers), pronóstico intra-mensual, optimización de precios, demanda censurada por quiebres, clima como driver de precisión (queda como feature explicativa/mock — viabilidad §3.4). Tampoco entra: re-deduplicar factura/remito (es del exportador del lado cliente desde 2026-07-15), reglas de abastecimiento (R3, backend), ni dashboard (R4, frontend).
