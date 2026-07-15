# Registro de Decisiones Arquitectónicas (ADR)

> Formato: contexto → decisión → consecuencias. Las decisiones "Aceptada — heredada DFV" fueron tomadas y validadas contra el sistema real del cliente 1 antes de crear este repo (docs en `referencias/`); son vinculantes salvo ADR posterior que las reemplace.

---

## ADR-001 — Hechos mensuales inmutables; la ingesta no deflacta
**Estado:** Aceptada — heredada DFV (2026-06-21)

**Contexto:** el entrenamiento necesita 8 años de historia en un contexto de alta inflación; "hoy" se mueve, por lo que los valores deflactados no son hechos estables.

**Decisión:** la ingesta materializa solo hechos **nominales** mensuales, append-only, nunca mutan: `(producto, año_mes) → unidades, revenue, precio_prom` (promedio **ponderado por cantidad** = `revenue/unidades`) y `(cliente, producto, año_mes) → unidades, revenue`. Toda conversión a "precio de hoy" es un paso de lectura.

**Consecuencias:** se puede recalcular la estadística a cualquier "hoy" sin re-ingestar; la prueba de volumen `<2s` corre contra estas tablas; el DER incorpora `HECHO_VENTA_MENSUAL_PRODUCTO` y `HECHO_VENTA_MENSUAL_CLIENTE_PRODUCTO` (corrección C1).

---

## ADR-002 — Deflación read-time con índice implícito por producto (preserva descuentos)
**Estado:** Aceptada — heredada DFV (2026-06-21, confirmada 2026-07-05)

**Contexto:** no existe precio de lista histórico en el cliente. Deflactar con IPC macro borra el descuento individual de cada cliente, que es justo la señal que el modelo necesita.

**Decisión:** deflactar el monto de cada cliente por el ratio del promedio del producto:
```
monto_real = revenue_cliente,t × (precio_prom_producto_hoy / precio_prom_producto,t)
```
- El promedio del producto es el **índice/ancla**, no el valor a deflactar → el término `precio_cliente,t / precio_prom,t` (descuento individual) sobrevive.
- **Prohibido** re-tasar como `unidades × precio_prom_hoy`: cancela el descuento.
- `precio_prom_hoy` = ventana estable reciente (1–3 meses) de la misma serie implícita; nunca precio de lista.
- Fallback de ancla: `producto → categoría → laboratorio → IPC INDEC` (media geométrica ponderada de relativos; clamp de ratios contra precios basura).

**Consecuencias:** entidades `ANCLA_PRECIO_PRODUCTO` e `INDICE_PRECIO_NIVEL` en el DER (corrección C2); el IPC macro queda como red de seguridad final, no como deflactor primario; casos de prueba CP-INF-01..05.

---

## ADR-003 — Deduplicación factura/remito en la ingesta
**Estado:** Aceptada — heredada DFV (2026-07-05)

**Contexto:** el ERP registra ventas como remito y luego factura; ingerir ambos duplica ventas y distorsiona toda la serie.

**Decisión:** `VENTA.tipo_comprobante` obligatorio + regla de deduplicación en la ingesta. Caso de prueba CP-DEDUP-01. Contingencia MVP: ingerir solo facturas y documentar cobertura parcial.

**Actualización 2026-07-15 (EDA):** el esquema real no tiene FK remito→factura; el propio ERP computa estadística como unión de ambas fuentes filtrando `estadistica ∈ {P,N}` (es decir, la dedup parece resuelta aguas arriba), y el share de remitos es hoy ~5-15% del revenue. La regla concreta queda **pendiente P1 del contrato de ingesta**: confirmar la semántica de `estadistica` con el dueño del ERP antes de congelar v1.0. La corrección C6 del DER (`tipo_comprobante`) sigue vigente igual.

**Docs impactados:** `contrato-ingesta.md` (P1), Plan de Pruebas (CP-DEDUP-01: el caso debe testear la regla que se confirme, no asumir "factura anula remito").

---

## ADR-004 — Stock: foto actual real; serie histórica fuera de alcance
**Estado:** Aceptada — heredada DFV (2026-07-05)

**Contexto:** el snap expone stock y lotes vigentes, pero no movimientos históricos de stock.

**Decisión:** alertas de vencimiento y redistribución operan sobre **stock actual + demanda predicha**. Ningún modelo asume series de stock ni rotación pasada. Limitación documentada: las ventas aproximan la demanda (demanda censurada por quiebres no observables).

