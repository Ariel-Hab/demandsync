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
| Generador de dataset sintético para el equipo (`datasets/sintetico/`) — dos salidas: renglones del contrato + hechos mensuales | ML Specialist | ⬜ planificado en S0 del track del motor |
| **Ratificar ADR-009** (frontera de datos del motor: repositorio abstracto, motor desacoplado de R1) | Backend Dev | ⬜ no bloquea M1–M3; si se rechaza, rediseño de la capa de datos antes de M4 |
| Aplicar impacto de ADR-009 a `docs/arquitectura.md` (§Flujo de datos, §Entorno de desarrollo) **una vez ratificado** | Analista Funcional (con Backend) | ⬜ |
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
