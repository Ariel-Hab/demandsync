# DemandSync

**Sistema Inteligente de Predicción de Ventas para distribuidoras veterinarias.**
Proyecto Final de Ingeniería — UTN FRBA 2026 — Equipo Nº 207.

DemandSync es un Sistema de Soporte a la Toma de Decisiones (DSS): ingiere datos del ERP del cliente (ventas históricas, catálogo, lotes, clientes) y de fuentes externas, y genera predicciones de demanda, segmentación de clientes, recomendaciones de venta cruzada, alertas de vencimiento y borradores de orden de compra. **No es transaccional**: solo lee y sugiere; toda decisión la ejecuta un humano en el ERP.

## Primer cliente

El primer cliente es **DFV** (distribuidora veterinaria, ERP "defeve"). El diseño de datos y el contrato de ingesta están validados contra su sistema real — ver [`docs/datos-defeve.md`](docs/datos-defeve.md). El sistema se diseña genérico para distribuidoras, pero cada decisión se prueba contra los datos reales de este cliente.

## Estado actual

**Fase de diseño (pre-código).** Documentación validada, entorno definido, plan del motor de predicción en elaboración. No hay código todavía; el primer código entra con el Release 1.

## Mapa del repositorio

| Carpeta | Contenido | Responsable primario |
|---|---|---|
| `docs/` | Visión, arquitectura, realidad de datos del cliente, decisiones (ADR) | Todo el equipo |
| `docs/referencias/` | Docs de diseño heredados de DFV + correcciones al DER y plan de pruebas | — (solo lectura) |
| `planning/` | Roadmap por releases y planes de trabajo | PM |
| `motor/` | **Motor de predicción**: viabilidad, diseño, protocolo de evaluación | ML Specialist |
| `backend/` | Ingesta, API REST, reglas de negocio (FastAPI) — *placeholder* | Backend Dev |
| `frontend/` | Dashboard DSS + asistente RAG — *placeholder* | Frontend Dev |
| `infra/` | Docker Compose de desarrollo, base PostgreSQL + pgvector — *placeholder* | Backend Dev |
| `datasets/` | Datos de muestra **sintéticos/anonimizados** (los reales nunca se commitean) | ML Specialist |

## Documentos de entrada obligatoria

1. [`docs/vision-y-alcance.md`](docs/vision-y-alcance.md) — qué es y qué no es el producto.
2. [`docs/arquitectura.md`](docs/arquitectura.md) — módulos, stack, fronteras, flujo de datos.
3. [`docs/datos-defeve.md`](docs/datos-defeve.md) — qué datos existen de verdad en el cliente 1.
4. [`docs/decisiones.md`](docs/decisiones.md) — decisiones ya tomadas; no re-litigar sin ADR nuevo.
5. [`planning/roadmap.md`](planning/roadmap.md) — en qué release estamos y qué sigue.

## Equipo

| Integrante | Rol |
|---|---|
| Ian Feldman | Project Manager |
| Dan Judzik | Analista Funcional |
| Santiago Maffini | Backend Developer |
| Alejo Gurfein | Frontend Developer |
| Ariel Habib | Machine Learning Specialist |

## Regla de oro de datos

Los extracts reales del ERP del cliente **no entran al repositorio** bajo ninguna forma (ni JSON, ni dumps, ni notebooks con outputs). Ver `datasets/README.md`.
