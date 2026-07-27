# Plan de Diseño del Motor de Predicción

**Fecha:** 2026-07-15
**Autor:** ML Specialist
**Prerequisito de lectura:** [`viabilidad.md`](viabilidad.md). Este plan implementa sus conclusiones.
**Cronograma y desglose:** [`roadmap-motor.md`](roadmap-motor.md) — este doc define *qué* se construye; el roadmap define *cuándo*, con gates de salida por hito.
**Estado:** diseño. M0 ✅ (2026-07-15). El código arranca sin esperar a R1: por **ADR-009** el motor lee hechos mensuales vía repositorio, con implementación de archivos locales (sintético / extract propio) hasta el swap a PostgreSQL en M4.

---

## Decisiones de diseño (cierran las 8 "decisiones abiertas" del brainstorming)

| # | Pregunta | Decisión | Fundamento |
|---|---|---|---|
| 1 | Variable objetivo | **Unidades** por producto (y por segmento) como target primario; a nivel cliente: P(compra) + tamaño esperado; revenue derivado por precio ancla | ADR-007; viabilidad §3.2–3.3 |
| 2 | Modelo global o por segmento | **Global** (cross-learning) con features categóricas de producto/categoría/laboratorio/segmento; challengers por serie | Evidencia M5; escala del dataset |
| 3 | Tech stack ML | `statsforecast` + `mlforecast` (LightGBM) + `hierarchicalforecast`; sin deep learning en el MVP | Viabilidad §2.8; baselines-first |
| 4 | Historial de training | **Extract propio desde el snap 2018→** (backfill una vez, incremental después); no depender del data mart de 25 meses del cliente | Único camino a los 96 meses |
| 5 | Separación física | El motor es **librería Python** dentro del monorepo, invocada por el job batch; no es servicio HTTP propio | Arquitectura; simplicidad MVP |
| 6 | Dashboard | Fuera del motor (Release 4, frontend) | Fronteras de módulos |
| 7 | Frecuencia de reentrenamiento | **Mensual**, alineada al cierre de mes de hechos; inferencia nocturna puede releer el último modelo | Grano mensual: reentrenar más seguido no aporta |
| 8 | Clustering explícito | **No** como feature (ADR-005); opcional como pooling interno con Ward determinístico si el EDA muestra segmentos de comportamiento muy distintos | ADR-005; evaluar post-M2 |

**Multi-horizonte:** estrategia **directa** — un modelo por horizonte (h=1..12, o al menos h∈{1,3,6,12}) en vez de recursiva. No acumula error de predicciones encadenadas y permite features específicas por horizonte. Costo: más entrenamientos — trivial a esta escala.

---

## Fases

### M0 — EDA y auditoría de datos (puede arrancar ya, máquina autorizada)
- Perfil por producto y por cliente×producto: ADI (intervalo medio entre demandas) y CV² → clasificación Syntetos-Boylan (smooth / erratic / intermittent / lumpy). Cuántas series caen en cada cuadrante decide cuánto pesa la rama intermitente.
- Verificación de la magnitud del doble conteo factura/remito (antes/después de dedup) — insumo para CP-DEDUP-01.
- Serie del índice implícito por producto: cobertura, huecos, % de productos que caerían al fallback categoría/lab, outliers de precio (calibrar el clamp).
- Mapa de eventos 2018–2026 (COVID, devaluaciones) sobre las series agregadas.
- Distribuciones para parametrizar el **generador sintético** de `datasets/`.
- **Entregable:** reporte con métricas agregadas (sin datos crudos) commiteado en `motor/eda/`; decisión final de granularidades a modelar.

### M1 — Baselines y arnés de evaluación (primer código del motor, sobre dataset sintético + validación real)
- Implementar el **arnés de backtesting** (ver abajo) ANTES que cualquier modelo. El arnés es el activo más importante del motor.
- Baselines con `statsforecast`: `SeasonalNaive`, media móvil, `AutoETS`, `AutoTheta`, `AutoARIMA`; para series intermitentes: `CrostonSBA`, `TSB`.
- Selección por serie: cada producto queda con su mejor baseline según MASE en backtest.
- **Entregable:** tabla WAPE/MASE/sesgo por nivel (total/categoría/producto) y horizonte (1/3/6/12). **Este es el piso a batir; se congela como referencia.**

