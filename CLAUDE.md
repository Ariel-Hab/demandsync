# CLAUDE.md — Guía Operativa para Agentes del Repositorio DemandSync

> Este repo lo usan **varias personas** (Equipo 207, UTN FRBA). Si sos un agente abierto por cualquier integrante, esta guía te da el contexto completo del proyecto y las reglas para trabajar sin pisar el trabajo de otros. Leela entera antes de tocar nada.

## 1. Qué es este proyecto

**DemandSync**: Sistema Inteligente de Predicción de Ventas para distribuidoras veterinarias. Proyecto Final de Ingeniería, UTN FRBA 2026, Equipo Nº 207. Es un **DSS de solo lectura**: ingiere datos del ERP del cliente y genera predicciones de demanda (1/6/12 meses), segmentación de clientes, recomendaciones de venta cruzada, alertas de vencimiento de lotes y borradores de orden de compra. No factura, no compra, no escribe en el ERP — solo sugiere; decide un humano.

**Primer cliente:** DFV, una distribuidora veterinaria real (ERP legado "defeve"). Todo el diseño de datos está validado contra su sistema real. El producto se diseña genérico, pero cada decisión se prueba contra este cliente.

**Estado actual: Release 0 (validación y diseño) para el producto, pero el motor ya tiene código.** La ingesta (R1) sigue bloqueada esperando que se congele el contrato de datos, así que backend, frontend e infra siguen en trabajo documental: contratos, planes y ADRs. El **motor** es la excepción por decisión explícita (ADR-009): accede a los datos por una interfaz de repositorio, así que se desarrolla y se evalúa contra archivos locales sin esperar la base — y de hecho ya tiene el arnés de backtesting, las métricas y el generador de dataset sintético funcionando. Ver `motor/roadmap-motor.md` para qué está hecho y qué falta.

## 2. Equipo y ownership — no pises el módulo ajeno

| Integrante | Rol | Módulo que le pertenece |
|---|---|---|
| Ian Feldman | Project Manager | `planning/` |
| Dan Judzik | Analista Funcional | `docs/` (contratos, casos de uso, validaciones) |
| Santiago Maffini | Backend Developer | `backend/`, `infra/` |
| Alejo Gurfein | Frontend Developer | `frontend/` |
| Ariel Habib | ML Specialist | `motor/`, `datasets/` |

**Regla:** trabajá en el módulo de quien te abrió. Si la tarea requiere cambiar un módulo ajeno o un contrato entre módulos (esquema de tabla, endpoint, formato de archivo), NO lo edites directamente: dejá el cambio propuesto documentado (issue, nota en `planning/`, o comentario en el doc del contrato) para acordarlo con el responsable. Los contratos entre módulos valen más que la conveniencia local.

## 3. Jerarquía de documentación (fuente de verdad, en orden)

1. **`docs/decisiones.md`** — ADRs. Las decisiones "Aceptadas" son vinculantes: **no las re-litigues ni escribas código/docs que las contradiga**; si hay motivo real para cambiar una, se registra un ADR nuevo que la reemplace.
2. **`docs/datos-defeve.md`** — qué datos existen DE VERDAD en el cliente 1 (y cuáles no). Cualquier diseño que asuma un dato que no figura ahí está mal.
3. **`docs/arquitectura.md`** — módulos, stack, flujo de datos, fronteras.
4. **`docs/vision-y-alcance.md`** — qué es y qué NO es el producto (límites explícitos).
5. **`motor/viabilidad.md` y `motor/plan-diseno.md`** — diseño del motor de predicción.
6. **`planning/roadmap.md`** — en qué release estamos, qué está pendiente y de quién.
7. **`docs/referencias/`** — historia de decisiones (docs heredados del trabajo con el cliente). **Solo lectura: nunca editar.** Ante conflicto entre un doc UTN formal y una corrección de `referencias/02_*`/`03_*`, gana la corrección (está validada contra el sistema real del cliente).

## 4. Regla de oro: datos del cliente

Este repo se comparte entre personas de dentro y fuera de la empresa cliente. Por lo tanto:

