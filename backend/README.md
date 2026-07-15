# backend/ — Ingesta, API y Reglas de Negocio

**Responsable:** Backend Developer. **Estado:** placeholder — el código entra en Release 1.

Alcance:
- **Ingesta (R1):** ETL de los JSON del contrato (`docs/datos-defeve.md`), deduplicación factura/remito (ADR-003), materialización de hechos mensuales inmutables (ADR-001), bitácora `PROCESO_INGESTA`.
- **API REST (R1→):** endpoints de consulta (< 2s contra vistas mensuales), predicciones, segmentos, alertas, borradores.
- **Negocio (R3):** Q sugerida = demanda predicha − (stock actual − stock seguridad), ajustada por lead time; alertas de vencimiento por gap de cobertura; redistribución.

Stack: FastAPI + SQLModel + Alembic + PostgreSQL 15 (+ pgvector). Ver `docs/arquitectura.md`.

El backend **no** implementa lógica de modelado: consume las tablas que escribe el motor (`PREDICCION_DEMANDA`, `SEGMENTO`, `RECOMENDACION`) versionadas por `EJECUCION_MODELO`.
