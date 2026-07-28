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

**Última actualización:** 2026-07-27 — arnés de backtesting del motor terminado y relevado (M1.0–M1.4); siguen los baselines (M1.5+).

- Release: **R0** para el producto. **R1 (ingesta) sigue bloqueado por el contrato** (P1–P4); el motor ya no lo espera (ADR-009).
- Docs base + **ADR-001..010**. Aceptadas por autoridad técnica del ML Specialist: 007 (unidades), 008 (WAPE/MASE/sesgo), 010 (demanda cero explícita). **ADR-009 sigue en Propuesta: a ratificar con el Backend Dev** (no bloquea M1–M3).
- **EDA sobre datos reales** ✅ (`motor/eda/eda-2026-07-15.md`): 96 meses desde 2018-07, ~2.200 productos activos, cuadrantes 48/31/10/11%, 25,4% sin ancla propia, 53,5% de pares cliente×producto con ≤2 compras en 36m.
- **Contrato de ingesta v0.9** (`docs/contrato-ingesta.md`). Frontera acordada 2026-07-15: el cliente entrega **ventas unificadas**; DemandSync valida garantías y **no** re-deduplica. `tipo_comprobante` retirado del contrato y del DER.
- **Motor — hecho** (detalle, evidencia y gates en `motor/roadmap-motor.md`): **S0** (paquete instalable, capa de datos con diccionario espejo del DER, generador sintético determinístico) y **M1.0–M1.4** (arnés rolling-origin, métricas ADR-008 por nivel de agregación con cobertura, corridas identificadas, reporte tabular con cortes por horizonte/nivel/categoría/cuadrante, red anti-leakage, clasificador de cuadrantes). **82 tests verdes**, `ruff` limpio.
- **Motor — falta de M1:** M1.5/M1.6 (baselines `statsforecast` + rama intermitente Croston/SBA/TSB) → M1.7 (tabla congelada sobre sintético) → M1.8 (**piso real** en la máquina autorizada). Recién ahí hay un número que dice algo sobre calidad: **todo lo medido hasta hoy es plomería con un predictor de juguete.**
- Reglas del motor que no hay que romper: **`datasets/` importa del motor, nunca al revés**; al clasificar para enrutar método hay que pasar `hasta=corte` (si no, el modelo elige viendo el futuro); ninguna tabla se congela en `motor/backtests/` sin `id` de corrida.
- Pendientes inmediatos:
  - Resolver **P1–P4 del contrato** (exportador unificado del lado cliente, lotes, `precio` con/sin descuento, criterio `activo`) → congela v1.0.
  - Aplicar impacto de **ADR-007/008** al DER, CU y Plan de Pruebas UTN, de **ADR-009** a `arquitectura.md`, y de **ADR-010** al Plan de Pruebas (Analista Funcional — ver `planning/roadmap.md`).
  - `docs/arquitectura.md` dice "sin código" en su encabezado y ya no es cierto (Analista Funcional).
  - Correcciones C1–C8 al DER y T1–T6/CP-* al plan de pruebas (Analista Funcional).
- **Lección de método (2026-07-27):** "corre de punta a punta sin errores" ≠ "mide bien". El arnés pasó su primera revisión con 9 defectos de medición dentro, porque sus tests usaban un solo producto con 10 meses densos: 5 de los 9 eran indetectables por esa suite. Todo test de métrica tiene que incluir series dispersas/intermitentes, multi-producto y casos degenerados. Corolario: un hallazgo que no queda como test ejecutable es una opinión — se encoda **antes** de arreglar.
- Pendientes inmediatos:
  - Resolver **P1–P4 del contrato** (P1 = exportador unificado del lado cliente, lotes, `precio` con/sin descuento, criterio `activo`) → congela v1.0.
  - Aplicar impacto de ADR-007/008 al DER, CU y Plan de Pruebas UTN + de ADR-009 a `arquitectura.md` (Analista Funcional — ver `planning/roadmap.md`).
  - Correcciones C1–C8 al DER y T1–T6/CP-* al plan de pruebas (Analista Funcional).
- Código del repo: `motor/` — paquete `demandsync-motor` instalable + `motor/src/motor/datos/` (repositorio de archivos parquet, diccionario espejo del DER, test de conformidad de esquema) + `motor/src/motor/backtesting/` (arnés rolling-origin + métricas WAPE/MASE/sesgo); `datasets/sintetico/` — generador sintético. Sin modelos/baselines todavía (M1.5/M1.6 son el próximo paso). **R1 (ingesta) sigue bloqueado por el contrato**; el motor ya no.