---

## ADR-005 — Dos segmentaciones, roles distintos; cluster_id nunca es feature
**Estado:** Aceptada — heredada DFV (2026-07-05)

**Contexto:** el cliente ya tiene una segmentación operacional determinística (percentiles, reglas); DemandSync agrega RFM+K-Means propio. Los IDs de cluster cambian de significado entre corridas.

**Decisión:** la segmentación operacional de DFV entra como **feature** (`CLIENTE_FEATURE`); la de DemandSync es agrupamiento ML versionado por `EJECUCION_MODELO` y sirve como dimensión de **salida** (scoping de predicciones), jamás como feature de entrenamiento entre corridas. La segmentación DFV actúa además de **oráculo de sanidad** en las pruebas (CP-SEG-01). Para reproducibilidad se prefiere Ward jerárquico; si se usa K-Means: semilla fija + versionado.

---

## ADR-006 — Repositorio independiente del ecosistema DFV; datos reales nunca en el repo
**Estado:** Aceptada (2026-07-15)

**Contexto:** DemandSync se desarrolla con acceso a los datos reales de DFV (ventaja para validar), pero el repo se comparte con un equipo externo a la empresa.

**Decisión:** repo propio fuera del árbol del ecosistema DFV. Los extracts reales viven solo en la máquina autorizada; al repo entran únicamente datos sintéticos/anonimizados (`datasets/`), métricas agregadas y conclusiones. Prohibido commitear credenciales, URLs internas o datos de clientes.

**Consecuencias:** el equipo desarrolla contra datos sintéticos que replican esquema y propiedades estadísticas; la validación con datos reales la corre quien tiene acceso y publica resultados agregados.

---

## ADR-007 — Variable objetivo primaria: unidades; revenue derivado
**Estado:** Propuesta (2026-07-15) — a ratificar por el equipo

**Contexto:** predecir montos en pesos argentinos arrastra el riesgo inflacionario completo (riesgo R6); predecir unidades lo elimina del target. El abastecimiento (Q sugerida, cobertura de lotes) necesita **unidades**, no pesos.

**Decisión propuesta:** el motor predice **unidades** por producto (y por segmento) como target primario. El valor monetario se deriva multiplicando por el precio actual/ancla cuando la UI o el negocio lo pidan. Los montos deflactados (ADR-002) se usan como **features** (valor real del cliente, RFM monetario), no como target del MVP.

**Consecuencias:** desacopla la calidad del modelo de la inflación; alinea con la contingencia R6 del plan de pruebas; RFM sigue necesitando deflación (CP-INF-04).

**Docs impactados:** Casos de Uso UTN (CU-03: la proyección primaria pasa a unidades), DER UTN (`PREDICCION_DEMANDA.cantidad_estimada` queda en unidades; valor monetario derivado), Plan de Pruebas (casos de predicción de valor).

---

## ADR-008 — Métricas de error: WAPE + MASE + sesgo como métricas internas; MAPE solo comunicacional
**Estado:** Propuesta (2026-07-15) — a ratificar por el equipo; impacta DER y plan de pruebas

**Contexto:** los docs UTN (CU-03, DER `PREDICCION_DEMANDA.mape`, `EJECUCION_MODELO.mape`) fijan MAPE como métrica. MAPE es indefinida con demanda cero (frecuente a nivel producto-segmento-mes), asimétrica (castiga sobre-forecast sin tope y premia forecast bajo) y no ponderada por volumen. La industria opera con WAPE/WMAPE + sesgo; la comparación entre series de distinta escala usa MASE/RMSSE (estándar de la competencia M5).

**Decisión propuesta:** internamente el motor se evalúa con **WAPE** (por nivel de agregación), **MASE** (comparación cross-serie contra naive estacional) y **sesgo** (over/under sistemático). MAPE se conserva como indicador comunicacional en la UI **solo en niveles agregados** donde no hay ceros. El campo `mape` del DER pasa a un genérico `metrica_error` + `tipo_metrica`, o se acompaña de `wape`.

**Consecuencias:** cambia levemente DER y casos de prueba; evita reportar errores infinitos/engañosos en productos intermitentes.

**Docs impactados:** DER UTN (`PREDICCION_DEMANDA.mape` y `EJECUCION_MODELO.mape` → `metrica_error` + `tipo_metrica` o columna `wape` adicional), Casos de Uso UTN (CU-03: badge de confianza), Plan de Pruebas (criterios de aceptación del Release 2).
