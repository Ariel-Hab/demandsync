# Corrección del Plan de Pruebas / Casos de Prueba — DemandSync

**Fecha:** 2026-07-05
**Autor:** Equipo DFV (validación desde el sistema fuente)
**Documento corregido:** *Plan de Pruebas de DemandSync v1.0* (10 CU, 36 casos, 4 Releases)
**Base de la corrección:** validación contra la realidad de los datos que alimentan a DemandSync (ver documento hermano `02_correccion_der_demandsync.md`).

---

## 0. Alcance de esta corrección

El plan está **bien estructurado**: 4 Releases incrementales, 10 CU, severidades bien graduadas, matriz de riesgos coherente. Las correcciones son de **cobertura**: faltan pruebas sobre dimensiones que solo se ven conociendo los datos reales (inflación, deduplicación factura/remito, disponibilidad de stock, deflación que preserva descuentos).

> **Nota:** trabajo sobre el plan (estrategia + alcance + riesgos). Los **36 casos individuales** están en `Casos_de_Prueba_DemandSync.xlsm`, que no tengo. Para corregirlos renglón por renglón, pasame ese archivo. Acá van las correcciones al plan y los **casos nuevos a diseñar**.

---

## 1. Correcciones a la estrategia y el alcance

### T1 — Falta la prueba de normalización por inflación (crítico)

No hay **ningún** caso que valide llevar los montos históricos a precio de hoy. En 8 años de historia en pesos es imprescindible: sin deflactar, el RFM-monetario y cualquier predicción de valor quedan dominados por la inflación (los años recientes aplastan a los viejos). Agregar casos (ver T7, casos CP-INF-*).

### T2 — Prueba de volumen: precisar la mitigación real

R3 (`<2s` sobre 5-10 años) está bien identificado, pero **no se mitiga solo con índices**: la mitigación estructural es la **capa de hechos mensuales materializados** (corrección DER C1). El caso de volumen debe validar los tiempos **contra la vista mensual agregada**, no contra el grano crudo de 8 años de renglones.

### T3 — CU de inventario: separar dato real-actual de sintético-histórico

Confirmado con el cliente: el stock/lote/vencimiento **actual es real** (del snap); **no hay histórico de movimientos de stock**. Corrección al alcance:
- **CU-06 (vencimientos)** y **CU-07 (borrador de OC)**: diseñar los casos sobre **stock/lote actual real** — es mejor evidencia que datos sintéticos.
- Cualquier caso que asuma **serie histórica de stock / rotación pasada**: marcarlo **fuera de datos reales** → sintético y documentado como tal.
- La mitigación de R1 (dataset sintético) sigue valiendo para casos borde, pero **aclarar** que el inventario actual **no** es sintético.

### T4 — Segmentación: usar la segmentación determinística de DFV como oráculo

El criterio de aceptación del Release 2 ("los clientes se agrupan de forma lógica") es subjetivo. DFV ya tiene una **segmentación operacional determinística** (percentiles) que puede servir de **oráculo de sanidad**: agregar un caso que contraste los segmentos RFM+K-Means de DemandSync contra los operacionales de DFV — no deben ser contradictorios para clientes claramente de alto/bajo valor.

### T5 — Deduplicación factura/remito (riesgo de datos no cubierto)

La ingesta trae **facturas y remitos** del snap. Una misma venta puede contarse **dos veces** → distorsiona toda la serie temporal. No hay caso que lo valide. Agregar prueba de deduplicación en la ingesta (CU-02 / CU-08).

### T6 — Ajustes a severidades y criterios de detección

- **Deflación incorrecta = severidad Alta** (encuadra en "una predicción/recomendación se genera con datos incorrectos"). Hoy no está contemplada.
- **Doble conteo factura/remito = severidad Alta** (mismo encuadre).
- Criterios de detección: agregar el **período de los datos** usados como dato de entrada obligatorio a registrar (necesario para reproducir casos de inflación).

---

## 2. Riesgos a agregar a la matriz

