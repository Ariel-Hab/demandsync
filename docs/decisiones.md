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

**Actualización 2026-07-15 (EDA):** el esquema real no tiene FK remito→factura; el propio ERP computa estadística como unión de ambas fuentes filtrando `estadistica ∈ {P,N}` (es decir, la dedup parece resuelta aguas arriba), y el share de remitos es hoy ~5-15% del revenue.

**Actualización 2026-07-15 (frontera de responsabilidad — reemplaza el mecanismo):** el cliente entrega un feed de **ventas unificadas** ya deduplicado; la unión factura/remito, los criterios estadísticos del ERP y la dedup son responsabilidad del **exportador del lado cliente** (P1 del contrato). Consecuencias: (a) DemandSync no re-deduplica — valida garantías y rechaza el archivo si fallan; (b) `VENTA.tipo_comprobante` deja de ser necesario en el DER de DemandSync (la parte de C6 sobre ese atributo queda sin efecto; la parte de "regla de deduplicación" pasa a ser una **garantía de origen** del contrato); (c) CP-DEDUP-01 se reformula: testea que la ingesta detecte/rechace un feed que viole la garantía, con datos sintéticos.

**Docs impactados:** `contrato-ingesta.md` (§1 y P1 — hecho 2026-07-15), DER UTN (retirar `tipo_comprobante` de VENTA o marcarlo opcional-informativo; anotar la garantía de origen), Plan de Pruebas (CP-DEDUP-01 reformulado como validación de garantía).

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
**Estado:** Aceptada (2026-07-25) — ratificada por el ML Specialist por autoridad técnica sobre el diseño del motor; equipo informado, sin objeciones pendientes de registrar.

**Contexto:** predecir montos en pesos argentinos arrastra el riesgo inflacionario completo (riesgo R6); predecir unidades lo elimina del target. El abastecimiento (Q sugerida, cobertura de lotes) necesita **unidades**, no pesos.

**Decisión:** el motor predice **unidades** por producto (y por segmento) como target primario. El valor monetario se deriva multiplicando por el precio actual/ancla cuando la UI o el negocio lo pidan. Los montos deflactados (ADR-002) se usan como **features** (valor real del cliente, RFM monetario), no como target del MVP.

**Consecuencias:** desacopla la calidad del modelo de la inflación; alinea con la contingencia R6 del plan de pruebas; RFM sigue necesitando deflación (CP-INF-04).

**Docs impactados:** Casos de Uso UTN (CU-03: la proyección primaria pasa a unidades), DER UTN (`PREDICCION_DEMANDA.cantidad_estimada` queda en unidades; valor monetario derivado), Plan de Pruebas (casos de predicción de valor).

---

## ADR-008 — Métricas de error: WAPE + MASE + sesgo como métricas internas; MAPE solo comunicacional
**Estado:** Aceptada (2026-07-25) — ratificada por el ML Specialist por autoridad técnica sobre la evaluación del motor; impacta DER y plan de pruebas, equipo informado.

**Contexto:** los docs UTN (CU-03, DER `PREDICCION_DEMANDA.mape`, `EJECUCION_MODELO.mape`) fijan MAPE como métrica. MAPE es indefinida con demanda cero (frecuente a nivel producto-segmento-mes), asimétrica (castiga sobre-forecast sin tope y premia forecast bajo) y no ponderada por volumen. La industria opera con WAPE/WMAPE + sesgo; la comparación entre series de distinta escala usa MASE/RMSSE (estándar de la competencia M5).

**Decisión:** internamente el motor se evalúa con **WAPE** (por nivel de agregación), **MASE** (comparación cross-serie contra naive estacional) y **sesgo** (over/under sistemático). MAPE se conserva como indicador comunicacional en la UI **solo en niveles agregados** donde no hay ceros. El campo `mape` del DER pasa a un genérico `metrica_error` + `tipo_metrica`, o se acompaña de `wape`.

**Consecuencias:** cambia levemente DER y casos de prueba; evita reportar errores infinitos/engañosos en productos intermitentes.

**Docs impactados:** DER UTN (`PREDICCION_DEMANDA.mape` y `EJECUCION_MODELO.mape` → `metrica_error` + `tipo_metrica` o columna `wape` adicional), Casos de Uso UTN (CU-03: badge de confianza), Plan de Pruebas (criterios de aceptación del Release 2).

---

## ADR-009 — Frontera de datos del motor: repositorio abstracto; el motor no depende de PostgreSQL para desarrollarse
**Estado:** Propuesta (2026-07-25) — **a ratificar con el Backend Dev**, es frontera motor↔backend

**Contexto:** el motor consume hechos mensuales que produce el ETL del Release 1, y R1 está bloqueado por el congelamiento del contrato de ingesta (P1–P4). Si el motor espera esa cadena, el track del ML Specialist queda serializado detrás de dos dependencias externas y —peor— el **arnés de backtesting, que es el activo más importante del motor, se escribiría último**. La disciplina baselines-first exige exactamente lo contrario: arnés y piso de baselines primero.

**Decisión propuesta:** el motor accede a datos únicamente a través de una **interfaz de repositorio** (`RepositorioHechos` para lectura, `RepositorioResultados` para escritura), con dos implementaciones intercambiables:

1. **Archivos locales** (parquet) conformes al DER, alimentados por el generador sintético o por un extract propio del snap en la máquina autorizada. Habilita M1–M3 sin base.
2. **PostgreSQL/SQLModel**, incorporada en M4 cuando R1 exista.

Ambas comparten un **diccionario de columnas único, espejo del DER corregido** (C1 hechos mensuales, C2 entidades de deflación, C3 `CLIENTE_FEATURE`), con un test de conformidad de esquema. El diccionario del motor no es una definición paralela: si el DER cambia un nombre o un tipo, el test rompe y eso es el comportamiento deseado.

Además, el generador sintético emite **dos salidas**: renglones de venta en el esquema del contrato de ingesta (lo que necesita el ETL del backend para probarse) y los hechos mensuales agregados desde su propia verdad de base (lo que consume el motor). Como la segunda se deriva de la primera por una agregación conocida, **el ETL de R1 debe reproducirla** — queda como test de integración de la ingesta.

**Consecuencias:** M1–M3 arrancan sin esperar contrato v1.0 ni ETL; la única dependencia dura de R1 pasa a ser el swap de implementación (M4.2), que es un cambio localizado. Costo: hay que mantener el diccionario sincronizado con el DER y sostener dos implementaciones del repositorio. Riesgo: si el backend renombra columnas sin avisar, la divergencia aparece recién en M4 — se mitiga acordando que el diccionario del motor es espejo del DER y todo rename es cambio de contrato. Si el Backend Dev rechaza esta frontera, el rediseño de la capa de datos hay que hacerlo **antes de M4**, no antes de M1.

**Docs impactados:** `docs/arquitectura.md` (§Flujo de datos y §Entorno de desarrollo: el motor puede correr sin base; el desacoplamiento del principio 1 se materializa con el repositorio), `motor/plan-diseno.md` (M4 incluye explícitamente el swap de implementación), `motor/roadmap-motor.md` (§3 y §10 ya lo asumen), `datasets/README.md` (el generador emite dos salidas, no solo el esquema de ingesta), `planning/roadmap.md` (R2 deja de depender de R1 salvo para la integración batch).
