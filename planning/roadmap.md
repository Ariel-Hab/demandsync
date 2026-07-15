# Roadmap

**Fecha:** 2026-07-15. Se actualiza al cierre de cada etapa.

## Estado actual: R0 — Validación y diseño (en curso)

Fase pre-código. Objetivo: que cada módulo tenga contrato, plan y criterio de éxito antes de escribir la primera línea.

| Tarea | Responsable | Estado |
|---|---|---|
| Repo + estructura + docs base (+ publicado en GitHub) | ML Specialist | ✅ 2026-07-15 |
| Correcciones al DER (C1–C8) incorporadas al drawio y al doc UTN | Analista Funcional | ⬜ |
| Correcciones al plan de pruebas (T1–T6, R6–R8, casos CP-*) en el .xlsm | Analista Funcional | ⬜ |
| Informe de viabilidad del motor (`motor/viabilidad.md`) | ML Specialist | ✅ 2026-07-15 |
| Plan de diseño del motor (`motor/plan-diseno.md`) | ML Specialist | ✅ 2026-07-15 |
| Ratificar ADR-007 (unidades como target) y ADR-008 (métricas) | Equipo | ⬜ |
| Contrato JSON de ingesta campo a campo (`docs/contrato-ingesta.md`) | Analista + Backend + lado cliente | 🟡 v0.9 redactado (2026-07-15); congelar v1.0 requiere resolver P1–P4 |
| Resolver P1–P4 del contrato (dedup/`estadistica`, lotes, semántica `precio`, criterio `activo`) | Lado cliente + Analista | ⬜ |
| EDA sobre datos reales (perfil de intermitencia, dedup, ancla, calidad) | ML Specialist | ✅ 2026-07-15 — `motor/eda/eda-2026-07-15.md` |
| Generador de dataset sintético para el equipo (`datasets/sintetico/`) — parámetros ya calibrados por el EDA | ML Specialist | ⬜ |
| Definir stack frontend | Frontend Dev | ⬜ (no bloquea R1–R3) |

**Criterio de salida de R0:** contrato JSON congelado (v1.0) + ADRs 007/008 resueltos.

## R1 — Fundamentos e Ingesta (Backend Dev + Analista)

Setup FastAPI/SQLModel/Alembic, PostgreSQL+pgvector, ETL del backfill 2018→ y del incremental mensual, **deduplicación factura/remito**, materialización de hechos mensuales, `CLIENTE_FEATURE`, bitácora `PROCESO_INGESTA`.
**Hito:** base poblada (sintética para el equipo, real en la máquina autorizada), consultas < 2s contra vistas mensuales, batch nocturno operativo. Casos: CP-DEDUP-01, CP-VOL-01.

Depende de: contrato JSON congelado (R0).

## R2 — Core Predictivo (ML Specialist, integración Backend)

Implementación del motor según `motor/plan-diseno.md`: deflación (ancla + índices + fallback), baselines, modelo global, backtesting, clustering RFM, endpoints de predicción.
**Hito:** métricas de error documentadas por horizonte y nivel; baselines batidos; segmentos no contradicen el oráculo DFV. Casos: CP-INF-01..05, CP-SEG-01.

Depende de: R1 (hechos mensuales poblados).

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
