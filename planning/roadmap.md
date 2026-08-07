# Roadmap

**Fecha:** 2026-07-15 · última actualización 2026-07-25. Se actualiza al cierre de cada etapa.

> Este roadmap es el de **releases del equipo**. El track detallado del motor (hitos M0–M4 desglosados, cronograma, gates de promoción) vive en [`motor/roadmap-motor.md`](../motor/roadmap-motor.md), propiedad del ML Specialist.

## Estado actual: R0 — Validación y diseño (en curso)

Fase pre-código. Objetivo: que cada módulo tenga contrato, plan y criterio de éxito antes de escribir la primera línea.

| Tarea | Responsable | Estado |
|---|---|---|
| Repo + estructura + docs base (+ publicado en GitHub) | ML Specialist | ✅ 2026-07-15 |
| Correcciones al DER (C1–C8) incorporadas al drawio y al doc UTN | Analista Funcional | ⬜ |
| Correcciones al plan de pruebas (T1–T6, R6–R8, casos CP-*) en el .xlsm | Analista Funcional | ⬜ |
| Informe de viabilidad del motor (`motor/viabilidad.md`) | ML Specialist | ✅ 2026-07-15 |
| Plan de diseño del motor (`motor/plan-diseno.md`) | ML Specialist | ✅ 2026-07-15 |
| Ratificar ADR-007 (unidades como target) y ADR-008 (métricas) | ML Specialist | ✅ 2026-07-25 — ratificadas por autoridad técnica; equipo informado |
| Aplicar impacto de ADR-007/008 al DER y CU UTN (`PREDICCION_DEMANDA.cantidad_estimada`→unidades; `mape`→`metrica_error`+`tipo_metrica`/`wape`; CU-03 badge de confianza) — no cubierto por C1–C8 | Analista Funcional | ⬜ |
| Aplicar impacto de ADR-007/008 al Plan de Pruebas (criterios de aceptación R2 en WAPE/MASE/sesgo, casos de predicción de valor) | Analista Funcional | ⬜ |
| Contrato JSON de ingesta campo a campo (`docs/contrato-ingesta.md`) | Analista + Backend + lado cliente | 🟡 v0.9 redactado (2026-07-15); congelar v1.0 requiere resolver P1–P4 |
| Resolver P1–P4 del contrato (P1 = **exportador de ventas unificadas del lado cliente**; lotes; semántica `precio`; criterio `activo`) | Lado cliente + Analista | ⬜ |
| EDA sobre datos reales (perfil de intermitencia, dedup, ancla, calidad) | ML Specialist | ✅ 2026-07-15 — `motor/eda/eda-2026-07-15.md` |
| Track de desarrollo del motor (`motor/roadmap-motor.md`: M1–M4 desglosados, cronograma S0–S15, gates) | ML Specialist | ✅ 2026-07-25 |
| Generador de dataset sintético para el equipo (`datasets/sintetico/`) — dos salidas: renglones del contrato + hechos mensuales | ML Specialist | ✅ 2026-07-27 — determinístico por semilla; gate de intermitencia cumplido (desvíos ≤1,25 pts sobre ±3). Ya usable por backend (probar el ETL) y frontend (mockear) |
| **Ratificar ADR-009** (frontera de datos del motor: repositorio abstracto, motor desacoplado de R1) | Backend Dev | ⬜ no bloquea M1–M3; si se rechaza, rediseño de la capa de datos antes de M4 |
| Aplicar impacto de ADR-009 a `docs/arquitectura.md` (§Flujo de datos, §Entorno de desarrollo) **una vez ratificado** | Analista Funcional (con Backend) | ⬜ |
| Corregir el encabezado de `docs/arquitectura.md`: dice "diseño aprobado a nivel documental; **sin código**" y ya no es cierto — el motor tiene paquete instalable, capa de datos, arnés de backtesting y clasificador (ver `motor/roadmap-motor.md` §9) | Analista Funcional | ⬜ |
| Aplicar impacto de **ADR-010** (demanda cero explícita) al Plan de Pruebas: el supuesto de **demanda censurada** pasa de nota a criterio explícito — sin histórico de stock, un mes en cero puede ser "nadie lo pidió" o "no había stock" y el motor los trata igual (ya documentado en `motor/viabilidad.md` §3.5, ahora operativo en cada fila del panel) | Analista Funcional | ⬜ ADR ya Aceptada por el ML Specialist (es regla de medición interna del motor, no cambia hechos persistidos ni el contrato de ingesta) |
| **Dos trampas del esquema real halladas al construir el extract de M1.8** (2026-07-31, verificadas contra el snap). **(1) `producto.id` es `varchar(255)`, no un entero**, y conviven `'2'`, `'02'` y `'0002'` como productos DISTINTOS con proveedor y estado distintos: **23 colisiones** sobre 9.486 códigos numéricos. Si el ETL de R1 castea el `sku` a entero, fusiona productos reales y ningún test lo nota. **(2) `nota_credito` es `BIT(1)`**: el driver lo devuelve como bytes (`b'\x01'`), y una comparación laxa con `== 1` da `False` para TODA nota de crédito — las devoluciones sumarían en vez de restar. Impacto a evaluar en el DER (tipo de `producto.sku`), en el contrato de ingesta §1/§3 y en el Plan de Pruebas (caso de colisión de códigos y caso de NC). Detalle y mitigación del lado motor en `motor/roadmap-motor.md` §5.5 | Analista Funcional (con Backend) | ⬜ hallazgo del ML Specialist; el motor ya lo mitiga de su lado |
| **Aplicar impacto de ADR-012** (universo de productos: obsequios y descontinuados), 2026-08-02, verificado contra el snap. **(1) Los obsequios se facturan con un centinela de $0,01** porque el ERP exige `precio > 0` — 3.638 renglones desde 2018-07, más 200.334 facturados en `0`. Un ETL que no los filtre los suma como ventas. **(2) El flag `producto.obsequio` NO sirve como filtro**: 12 de los 48 del universo venden a precio real y los 48 cargan 0,92% del revenue; hay que cortar por renglón. **(3) Los descontinuados se marcan con "." en `producto.descripcion`** (460 en el catálogo), no en el `id`, y son subconjunto exacto de `producto.disabled`. **(4) `disabled` no tiene fecha** (NULL en 7.398 de 7.947), así que es estado actual como el stock de ADR-004 y no se puede aplicar a historia sin sesgo de supervivencia. Impacto a evaluar en el **contrato de ingesta §1/§3** (¿el exportador marca el renglón de obsequio, o DemandSync lo infiere por precio?), **DER** (`obsequio`/`disabled` como atributos de producto, y que `disabled` no tiene fecha), **Plan de Pruebas** (CP-INF-*, universo de CP-VOL-01) y `docs/datos-defeve.md`. Detalle en ADR-012 y en `motor/roadmap-motor.md` §5.5.1 | Analista Funcional (con Backend) | ⬜ hallazgo del ML Specialist; el motor ya lo mitiga de su lado |
| **Aplicar impacto de ADR-013** (features de precio real), 2026-08-04, medido sobre el extract real. Es un ajuste **de precisión, no de alcance**: el Plan de Pruebas tiene que dejar explícito que el monto deflactado de **CP-INF-04** (RFM de M3.3) es a grano **cliente**, donde conserva señal porque el descuento individual sobrevive. A grano **producto** el monto deflactado es `unidades × ancla` —el target reescalado— y el precio deflactado es el ancla (identidad algebraica, 99,1% de las filas reales), así que ninguna feature monetaria deflactada entra a ese grano. **No cambia ADR-002 ni ningún caso de prueba existente**; precisa el grano de uno. Detalle en ADR-013 y en `motor/roadmap-motor.md` §6.3 | Analista Funcional | ⬜ hallazgo del ML Specialist; el motor ya lo aplica de su lado |
| **Ratificar ADR-014** (el clima no es feature del modelo de demanda; queda como variable de contexto mock), 2026-08-05. **No es decisión del ML Specialist**: toca el *Objetivo del Producto* del Acta aprobada, por eso entra como Propuesta y no Aceptada. El motor ya opera así desde M2.2 —no hay ninguna feature climática en el código— así que lo que falta es la decisión de alcance, no el código. Sustento: el dato climático del MVP es **mock por contrato §6**, así que entrenar sobre él no puede producir señal; y a 6–12 meses el clima futuro no se conoce (evidencia en `motor/viabilidad.md` §2.6: el beneficio documentado es ~2% de ventas y se concentra en ≤7 días) | **PM** (dueño del alcance) + Analista Funcional | ⬜ |
| **Aplicar impacto de ADR-014** a los documentos formales: **Acta** (*Objetivo del Producto* 1 y 2: el clima se ingiere y se muestra, no se modela); **CU-03** *Supuestos* (retirar "la variable climática ya está incorporada al pipeline" — hoy es falso); **CU-09** pasos 4–5 (**retirar el clima de la plantilla de respuesta del asistente o marcarlo como contexto no causal**). Lo de CU-09 es lo que más urge y lo menos obvio: hoy el RAG está especificado para justificarle una recomendación a un vendedor citando una serie **simulada**, y ese vendedor le repite el argumento a la veterinaria. También `docs/vision-y-alcance.md` §1. El Gantt (tarea 41) **no cambia**: el mock se mantiene | **PM** (Acta) + Analista Funcional (CU, vision-y-alcance) | ⬜ |
| **Ratificar ADR-018** — *el compromiso de precisión se expresa por cuadrante de comportamiento, no por horizonte* (2026-08-06). **Reemplaza a ADR-015 y consolida en una sola decisión las tres entradas que este roadmap tenía abiertas sobre lo mismo** (sesgo por horizonte, cobertura del intervalo, precisión del punto). Qué cambió respecto de lo que se venía discutiendo: (a) el argumento del sesgo **se cayó** — ADR-016 mostró que el sub-pronóstico largo era del criterio de medición, y el modelo promovido cumple el ±5% en los cuatro horizontes; (b) la precisión varía **4 a 9 veces entre cuadrantes de comportamiento y 1,1 veces entre horizontes**, así que acotar por horizonte protege del eje chico y deja abierto el grande; (c) **se intentó arreglar la calibración del intervalo por post-proceso y no alcanza** (medido: en `intermitente` es imposible porque el 81,4% de las filas tiene score de conformidad exactamente 0). Lo que se pide decidir: el criterio de aceptación del R2 pasa a **nivel total y categoría** (donde está medido y cumplido: WAPE 0,109–0,146 total, sesgo dentro del ±5%), el grano producto se **documenta por cuadrante** como diagnóstico, y la advertencia de CU-03 pasa a depender del **cuadrante** en vez del horizonte | **PM** (dueño del criterio de aceptación) + Analista Funcional | ⬜ propuesto por el ML Specialist |
| **Aplicar impacto de ADR-018** a los documentos formales: **Acta** (*Riesgos* 5: registrar que se evaluó, se midió y **no** se invocó —la mitigación de "acotar al horizonte de 1 mes" ya no hace falta—; hito de validación del R2: criterios a nivel total y categoría, más tabla de diagnóstico por cuadrante); **CU-03** (el indicador de confianza pasa a ser el **intervalo P10–P90**, que **reemplaza al badge de MAPE** que ADR-008 dejó sin dueño; la advertencia de varianza pasa a depender del **cuadrante del producto**, no del horizonte — un `lumpy` avisa también a 1 mes); **Plan de Pruebas** (aceptación del R2 por nivel de agregación; la cobertura del intervalo se **documenta** por cuadrante, no se exige uniforme); **Matriz de Gestión de Riesgos** (la fila de RMSE/MAPE pasa a WAPE/sesgo por nivel) | **PM** (Acta, Matriz de Riesgos) + Analista Funcional (CU, Plan de Pruebas) | ⬜ |
| **Desfasaje entre el Gantt aprobado y el orden real de trabajo del motor** (relevado 2026-08-05, no requiere ADR — es planificación). La línea base pone hoy el arranque de "Servicio Clustering – Análisis RFM" (tarea 48, 08-04→08-18) y recién el 08-25 el inicio de series temporales (tareas 50–52). El motor fue al revés por disciplina **baselines-first**: arnés, 7 baselines y **piso real congelado** ya están (2026-08-03), y el clustering RFM es **M3.3**, planificado para S11. O sea: **muy adelantado en la línea de series temporales, atrasado en la de clustering.** Además la tarea 55 ("Evaluación MAPE y ajuste fino") presupuesta **3 días** para algo en lo que ya se gastaron ~500 min solo de backtest. Pedido concreto: **rebaseline de la línea de Core Predictivo**, o dejar registrada la desviación con su motivo antes del tercer tablero (2026-09-15) | **PM** | ⬜ relevado por el ML Specialist |
| Definir stack frontend | Frontend Dev | ⬜ (no bloquea R1–R3) |

