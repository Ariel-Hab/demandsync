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
| 2 | Modelo global o por segmento | **Global** (cross-learning) con features categóricas de producto/categoría/laboratorio/**segmento operacional DFV**; challengers por serie | Evidencia M5; escala del dataset |
| 3 | Tech stack ML | `statsforecast` + `mlforecast` (LightGBM) + `hierarchicalforecast`; sin deep learning en el MVP | Viabilidad §2.8; baselines-first |
| 4 | Historial de training | **Extract propio desde el snap 2018→** (backfill una vez, incremental después); no depender del data mart de 25 meses del cliente | Único camino a los 96 meses |
| 5 | Separación física | El motor es **librería Python** dentro del monorepo, invocada por el job batch; no es servicio HTTP propio | Arquitectura; simplicidad MVP |
| 6 | Dashboard | Fuera del motor (Release 4, frontend) | Fronteras de módulos |
| 7 | Frecuencia de reentrenamiento | **Mensual**, alineada al cierre de mes de hechos; inferencia nocturna puede releer el último modelo | Grano mensual: reentrenar más seguido no aporta |
| 8 | Clustering explícito | **No** como feature (ADR-005); opcional como pooling interno con Ward determinístico si el EDA muestra segmentos de comportamiento muy distintos | ADR-005; evaluar post-M2 |

**Cuál "segmento" es el de la decisión 2.** El **operacional de DFV** (`CLIENTE_FEATURE`), el único que ADR-005 admite como feature — **nuestro `cluster_id` de RFM nunca entra** (ver *El segmento es salida, no entrada* en M3). Leído al revés, ese casillero parece contradecir ADR-005. Además solo aplica al modelo **cliente×producto de M3.2**: una fila producto-mes de M2.3 no tiene cliente, así que no tiene segmento.

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
- Selección por serie: cada producto queda con su mejor baseline según MASE en backtest. Los candidatos compiten **libres en toda serie**: el cuadrante de intermitencia desagrega el reporte pero no filtra qué modelos se prueban (decide el MASE medido, no una regla fija).
  - ⚠️ **Esa selección es retrospectiva y el piso que produce es optimista** — el ganador de cada serie se elige con el MASE de todos los cortes y se aplica también a los más viejos. **Resuelto el 2026-08-05 en M1.9 / ADR-016:** el piso pasa a construirse con **selección prospectiva** (el ganador se reelige en cada corte usando solo el error ya observado, `anio_mes <= corte`) más **cascada por disponibilidad** (si el elegido no cubre una celda, se baja al siguiente de su ranking). La tabla retrospectiva queda como registro histórico. Números y descomposición en `roadmap-motor.md` §5.6.2.
- **Entregable:** tabla WAPE/MASE/sesgo por nivel (total/categoría/producto) y horizonte (1/3/6/12). **Este es el piso a batir; se congela como referencia** — y declara en su encabezado con qué criterio de selección se armó, porque los dos producen números distintos y una tabla que no lo dice no se puede comparar contra otra.

### M2 — Deflación + modelo global ML
- Implementar ancla + índices de nivel + fallback + clamp (ADR-002) como transformador reutilizable, con el cuidado de leakage descrito abajo.
- `mlforecast` + LightGBM global: lags (1,2,3,6,12), rolling means (3,6,12), mes del año, categoría/laboratorio, escala de precio (ancla) y **precio relativo a su nivel** con su variación (3m/12m).
  - ⚠️ **Tres correcciones a esta lista, medidas en M2.2 (2026-08-04) — ver `roadmap-motor.md` §6.3 y ADR-013.** (a) *"Precio real deflactado y su variación"* a grano producto **es una constante y una columna de ceros**: `precio_prom × d = ancla` por construcción (99,15% de las filas reales, CV 0,0000). La señal está en el precio contra el índice de su nivel, y por eso la lista dice eso ahora. Lo mismo con los montos: `revenue_real = unidades × ancla`, o sea el target reescalado. (b) `mismo_mes_año_anterior` se sacó porque a grano mensual **es** `lag 12`, que ya está en la lista. (c) **`CLIENTE_FEATURE` se difiere a M3.2**: el extract real no tiene cliente×producto, así que en M2 solo se podría ejercitar en sintético y M2.5 compararía una corrida real con una feature menos que la sintética.
- Quantile regression (P10/P50/P90) para intervalos.
  - ✅ **M2.4, 2026-08-06** — `predecir_global(cuantiles=...)` + `motor.backtesting.intervalos`; tabla en `backtests/intervalos-global-real-2026-08-06.md`. El P10–P90 **calibra sin recalibrar**: cobertura empírica 0,7798 / 0,8199 / 0,8130 / 0,8085 contra el 0,80 nominal. **Con una salvedad que el promedio esconde:** `suave` calibra perfecto pero `erratica` **sub-cubre ~12 puntos** en los cuatro horizontes, e `intermitente`/`lumpy` sobre-cubren con intervalos de hasta 13x la magnitud del real. Como ADR-015 punto 2 convierte esta cobertura en el compromiso del producto para h=6/h=12, esa dispersión es decisión del PM/Analista y no del motor — ver `roadmap-motor.md` §6.6.
- **Criterio de promoción:** el global ML reemplaza al baseline **solo en las series/niveles donde le gana en backtest** (champion/challenger por serie), **contra el piso prospectivo de M1.9** (`baselines-real-prospectivo-2026-08-05.md`) y no contra el retrospectivo. Y el champion/challenger se elige **con la misma regla** —por corte, con lo ya observado, y cascada por disponibilidad—: si el global recibiera trato retrospectivo la cancha quedaría inclinada a su favor, que es el mismo problema al revés (ADR-016 punto 4).
  - ✅ **M2.5, 2026-08-06 — aplicado y medido; ADR-017.** Lo promocionable es el **champion** (9 candidatos: 7 baselines + `GlobalLGBM` + `GlobalLGBM_P50`), **no el global solo**, y no es un tecnicismo: el global aplicado a todas las series **no cumple el gate de M2** —a h=12 y grano producto da 0,3746 contra 0,3699 del piso— y en `intermitente`/`lumpy` es **2 a 3 veces peor que el baseline**, con sobre-pronóstico que crece con el horizonte (sesgo +5,11 en `lumpy` a h=12). El WAPE agregado no lo mostraba porque esos dos cuadrantes son el **31% de los productos y el 0,6% del peso**. El champion gana los cuatro horizontes (0,3230 / 0,3667 / 0,3928 / 0,3644) y los baselines se quedan con el **84%** de los pares (serie, corte). Ver `roadmap-motor.md` §6.7.

### M3 — Jerarquía, cliente y segmentos
- Reconciliación total→categoría→laboratorio→producto (`hierarchicalforecast`, MinT/bottom-up según backtest).
- Nivel cliente: modelo de propensión P(compra en h) por cliente×producto (clasificación binaria LightGBM, mismas features) + tamaño esperado condicional. Alimenta venta cruzada y redistribución.
- Clustering RFM propio (sobre montos **deflactados**, CP-INF-04) versionado por corrida; contraste contra la segmentación operacional DFV (CP-SEG-01).
- Clientes nuevos (< 6 meses): prior del segmento operacional más cercano.
- **Entregable:** suite completa de predicciones coherentes + propensiones, con métricas por nivel.

#### El segmento es salida, no entrada

Pregunta recurrente: *si segmentamos clientes, ¿la salida no debería ser el segmento **más** su predicción?* Sí — y lo es. **La predicción por segmento se entrega**, los CU la prometen y `viabilidad.md` §3.2 la da por alcanzable. Lo que ADR-005 fija no es *si* se entrega, sino **cuándo entra el segmento al pipeline**:

```
(A) Segmento como ENTRADA — descartada
    clusterizar clientes → cluster_id entra al modelo (o un modelo por cluster)
                        → el modelo predice la demanda del cluster

(B) Segmento como SALIDA — la decidida
    modelo global predice al grano fino (producto; cliente×producto = propensión)
                        → se agrega / filtra por cluster para presentar
                        → "demanda del segmento 3" = suma de sus miembros
```

Las dos muestran lo mismo en pantalla; en (B) el número del segmento **se deriva** de predicciones más finas. Los tres motivos —IDs de cluster inestables entre corridas, no fragmentar el modelo global, y que el segmento es un eje **ortogonal** al árbol de reconciliación de M3.1— están desarrollados en la aclaración del **ADR-005** (2026-08-06), que es la fuente para citar si alguien lo pregunta.

Consecuencia práctica para M3.1: el árbol a reconciliar es **total → categoría → laboratorio → producto** y el segmento **no es un nivel de ese árbol**. Meterlo obligaría a reconciliar un cubo (dos jerarquías cruzadas) en vez de un árbol; agregando desde abajo, los totales por segmento cierran por construcción.

#### Etiquetado del segmento: estable entre corridas, no encadenado

El `cluster_id` de cada corrida es arbitrario por diseño (ADR-005) — no se puede mostrar tal cual a un operador que espera ver siempre los mismos nombres. La solución **no es** comparar cada corrida contra la anterior (esa cadena deriva sin que nadie lo decida y depende de guardar historial). Es fijar **arquetipos de referencia** en el espacio R/F/M **una sola vez** — calibrados, si es posible, con los mismos cortes P33/P67 que ya usa la segmentación operacional de DFV, para favorecer coherencia con CP-SEG-01 — y en cada corrida etiquetar cada centroide con el arquetipo más cercano. El administrador cura los arquetipos (coherente con CU-04); no retagea clusters cada mes. Detalle, casos borde y gate en `roadmap-motor.md` §7, bloque "Diseño pendiente de M3.3".

#### Composición diagnóstica por cluster, no predicción cruzada (todavía)

Cada cluster debe poder mostrar qué categorías/productos/laboratorios están presentes entre sus miembros — `groupby(segmento) → top categoría/producto/laboratorio` sobre la fila cliente×producto de M3.2, que ya trae segmento y catálogo. Es descriptivo, sale de la arquitectura (B) sin modelo nuevo, y cubre lo que CU-04/CU-05 ya piden. **No** se compromete todavía una predicción reconciliada por segmento×categoría: M3.1 reconcilia el árbol sobre series agregadas sin cliente, M3.2 predice cliente×producto con otro modelo, y no está garantizado que las dos sumen igual — abierto, no bloquea M3.3.

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
4. Sesgo global dentro de ±5% a nivel total **en h=1 y h=3**. En **h=6 y h=12** el compromiso es la **cobertura empírica del intervalo P10–P90** más el sesgo publicado con su signo y comparado contra el del piso — **ADR-015** (2026-08-05), que invoca el Riesgo 5 del Acta. El piso real sub-pronostica −5,2% (h=6) y −6,0% (h=12); el gate sigue exigiendo que el global lo **corrija**, lo que se acota es la promesa del producto, no la vara del modelo.
5. Predicciones con intervalos escritas en `PREDICCION_DEMANDA` vía `EJECUCION_MODELO`, consultables < 2s.
6. Segmentos RFM no contradicen el oráculo DFV (CP-SEG-01) y los casos CP-INF-01..05 pasan.

## Fuera de alcance del motor (MVP)

Deep learning (LSTM/transformers), pronóstico intra-mensual, optimización de precios, demanda censurada por quiebres, clima como driver de precisión (queda como feature explicativa/mock — viabilidad §3.4, formalizado en **ADR-014**: el dato del MVP es mock por contrato §6 y el clima futuro no se conoce a 6–12 meses; la estacionalidad de calendario capta la parte predecible).
