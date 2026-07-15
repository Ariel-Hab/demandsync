# motor/ — Motor de Predicción de Demanda

**Responsable:** ML Specialist. **Estado:** fase de diseño (Release 0/2). Sin código todavía.

## Alcance

Todo lo que ocurre entre los hechos mensuales materializados y la tabla `PREDICCION_DEMANDA`:

1. **Deflación read-time** (ADR-002): ancla por producto + índices de nivel + fallback, aplicada al armar features.
2. **Feature engineering**: lags, ventanas móviles, estacionalidad, features de cliente, precio real.
3. **Modelos**: baselines estadísticos → intermitentes → modelo global ML; clustering RFM propio.
4. **Backtesting**: protocolo de evaluación rolling-origin con métricas por nivel y horizonte.
5. **Empaquetado batch**: corridas versionadas (`EJECUCION_MODELO`), escritura de predicciones e intervalos.

## Interfaces

- **Entrada (lee de la base):** `HECHO_VENTA_MENSUAL_PRODUCTO`, `HECHO_VENTA_MENSUAL_CLIENTE_PRODUCTO`, `CLIENTE_FEATURE`, catálogo, `VARIABLE_EXTERNA`, `PARAMETRO_SISTEMA`.
- **Salida (escribe en la base):** `ANCLA_PRECIO_PRODUCTO`, `INDICE_PRECIO_NIVEL`, `SEGMENTO`/`CLIENTE_SEGMENTO`, `PREDICCION_DEMANDA` (con intervalos), `RECOMENDACION`, todo colgado de una `EJECUCION_MODELO`.
- El motor **no** expone HTTP ni lee JSON crudo del ERP: es una librería Python invocada por el job batch nocturno.

## Documentos

| Doc | Contenido |
|---|---|
| [`viabilidad.md`](viabilidad.md) | Informe de viabilidad: qué dice el estado del arte, qué permiten los datos del cliente 1, veredicto y adecuaciones |
| [`plan-diseno.md`](plan-diseno.md) | Plan de diseño e implementación del motor por fases (M0–M4), protocolo de backtesting, decisiones resueltas |