### M2 — Deflación + modelo global ML
- Implementar ancla + índices de nivel + fallback + clamp (ADR-002) como transformador reutilizable, con el cuidado de leakage descrito abajo.
- `mlforecast` + LightGBM global: lags (1,2,3,6,12), rolling means (3,6,12), mes del año, `mismo_mes_año_anterior`, categoría/laboratorio, features de cliente (`CLIENTE_FEATURE`), precio real deflactado y su variación.
- Quantile regression (P10/P50/P90) para intervalos.
- **Criterio de promoción:** el global ML reemplaza al baseline **solo en las series/niveles donde le gana en backtest** (champion/challenger por serie).

### M3 — Jerarquía, cliente y segmentos
- Reconciliación total→categoría→laboratorio→producto (`hierarchicalforecast`, MinT/bottom-up según backtest).
- Nivel cliente: modelo de propensión P(compra en h) por cliente×producto (clasificación binaria LightGBM, mismas features) + tamaño esperado condicional. Alimenta venta cruzada y redistribución.
- Clustering RFM propio (sobre montos **deflactados**, CP-INF-04) versionado por corrida; contraste contra la segmentación operacional DFV (CP-SEG-01).
- Clientes nuevos (< 6 meses): prior del segmento operacional más cercano.
- **Entregable:** suite completa de predicciones coherentes + propensiones, con métricas por nivel.

### M4 — Empaquetado batch e integración
- Corrida = `EJECUCION_MODELO` (tipo, versión, hiperparámetros JSONB, métricas de backtest) → escribe `PREDICCION_DEMANDA` (con `limite_inferior/superior`) y segmentos.
- **Swap de la implementación del repositorio de archivos locales a PostgreSQL/SQLModel** (ADR-009). Es la única dependencia dura del motor con el Release 1: M1–M3 corren contra archivos.
- Contrato con backend: el job nocturno invoca `motor.correr(fecha_corte)`; el motor lee/escribe solo tablas (sin HTTP).
- Reentrenamiento mensual + monitoreo de degradación (comparar error realizado del mes vs backtest — insumo para detectar drift).

---

## Protocolo de backtesting (innegociable)

- **Paso 0 — densificación del calendario (ADR-010):** antes de medir, la serie se completa con **ceros explícitos** en los meses sin venta, desde la primera venta de cada serie hasta el último mes del período. Las tablas de hechos son dispersas (no persisten no-eventos) y medir directamente sobre ellas condiciona el error a que hubo venta: sobre-pronosticar donde la demanda fue cero queda invisible, que es el error dominante con 42% de series intermitentes. Se rellenan solo las columnas de cantidad; **`precio_prom` queda nulo, nunca cero** (un cero contaminaría el índice implícito de la deflación). Verificado sobre el sintético: sin este paso se pierde el 30,6% de los pares producto-mes y el WAPE a h=1 se reporta 0,53 cuando es 0,80.
- **Rolling origin:** cortes mensuales sobre los últimos 18 meses (ej. corte en t → entrenar con ≤ t → predecir t+1..t+12 → avanzar). Sin shuffle, sin k-fold clásico. Los cortes salen del **calendario**, no de los meses observados (si no, por serie individual los "cortes mensuales" quedan separados por saltos de varios meses).
- **Regla anti-leakage de deflación:** para el corte t, `precio_prom_hoy` y todos los índices se calculan **solo con datos ≤ t**. El ancla "de hoy" del backtest es el hoy de ese corte, no el actual. (Error sutil y letal: deflactar todo el histórico con el ancla presente hace que el modelo vea información del futuro vía precios.)
- **Métricas (ADR-008):** WAPE por nivel de agregación, MASE vs `SeasonalNaive` por serie, sesgo (%over/under). MAPE solo se reporta en niveles agregados para comunicación.
- **Cortes de reporte:** por horizonte (1/3/6/12), por cuadrante de intermitencia, por categoría. Un número global esconde todo.
- Períodos anómalos (COVID) se reportan con y sin exclusión.

## Definición de "listo" del motor (Release 2)

1. Arnés de backtesting reproducible corriendo sobre sintético y real.
2. Baselines congelados y documentados (tabla de referencia).
3. Modelo global gana a los baselines en WAPE en los niveles producto y categoría para h=1 y h=3 (para h=6/12 alcanza con empatar con mejor intervalo).
4. Sesgo global dentro de ±5% a nivel total.
5. Predicciones con intervalos escritas en `PREDICCION_DEMANDA` vía `EJECUCION_MODELO`, consultables < 2s.
6. Segmentos RFM no contradicen el oráculo DFV (CP-SEG-01) y los casos CP-INF-01..05 pasan.

## Fuera de alcance del motor (MVP)

Deep learning (LSTM/transformers), pronóstico intra-mensual, optimización de precios, demanda censurada por quiebres, clima como driver de precisión (queda como feature explicativa/mock — viabilidad §3.4).
