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

**Última actualización:** 2026-08-03 — **M1 CERRADO: el piso real quedó re-congelado** (`baselines-real-2026-08-03.md`, corrida `a79a9b23676b`, 2.128 productos × 18 cortes, 294 min). **M2.2 (features) está desbloqueada.** El hallazgo de la corrida: el sesgo de los baselines incumple el ±5% de M2 en horizonte largo, y el −1,4% que festejó la corrida anterior era artefacto del mes incompleto.

- Release: **R0** para el producto. **R1 (ingesta) sigue bloqueado por el contrato** (P1–P4); el motor ya no lo espera (ADR-009).
- Docs base + **ADR-001..010**. Aceptadas: 007 (unidades), 008 (WAPE/MASE/sesgo), 010 (demanda cero explícita). **ADR-009 sigue en Propuesta: a ratificar con el Backend Dev** (no bloquea M1–M3).
- **EDA sobre datos reales** ✅ (`motor/eda/eda-2026-07-15.md`): 96 meses desde 2018-07, cuadrantes 48/31/10/11%.
- **Contrato de ingesta v0.9** (`docs/contrato-ingesta.md`): el cliente entrega ventas unificadas; DemandSync valida garantías y no re-deduplica.
- **Motor — hecho** (detalle y gates en `motor/roadmap-motor.md`): **S0 y M1 CERRADO** — arnés rolling-origin con checkpointing reanudable, métricas ADR-008 por nivel con cobertura, clasificador de cuadrantes, los 7 baselines, la selección por serie, el extract del snap y **el piso congelado** (`baselines-real-2026-08-03.md`). **250 tests verdes**, `ruff` limpio.
- **Motor — sigue:** **M2.2 → M2.5** (features → champion/challenger). El extract canónico es **`C:/dfv-extract-v2`** (fuera del repo, son datos reales); `C:/dfv-extract` es el viejo y `-v3` una prueba con umbral $1 — **correr contra el directorio equivocado no falla, da otro número**. Regenerarlo requiere el túnel SSH de cotizaciones arriba (`docker compose --profile dev up`) y `pip install -e "motor[extract]"`.
- **M2.1 cerrada (2026-07-31):** `motor/src/motor/deflacion/` + el IPC del INDEC empaquetado (`motor.datos.ipc`, dato público, CC-BY). **235 tests**, `ruff` limpio. Cobertura de ancla **73,2% propia** contra el 74,6% que esperaba el EDA §4. La validación que más convence: deflactando el extract, el revenue anual real queda **plano entre 36.000 y 40.700 M de 2019 a 2025** mientras el nominal se multiplica por 29. Corre en 2,1 s sobre 137.399 filas. **Las constantes se midieron, no se eligieron** (`LIMITE_RELATIVO=3`: con 2 el clamp recorta la devaluación de dic-2023; con 3 deja de reaccionar a eventos macro).
- **Una cosa de M2.1 para el que siga:** el peldaño **laboratorio lo usa 1 producto** de 2.128 — los datos reales no lo ejercitan, se testea a mano o queda sin cubrir. *(El otro pendiente, el deflactor directo sin acotar, se cerró el 2026-08-02 — ver abajo.)*
- **M1.8b (2026-08-02, ADR-012) — el universo estaba mal.** Tres hallazgos: (a) los **obsequios** se facturan con un centinela de **$0,01** (el ERP exige `precio > 0`) y nunca se filtraron — se cortan **por renglón**, no por producto, porque el flag `producto.obsequio` marca 12 productos que **venden a precio real** y los 48 marcados cargan 0,92% del revenue; (b) el "." de los **descontinuados** vive en `descripcion`, no en `id`, y es subconjunto exacto de `disabled` — que **no tiene fecha**, así que aplicarlo hacia atrás es sesgo de supervivencia (184 productos vivos al corte 2024-12); (c) **la réplica del snap se atrasa**: "último mes completo" es calendario, no datos. Universo **2.189 → 2.128**. **248 tests**, `ruff` limpio.
- **El residuo del deflactor quedó cerrado (2026-08-02):** `LIMITE_DESVIO_NIVEL = 10` acota `q = d/d_nivel` contra **categoría y laboratorio, nunca contra el IPC**. La distinción es lo que evita contradecir a ADR-002 — la cascada *estima un precio que falta*, esto *valida uno observado* — y es lo que salva CP-INF-01, cuyo fixture usa la rama IPC. Deflactor máximo **13.821 → 319**, cero filas por encima de 1.000, revenue real total −0,32%. **250 tests.**
- **El piso re-congelado, en números** (`§5.6.1`, corrida `a79a9b23676b`): WAPE **0,287 / 0,128 / 0,103** (producto / categoría / total, h=1). **Ojo: la tabla real y la sintética NO se comparan entre sí** (composición distinta: 58% `suave` real contra 25% forzado).
- **Descompuesto contra el piso anterior** reusando los checkpoints de las dos corridas: **el filtro de obsequios de ADR-012 no movió el piso** (WAPE 0,2939 → 0,2933; el WAPE pondera por magnitud y esas 61 series son diminutas — 0,39% de las unidades). Lo que lo movía era **el mes incompleto**. ADR-012 era necesaria por el deflactor, no por el piso; no la recuerden al revés.
- **Decidido y diferido (2026-08-02):** CP-INF-03 no necesita cubrir todos los peldaños en esta etapa — el laboratorio lo usa 1 producto y ahora se ejercita de costado como nivel de contraste.
- **T0.4 cerrada (2026-07-31):** el generador ya emite `cliente_feature` en 32 versiones, meses de neto negativo y cero, altas y bajas de producto correlacionadas con el arquetipo, y las 12 categorías reales. Cinco `gate_ok` en el manifiesto y **23 tests** — los primeros que el generador tuvo. **Los tests se validaron por mutación:** rompiendo las correcciones caen 7, y uno se borró por seguir verde con el bug puesto. **M2.1 tiene un caso nuevo que cubrir:** 22 filas reales con precio implícito **negativo** por signos cruzados entre unidades y revenue (§5.5 #6), ya sembradas en el sintético.
- **El gate de sesgo de M2 NO es un trámite.** El piso da −3,4% (h=1) y −2,6% (h=3), pero **−5,2% (h=6) y −6,0% (h=12): fuera del ±5%**. Los baselines sub-pronostican sistemático en horizonte largo y el global tiene que **corregirlo**, no solo empatar el WAPE. El −1,4% de la corrida vieja salía de evaluar 1 de los 7 pares de h=12 contra un mes al 32%: achica `real` y corre `pred − real` hacia arriba, tapando el sub-pronóstico.
- **Cobertura < 1 en el piso real, explicada:** el 100% de las filas sin predicción son **altas de catálogo** (275 productos nuevos desde 2024-11, 226 de ellos `SIN CATEGORIA`). Ningún baseline cubre un producto que no existía en el corte. **M2.5 tiene que comparar a igual cobertura**, o es injusto en las dos direcciones.
- **Dos trampas del esquema real que el ETL de R1 también se va a comer** (§5.5, pendiente anotado para el Analista): **`producto.id` es `varchar(255)`** y `'2'`/`'02'`/`'0002'` son productos distintos que colapsan al mismo entero (23 colisiones) — castear el sku fusiona productos y ningún test lo nota; **`nota_credito` es `BIT(1)`** y llega como bytes, así que un `== 1` laxo hace que las devoluciones **sumen en vez de restar**.
- **El "13,8% de productos sin venta hace más de 12 meses" NO son bajas.** Con 42% de series intermitentes, un hueco de 12 meses es comportamiento normal. El criterio válido exige que el silencio final **supere el hueco más largo que ese producto ya tuvo estando vivo**, y ahí la tasa real cae a **5,8%**. Vale para cualquier análisis de discontinuados, no solo para el generador.
- **Hallazgo replicado tres veces:** ninguno de los 7 candidatos domina (el mejor se lleva **23%**) y **`CrostonSBA` gana mucho más en `suave` (315) que en `lumpy` (20)** — al revés de la teoría, y ya no es un artefacto del generador. Enrutar por cuadrante habría sido peor que dejarlos competir libres; no enrutar en M2/M3 sin volver a medirlo.
- **Cuidado al correr a escala:** `n_jobs` alto **mata la corrida** por archivo de paginación (`n_jobs=8` murió en el corte 5; usar **4**), y una corrida larga sin `--checkpoint-dir` es una apuesta perdida — el checkpointing ya salvó dos corridas. **Lanzala con `nohup`**: un proceso registrado como tarea de la sesión no sobrevive a un corte de sesión. Costo medido a 2.128 productos: **12→19 min por corte** (sube con la historia), **294 min las 18**. **Y no borres los checkpoints hasta cerrar el análisis**: separar "obsequios" de "mes incompleto" se pudo solo porque los de las dos corridas seguían en disco — se recortan subconjuntos de las predicciones ya hechas y se recalcula, sin reajustar nada.
- Reglas del motor que no hay que romper: **`datasets/` importa del motor, nunca al revés**; clasificar para enrutar exige `hasta=corte`; ninguna tabla se congela en `motor/backtests/` sin `id` de corrida; **los checkpoints del arnés son datos crudos y jamás se commitean** (en M1.8 son datos reales del cliente).
- **Si arrancás una sesión en `motor/` o `datasets/`, leé antes `motor/roadmap-motor.md` §12 y `motor/README.md` §Arranque.** El dataset sintético **no está en el repo** (regenerar por semilla); tres deudas del generador anotadas como **T0.4**.
- Pendientes inmediatos: resolver **P1–P4 del contrato** → congela v1.0; aplicar impacto de **ADR-007/008/009/010** al DER, CU, Plan de Pruebas y `arquitectura.md` (Analista Funcional — ver `planning/roadmap.md`); correcciones C1–C8 y T1–T6/CP-* al plan de pruebas (Analista Funcional).
- **Lección de método (2026-07-27, sigue vigente):** "corre sin errores" ≠ "mide bien" — todo test de métrica necesita series dispersas, multi-producto y casos degenerados; un hallazgo sin test ejecutable es una opinión. **Corolario (2026-07-30):** un test que *dice* cubrir un bug tampoco alcanza — verificá que falle sin el arreglo, o es decoración.