**Criterio de salida de R0:** contrato JSON congelado (v1.0) + ADRs 007/008 resueltos.

## R1 — Fundamentos e Ingesta (Backend Dev + Analista)

Setup FastAPI/SQLModel/Alembic, PostgreSQL+pgvector, ETL del backfill 2018→ y del incremental mensual, **deduplicación factura/remito**, materialización de hechos mensuales, `CLIENTE_FEATURE`, bitácora `PROCESO_INGESTA`.
**Hito:** base poblada (sintética para el equipo, real en la máquina autorizada), consultas < 2s contra vistas mensuales, batch nocturno operativo. Casos: CP-DEDUP-01, CP-VOL-01.

Depende de: contrato JSON congelado (R0).

## R2 — Core Predictivo (ML Specialist, integración Backend)

Implementación del motor según `motor/plan-diseno.md`, ejecutada según el track de `motor/roadmap-motor.md`: deflación (ancla + índices + fallback), baselines, modelo global, backtesting, clustering RFM, endpoints de predicción.
**Hito:** métricas de error documentadas por horizonte y nivel; baselines batidos; segmentos no contradicen el oráculo DFV. Casos: CP-INF-01..05, CP-SEG-01.

Depende de: **R1 solo para la integración productiva** (M4: implementación PostgreSQL del repositorio + invocación batch). Por ADR-009 los hitos M1–M3 corren contra el dataset sintético y el extract propio de la máquina autorizada, así que **arrancan en paralelo a R1** — no lo esperan. Entregable del motor hacia el equipo: dataset sintético en S0; piso de baselines (insumo de los criterios de aceptación de R2 en el plan de pruebas) en S4.

## R3 — Reglas de Negocio y Abastecimiento (Backend Dev)

Necesidad de stock (demanda predicha + lead time + stock seguridad), alertas de vencimiento sobre **stock actual**, sugerencias de redistribución, borradores de OC exportables.
**Hito:** OC sugerida coherente y justificada. Casos: CP-STK-01, CP-STK-02.

Depende de: R2 (predicciones disponibles) + parámetros CU-10.

## R4 — Presentación y Explicabilidad (Frontend Dev + Backend)

Dashboard DSS, indexación RAG (pgvector), chat de explicabilidad, paneles de métricas.
**Hito:** flujo completo usuario final + justificación técnica vía RAG.

Depende de: R2/R3 (hay resultados que mostrar y explicar).

## Reglas de trabajo

- Cada release arranca con un plan corto en `planning/` (fecha absoluta en el encabezado) y cierra actualizando este roadmap.
- Decisión técnica importante durante un release → ADR en `docs/decisiones.md` antes de cerrar.
- Lo que dependa de datos reales se valida en la máquina autorizada; al repo van métricas y conclusiones.