- **PROHIBIDO commitear datos reales del cliente**: ventas, clientes, precios, volúmenes, exports JSON, dumps, CSVs, o notebooks con outputs que los muestren. También credenciales, URLs internas, IPs o nombres de infraestructura del cliente.
- Los datos reales viven solo en la **máquina autorizada** (la del ML Specialist, que tiene acceso a la réplica del ERP). Al repo entran únicamente **métricas agregadas y conclusiones** (ej. tablas de error WAPE por categoría).
- El equipo desarrolla contra el **dataset sintético** de `datasets/sintetico/` (replica esquema y propiedades estadísticas, no registros). Si tu tarea necesita datos reales y no estás en la máquina autorizada, la salida correcta es: preparar el experimento para que lo corra el ML Specialist, no conseguir los datos.
- El `.gitignore` bloquea `datasets/*`; no lo debilites. Antes de cualquier commit que incluya archivos de datos o notebooks, verificá que no haya registros reales.

## 5. Contexto técnico rápido

- **Stack backend:** Python, FastAPI, SQLModel, Alembic, PostgreSQL 15 + pgvector (RAG). Batch nocturno; la API solo lee resultados materializados; consultas < 2s contra vistas mensuales agregadas.
- **Motor:** librería Python (no servicio HTTP) — `statsforecast` (baselines + intermitentes), `mlforecast` + LightGBM (modelo global), `hierarchicalforecast` (reconciliación). Invocada por el job batch; lee y escribe solo tablas.
- **Frontend:** a definir en R4 (no bloquea R1–R3).
- **Ingesta:** archivos JSON exportados del ERP según contrato congelado (ver `docs/datos-defeve.md`); deduplicación factura/remito obligatoria (ADR-003).
- **Conceptos clave del dominio que NO hay que violar:**
  - Hechos mensuales **inmutables y nominales**; nunca se persisten valores deflactados (ADR-001).
  - La deflación es read-time, con índice implícito por producto que **preserva el descuento individual** (ADR-002). Re-tasar `unidades × precio_hoy` está prohibido: borra el descuento.
  - Stock: solo foto actual; no existe histórico de movimientos (ADR-004).
  - `cluster_id` de segmentación jamás entra como feature de entrenamiento (ADR-005).
  - Todo resultado analítico se versiona por `EJECUCION_MODELO`.

## 6. Metodología de trabajo

- **Idioma:** español en docs, commits y nombres de dominio del código.
- **Plan antes de código:** para cualquier tarea que toque más de un archivo o cree estructura nueva, escribí primero un plan corto (qué archivos, qué cambios) y esperá confirmación de quien te abrió. Planes de etapa van en `planning/` con **fecha absoluta** (`**Fecha:** AAAA-MM-DD`) en el encabezado; al completarse la etapa, el plan se poda o se archiva actualizando `planning/roadmap.md`.
- **Control contra el roadmap del módulo** *(vigente hoy para `motor/` y `datasets/` → [`motor/roadmap-motor.md`](motor/roadmap-motor.md); se extiende a cada módulo cuando publique el suyo)*. Todo trabajo de desarrollo en el módulo se contrasta con su roadmap, antes y después:
  1. **Antes de empezar:** leé el roadmap y ubicá la tarea en una unidad de trabajo concreta (`T0.x`, `M1.x`, …). Si no encaja en ninguna, **no arranques**: o pertenece a un hito posterior, o falta la unidad de trabajo — en ese caso primero se agrega al roadmap (con entregable y gate de salida) y recién después se codea.
  2. **Respetá el orden y los gates:** no se empieza un hito si el gate de salida del anterior no está cumplido **con evidencia** (ver *Verificación*). Caso concreto en el motor: ningún modelo antes de que el arnés de backtesting y el piso de baselines estén congelados y commiteados.
  3. **Al terminar:** actualizá el estado de esa unidad en el roadmap del módulo **en la misma unidad de trabajo**. Prohibido dejarlo "para después" — misma disciplina que la documentación del TP.
  4. **Si el trabajo obliga a cambiar el plan** (reordenar, recortar, agregar o partir una unidad), el cambio se escribe en el roadmap con su motivo antes de seguir. Si además mueve un gate, una frontera entre módulos o un criterio de aceptación, va ADR.
