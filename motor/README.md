# motor/ — Motor de Predicción de Demanda

**Responsable:** ML Specialist. **Estado:** fase de diseño (Release 0/2). Sin código todavía.

> **Regla de trabajo en este módulo (CLAUDE.md §6):** todo desarrollo se controla contra [`roadmap-motor.md`](roadmap-motor.md). Antes de codear, ubicá la tarea en una unidad de trabajo (`T0.x`/`M1.x`/…); si no existe, se agrega al roadmap primero. No se empieza un hito con el gate del anterior sin cumplir. Al terminar, se actualiza el estado de la unidad en el roadmap en la misma unidad de trabajo.

## Alcance

Todo lo que ocurre entre los hechos mensuales materializados y la tabla `PREDICCION_DEMANDA`:

1. **Deflación read-time** (ADR-002): ancla por producto + índices de nivel + fallback, aplicada al armar features.
2. **Feature engineering**: lags, ventanas móviles, estacionalidad, features de cliente, precio real.
3. **Modelos**: baselines estadísticos → intermitentes → modelo global ML; clustering RFM propio.
4. **Backtesting**: protocolo de evaluación rolling-origin con métricas por nivel y horizonte.
5. **Empaquetado batch**: corridas versionadas (`EJECUCION_MODELO`), escritura de predicciones e intervalos.

## Interfaces

- **Entrada:** `HECHO_VENTA_MENSUAL_PRODUCTO`, `HECHO_VENTA_MENSUAL_CLIENTE_PRODUCTO`, `CLIENTE_FEATURE`, catálogo, `VARIABLE_EXTERNA`, `PARAMETRO_SISTEMA`.
- **Salida:** `ANCLA_PRECIO_PRODUCTO`, `INDICE_PRECIO_NIVEL`, `SEGMENTO`/`CLIENTE_SEGMENTO`, `PREDICCION_DEMANDA` (con intervalos), `RECOMENDACION`, todo colgado de una `EJECUCION_MODELO`.
- El acceso a esas tablas es **a través de una interfaz de repositorio** con dos implementaciones —archivos locales y PostgreSQL— para que el motor se desarrolle y se evalúe sin depender del Release 1 (ADR-009, *Propuesta*: a ratificar con el Backend Dev).
- El motor **no** expone HTTP ni lee JSON crudo del ERP: es una librería Python invocada por el job batch nocturno.

## Desarrollo

```bash
cd motor
pip install -e ".[dev]"
pytest
```

Layout `src/`: el paquete importable es `motor` (`motor/src/motor/`). `datos/` (T0.3) y `backtesting/` (M1.1) se agregan como subpaquetes en sus propias unidades de trabajo — no existen todavía.

## Documentos

| Doc | Contenido |
|---|---|
| [`viabilidad.md`](viabilidad.md) | Informe de viabilidad: qué dice el estado del arte, qué permiten los datos del cliente 1, veredicto y adecuaciones |
| [`plan-diseno.md`](plan-diseno.md) | Plan de diseño e implementación del motor por fases (M0–M4), protocolo de backtesting, decisiones resueltas |
| [`roadmap-motor.md`](roadmap-motor.md) | **Track del ML Specialist:** los hitos M0–M4 desglosados en unidades de trabajo con entregable y gate de salida, cronograma en semanas relativas, dependencias externas y riesgos |
| [`eda/`](eda/) | Reportes de EDA sobre datos reales — solo métricas agregadas (ADR-006) |
| `backtests/` | Tablas de error congeladas por corrida (piso de baselines, champion/challenger) — solo métricas agregadas. Se crea en M1 |