| ID | Descripción | Mitigación | Contingencia |
|---|---|---|---|
| **R6** | La normalización por inflación no se implementa, o se usa IPC macro en lugar del índice implícito por producto → RFM y predicciones de valor distorsionadas y descuentos individuales borrados. | Adoptar el índice implícito por producto que preserva el descuento (spec en corrección DER C2). Validar con casos CP-INF-*. | Acotar el MVP a predicción de **unidades** (no montos), donde la inflación no incide; documentar la limitación. |
| **R7** | Doble conteo por ingesta de facturas + remitos sin deduplicar → serie temporal inflada. | Definir y testear la regla de deduplicación en la ingesta (CP-DEDUP-01). | Ingerir una sola fuente (factura) en el MVP y documentar la cobertura parcial. |
| **R8** | Ausencia de histórico de stock → los modelos de rotación/redistribución solo pueden basarse en el stock actual. | Diseñar CU-06/07 sobre stock actual; no asumir series de stock. | Documentar que la redistribución histórica queda fuera de alcance. |

---

## 3. Casos de prueba nuevos a diseñar

| Código | CU | Caso | Prioridad |
|---|---|---|---|
| CP-INF-01 | CU-03 | Dos ventas idénticas (mismas unidades, mismo producto) en 2019 y 2025 se normalizan a valores comparables en pesos de hoy. | Alta |
| CP-INF-02 | CU-04 | La deflación **preserva el descuento individual**: un cliente que pagó 20% por debajo del promedio en 2019 sigue 20% por debajo del promedio deflactado. | Alta |
| CP-INF-03 | CU-03 | Fallback de ancla: producto sin ventas recientes → se deflacta por índice de categoría/laboratorio → IPC. | Media |
| CP-INF-04 | CU-04 | El `valor_monetario` de RFM se calcula sobre montos **deflactados**, no nominales. | Alta |
| CP-INF-05 | CU-03 | Sanidad: un precio basura (`0.01`) clampeado no dispara el índice de toda la categoría. | Media |
| CP-DEDUP-01 | CU-02/08 | Una venta que existe como remito y como factura se cuenta **una sola vez** tras la deduplicación. | Alta |
| CP-VOL-01 | CU-03 | La consulta de predicción `<2s` se valida contra la **vista mensual agregada** con 8 años de datos. | Alta |
| CP-SEG-01 | CU-04 | Los segmentos RFM+K-Means no contradicen la segmentación operacional de DFV para clientes claros de alto/bajo valor (oráculo). | Media |
| CP-STK-01 | CU-06 | La alerta de vencimiento se calcula sobre **stock actual real** (lote del snap) + demanda predicha. | Alta |
| CP-STK-02 | CU-07 | El borrador de OC usa stock actual + demanda + `lead_time` configurado (no serie histórica de stock). | Media |

---

## 4. Resumen

| # | Corrección | Tipo | Prioridad |
|---|---|---|---|
| T1 | Agregar casos de normalización por inflación (CP-INF-*) | Cobertura faltante | 🔴 Alta |
| T2 | Volumen `<2s` contra vista mensual agregada | Precisión de la prueba | 🔴 Alta |
| T3 | Inventario: real-actual vs sintético-histórico | Ajuste de alcance | 🟠 Media |
| T4 | Segmentación DFV como oráculo (CP-SEG-01) | Cobertura faltante | 🟠 Media |
| T5 | Deduplicación factura/remito (CP-DEDUP-01) | Cobertura faltante | 🔴 Alta |
| T6 | Severidades (deflación/dedup = Alta) + período en criterios | Ajuste de criterios | 🟠 Media |
| R6/R7/R8 | Tres riesgos nuevos en la matriz | Gestión de riesgos | 🔴 Alta |

**Correcto y sin cambios:** estructura por Releases, pruebas de integración/regresión/concurrencia, gradación de severidades base, criterios de aceptación por Hito, ambiente de pruebas (PostgreSQL+pgvector / FastAPI), riesgos R1-R5.