- **Decisiones técnicas importantes** (regla de negocio descubierta, cambio de contrato, elección de librería estructural) → ADR en `docs/decisiones.md` (formato: contexto / decisión / consecuencias, con estado `Propuesta` hasta que el equipo la ratifique).
- **Documentación del TP siempre al día:** toda decisión de negocio que se tome o cambie (regla de negocio, alcance, métrica, contrato de datos) DEBE reflejarse en la misma unidad de trabajo en la documentación formal del trabajo práctico — los documentos UTN afectados (Acta, DER, Casos de Uso, Plan de Pruebas) y sus espejos en `docs/`. Está prohibido dejar la documentación divergente del acuerdo vigente "para después". Concretamente: cada ADR nuevo o modificado debe cerrar con una línea **"Docs impactados:"** listando qué documentos hay que actualizar, y la tarea no se considera terminada hasta que esa actualización esté hecha (o registrada como pendiente asignado en `planning/roadmap.md` si el doc formal lo edita otro rol).
- **Commits:** `<tipo>: <descripción imperativa, español, máx 72 chars>` — tipos: `feat`, `fix`, `docs`, `refactor`, `chore`, `test`. Agregá archivos explícitamente (no `git add -A`). No commitees trabajo a medias que rompa el build.
- **Verificación:** nada se declara "listo" sin evidencia ejecutada (test corrido, endpoint curleado, métrica calculada). En el motor rige además la disciplina **baselines-first**: ningún modelo se promociona si no le gana a los baselines en backtest (ver `motor/plan-diseno.md`).
- **No inventes datos del cliente:** si te falta un dato de negocio (¿existe tal campo? ¿cuántos meses de historia hay?), la respuesta está en `docs/datos-defeve.md` o hay que preguntarle al ML Specialist / Analista. No asumas.

## 7. Estado de la Misión

*(Instrucción para el agente: al cerrar una sesión de trabajo relevante, actualizá SOLO esta sección con el estado y los pendientes accionables, con fecha. Mantenela corta — máx ~15 líneas; el detalle va en `planning/roadmap.md`.)*

**Última actualización:** 2026-07-31 — **M1 CERRADO**. Piso real congelado en `motor/backtests/baselines-real-2026-07-31.md` (corrida `f7af767ca7e6`, 2.189 productos × 18 cortes, 214 min). Desde acá rige baselines-first: ningún modelo se promociona sin batir esa tabla. Sigue **M2** (deflación y modelo global), con **T0.4** como precondición de M2.2.

