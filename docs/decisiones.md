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

---

## ADR-010 — Demanda cero explícita: el motor mide sobre un calendario denso, desde la primera venta de cada producto
**Estado:** Aceptada (2026-07-27) — ratificada por el ML Specialist por autoridad técnica sobre la medición del motor (mismo criterio que ADR-007/008). No altera hechos persistidos ni el contrato de ingesta: es una regla de preparación **read-time**, como la deflación de ADR-002.

**Contexto:** `HECHO_VENTA_MENSUAL_PRODUCTO` es **disperso**: un producto-mes sin venta no tiene fila (verificado sobre el dataset sintético: 160.664 filas de 220.800 celdas posibles, densidad 72,8%, cero filas con `unidades = 0`). Eso es correcto para una tabla de hechos —no se persisten no-eventos— pero el consumo analítico necesita la serie completa: un pronóstico se evalúa mes a mes, exista o no la fila.

El relevamiento del 2026-07-27 (`motor/roadmap-motor.md` §5.1) encontró que el arnés de backtesting trataba la tabla como si fuera un panel denso, con tres consecuencias medidas: (1) el 30,6% de los pares producto-mes nunca se medía, y el WAPE real a h=1 era 0,80 contra 0,53 reportado; (2) la escala de MASE, que `utilsforecast` calcula con un desplazamiento de 12 **filas**, dejaba de equivaler a 12 meses — el 68,8% de las series con el denominador mal, hasta 9,6x; (3) los "cortes mensuales" del backtest no eran consecutivos al operar por serie. Sin ceros explícitos, **sobre-pronosticar donde la demanda fue cero es invisible**, que es justamente el error dominante en un portafolio con 42% de series intermitentes.

**Decisión:** el motor densifica el calendario antes de medir y antes de modelar. La regla:

1. **Grano:** un registro por `(serie, mes)` para todos los meses del calendario, sin huecos.
2. **Desde:** el **primer mes con venta de cada serie**, no el inicio del dataset. Un producto que entró al catálogo en 2023 no tuvo demanda cero en 2019: no existía, y rellenarlo inventaría años de ceros falsos que sesgarían la intermitencia medida.
3. **Hasta:** el **último mes del período de datos**, aunque la serie haya dejado de vender. Los ceros de cola se miden: si el modelo predice 10 unidades de un producto discontinuado, ese error tiene que verse. Cortar en la última venta lo esconde — y detectar obsolescencia es exactamente para lo que existe TSB (M1.6).
4. **Qué se rellena con cero:** solo las columnas de **cantidad** (`unidades`, `revenue`). **`precio_prom` queda nulo, nunca cero**: en un mes sin venta no hay precio observado, y un cero contaminaría el índice implícito de la deflación (ADR-002).
5. La densificación es **read-time y no se persiste** (coherente con ADR-001: los hechos mensuales siguen siendo inmutables, nominales y dispersos).

**Consecuencias:**
- Las métricas de ADR-008 pasan a medir sobre la población completa. Los números previos al 2026-07-27 no son comparables con los posteriores: **el piso de baselines se congela recién con esta regla vigente** (gate de M1).
- Habilita la rama intermitente de M1.6 (`CrostonSBA`, `TSB`): esos métodos aciertan prediciendo bajo en los meses de cero, y sin ceros medidos perderían sistemáticamente contra un naive que sobre-pronostica. Con la tabla dispersa se habría elegido el método equivocado para ~42% del catálogo.
- Aplica igual a `P(compra)` de M3.2 (cliente×producto): ahí los ceros **son** la señal que el modelo predice. Advertencia de escala: densificar 319k pares × 96 meses son ~30M de filas; se densifica por ventana de evaluación, no el histórico completo.
- Hace **operativo** el supuesto de demanda censurada ya documentado en `motor/viabilidad.md` §3.5: al no haber histórico de stock, un cero puede ser "nadie lo pidió" o "no había stock", y el motor los trata igual. La densificación no crea esa limitación —ya existía— pero la vuelve explícita en cada fila. Si algún día el cliente expone quiebres, la regla se revisa con un ADR nuevo.
- Costo: el panel denso es ~1,4x la tabla dispersa a nivel producto. Irrelevante a esta escala.

**Alternativas descartadas:** (a) densificar desde el inicio del dataset — inventa ceros de productos que no existían y corrompe la clasificación de intermitencia; (b) densificar solo entre primera y última venta — esconde la obsolescencia, que es un caso de negocio real; (c) dejar que cada modelo densifique por su cuenta — reintroduce el defecto en cada componente nuevo y hace incomparables las métricas entre modelos.

**Docs impactados:** `motor/plan-diseno.md` (§Protocolo de backtesting: agregar la densificación como paso previo obligatorio), `motor/roadmap-motor.md` (§5.1 M1.0 ya la asume como entregable (a)), `motor/src/motor/backtesting/README.md` (regla de calendario), Plan de Pruebas UTN (el supuesto de demanda censurada pasa de nota a criterio explícito; coordinar con el Analista Funcional — registrado en `planning/roadmap.md`).
