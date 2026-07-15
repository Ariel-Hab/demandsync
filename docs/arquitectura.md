# Arquitectura

> Última actualización: 2026-07-15. Estado: diseño aprobado a nivel documental; sin código.

## Principios

1. **Desacoplamiento estricto entre módulos** (mitigación del riesgo 2 del acta): contratos REST + tablas versionadas; cada módulo se puede desarrollar y probar con mocks del resto.
2. **Hechos inmutables, derivados recalculables**: lo ingestado nunca muta; todo lo que depende de "hoy" (deflación, features, predicciones) se recalcula y se versiona por corrida.
3. **Batch nocturno**: ingesta, entrenamiento e inferencia corren offline; la API solo lee resultados materializados.
4. **El motor es una librería, no un servicio**: se invoca desde el job batch; no expone HTTP propio. La API REST del backend sirve sus resultados.

## Flujo de datos

```
ERP cliente (defeve) ──export──▶ archivos JSON (esquema congelado)
                                      │
                              [backend/ingesta ETL batch]
                                      │  dedup factura/remito, validación, normalización
                                      ▼
                    PostgreSQL: VENTA/DETALLE_VENTA (crudo, inmutable)
                                + HECHO_VENTA_MENSUAL_PRODUCTO
                                + HECHO_VENTA_MENSUAL_CLIENTE_PRODUCTO   ← ancla del sistema
                                + CLIENTE_FEATURE (features desde Analytics DFV)
                                + LOTE (stock actual), catálogo, VARIABLE_EXTERNA
                                      │
                              [motor — batch nocturno]
                                      │  deflación read-time (ancla + índices) → features → modelos
                                      ▼
                    PREDICCION_DEMANDA / SEGMENTO / RECOMENDACION  (versionado por EJECUCION_MODELO)
                                      │
                              [backend/negocio]
                                      │  stock actual + lead time + stock seguridad
                                      ▼
                    ALERTA_VENCIMIENTO / SUGERENCIA_REDISTRIBUCION / BORRADOR_ORDEN_COMPRA
                                      │
                              [API REST FastAPI]
                                      ▼
                    [frontend: dashboard DSS + chat RAG (pgvector)]
```

## Stack

| Capa | Tecnología | Justificación |
|---|---|---|
| API + ETL + negocio | Python, FastAPI, SQLModel, Alembic | Definido en el acta (Release 1); experiencia del equipo |
| Base de datos | PostgreSQL 15 + pgvector | Relacional + vectorial en una sola base (RAG) |
| Motor de predicción | Python: `statsforecast` (baselines estadísticos e intermitentes), `mlforecast` + LightGBM (modelo global ML), `hierarchicalforecast` (reconciliación) | Estado del arte accesible; evita implementar modelos a mano — ver `motor/viabilidad.md` |
| Jobs batch | Scheduler simple (cron / APScheduler) dentro del contenedor backend | Suficiente para batch nocturno; sin orquestador pesado en el MVP |
| Frontend | A definir por el Frontend Dev en R4 (el acta sugiere gestión de estados tipo Riverpod/Flutter; una SPA web también cumple) | Decisión diferida — no bloquea R1–R3 |
| Infra dev | Docker Compose (postgres + backend) | Reproducible en cualquier máquina del equipo |

## Modelo de datos

El DER oficial (25 entidades, 9 módulos) está en el documento UTN *Especificación del Modelo de Datos*, **con las correcciones C1–C8 de `referencias/02_correccion_der_demandsync.md` incorporadas como obligatorias**, en particular:

- **C1** — capa de hechos mensuales (`HECHO_VENTA_MENSUAL_*`): sin esto no se cumple ni la deflación ni el `<2s`.
- **C2** — entidades de deflación (`ANCLA_PRECIO_PRODUCTO`, `INDICE_PRECIO_NIVEL`).
- **C3** — `CLIENTE_FEATURE` (features de Analytics DFV).
- **C6** — `VENTA.tipo_comprobante` + regla de deduplicación.

## Entorno de desarrollo y datos

- Cada dev levanta `infra/docker-compose.yml` (cuando exista) con PostgreSQL + pgvector local.
- **Los datos reales del cliente no salen de la máquina autorizada** (la que tiene acceso al snap de DFV). El equipo trabaja con datasets sintéticos/anonimizados en `datasets/` que replican el esquema y las distribuciones (intermitencia, estacionalidad, inflación) del real.
- El ML Specialist corre los experimentos con datos reales localmente y publica al repo **solo métricas agregadas y conclusiones**, nunca los datos.

## Ownership

| Módulo | Responsable | Backup |
|---|---|---|
| Ingesta + API + negocio (`backend/`) | Backend Dev | Analista Funcional (contratos y validaciones) |
| Motor (`motor/`) | ML Specialist | Backend Dev (integración batch) |
| Frontend + RAG UI (`frontend/`) | Frontend Dev | — |
| Infra dev (`infra/`) | Backend Dev | — |
| Contratos de datos con el cliente (`docs/datos-defeve.md`) | Analista Funcional + ML Specialist | — |