- Release: **R0** para el producto. **R1 (ingesta) sigue bloqueado por el contrato** (P1–P4); el motor ya no lo espera (ADR-009).
- Docs base + **ADR-001..010**. Aceptadas: 007 (unidades), 008 (WAPE/MASE/sesgo), 010 (demanda cero explícita). **ADR-009 sigue en Propuesta: a ratificar con el Backend Dev** (no bloquea M1–M3).
- **EDA sobre datos reales** ✅ (`motor/eda/eda-2026-07-15.md`): 96 meses desde 2018-07, cuadrantes 48/31/10/11%.
- **Contrato de ingesta v0.9** (`docs/contrato-ingesta.md`): el cliente entrega ventas unificadas; DemandSync valida garantías y no re-deduplica.
- **Motor — hecho** (detalle y gates en `motor/roadmap-motor.md`): **S0 y M1 completo** — arnés rolling-origin con checkpointing reanudable, métricas ADR-008 por nivel con cobertura, clasificador de cuadrantes, los 7 baselines, la selección por serie, el extract del snap y **las dos tablas congeladas** (sintética y real). **144 tests verdes**, `ruff` limpio.
- **Motor — sigue:** **M2** (M2.1 deflación → M2.5 champion/challenger). **T0.4 es precondición de M2.2.** El extract vive en `C:/dfv-extract` (fuera del repo, son datos reales); regenerarlo requiere el túnel SSH de cotizaciones arriba (`docker compose --profile dev up`) y `pip install -e "motor[extract]"`.
- **El piso real, en números** (`§5.6`): WAPE 0,32 / 0,15 / 0,12 (producto / categoría / total, h=1). **Sesgo total −1,4%**, que ya cumple el ±5% de M2 — el −10% del sintético era un artefacto del generador. **Ojo: la tabla real y la sintética NO se comparan entre sí** (composición distinta: 58% `suave` real contra 25% forzado).
- **Cobertura < 1 en el piso real, explicada:** el 100% de las filas sin predicción son **altas de catálogo** (301 productos nuevos desde 2024-12, 252 de ellos `SIN CATEGORIA`). Ningún baseline cubre un producto que no existía en el corte. **M2.5 tiene que comparar a igual cobertura**, o es injusto en las dos direcciones.
- **Dos trampas del esquema real que el ETL de R1 también se va a comer** (§5.5, pendiente anotado para el Analista): **`producto.id` es `varchar(255)`** y `'2'`/`'02'`/`'0002'` son productos distintos que colapsan al mismo entero (23 colisiones) — castear el sku fusiona productos y ningún test lo nota; **`nota_credito` es `BIT(1)`** y llega como bytes, así que un `== 1` laxo hace que las devoluciones **sumen en vez de restar**.
- **El sintético inventa 8 categorías que no existen** (`datasets/sintetico/parametros.py:63`). No afecta a M1.8 —la categoría sale del extract y además no entra al modelo, solo desagrega el reporte— pero sí a **M2.2**, donde pasa a ser feature. Corregirlo es deuda de **T0.4**; la distribución real ya está medida (§5.5) y es **muy despareja** —`CLINICO` 723 contra `ACCESORIO` 19— así que el generador, que reparte uniforme, necesita las proporciones y no solo los nombres.
- **Hallazgo replicado en datos reales:** ninguno de los 7 candidatos domina (el mejor se lleva el 31%) y **`CrostonSBA` gana mucho más en `suave` (322) que en `lumpy` (16)** — al revés de la teoría, y ya no es un artefacto del generador. Enrutar por cuadrante habría sido peor que dejarlos competir libres; no enrutar en M2/M3 sin volver a medirlo.
- **Cuidado al correr a escala:** `n_jobs` alto **mata la corrida** por archivo de paginación (`n_jobs=8` murió en el corte 5; usar **4**), y una corrida larga sin `--checkpoint-dir` es una apuesta perdida — el checkpointing ya salvó dos corridas. **Lanzala con `nohup`**: un proceso registrado como tarea de la sesión no sobrevive a un corte de sesión. Costo real medido: ~12 min por corte a 2.189 productos, ~3,6 h las 18.
- Reglas del motor que no hay que romper: **`datasets/` importa del motor, nunca al revés**; clasificar para enrutar exige `hasta=corte`; ninguna tabla se congela en `motor/backtests/` sin `id` de corrida; **los checkpoints del arnés son datos crudos y jamás se commitean** (en M1.8 son datos reales del cliente).
- **Si arrancás una sesión en `motor/` o `datasets/`, leé antes `motor/roadmap-motor.md` §12 y `motor/README.md` §Arranque.** El dataset sintético **no está en el repo** (regenerar por semilla); tres deudas del generador anotadas como **T0.4**.
- Pendientes inmediatos: resolver **P1–P4 del contrato** → congela v1.0; aplicar impacto de **ADR-007/008/009/010** al DER, CU, Plan de Pruebas y `arquitectura.md` (Analista Funcional — ver `planning/roadmap.md`); correcciones C1–C8 y T1–T6/CP-* al plan de pruebas (Analista Funcional).
- **Lección de método (2026-07-27, sigue vigente):** "corre sin errores" ≠ "mide bien" — todo test de métrica necesita series dispersas, multi-producto y casos degenerados; un hallazgo sin test ejecutable es una opinión. **Corolario (2026-07-30):** un test que *dice* cubrir un bug tampoco alcanza — verificá que falle sin el arreglo, o es decoración.
