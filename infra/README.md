# infra/ — Entorno de desarrollo

**Responsable:** Backend Developer. **Estado:** placeholder — se crea al inicio de Release 1.

Contenido previsto:
- `docker-compose.yml` de desarrollo: PostgreSQL 15 + pgvector, backend FastAPI con bind-mount del código, job batch.
- Scripts de inicialización de base (extensión pgvector, esquema vía Alembic).
- Carga del dataset sintético (`datasets/sintetico/`) para levantar un entorno funcional sin datos reales.

El MVP del proyecto se despliega **local** (restricción del acta); no hay infraestructura de producción en el alcance UTN.
