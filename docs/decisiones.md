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

---

## ADR-011 — El IPC del INDEC viaja dentro del paquete del motor, con fecha de vencimiento
**Estado:** Propuesta (2026-07-31) — a ratificar con el Backend Dev (afecta el empaquetado del job batch) y el Analista Funcional (es un insumo nuevo en el flujo de datos).

**Contexto:** la cascada de deflación de ADR-002 es `producto → categoría → laboratorio → IPC`. Los tres primeros peldaños salen de las ventas del propio cliente; el cuarto no sale de ningún lado. Al implementar M2.1 apareció que **ese peldaño no tenía insumo**: la decisión estaba tomada desde 2026-06-21 pero la serie no existía en ninguna parte del repo, así que la cascada no tenía fondo y un producto sin categoría ni laboratorio medibles devolvía `NaN` propagado.

Medido sobre el extract real: el IPC atiende **12 productos de 2.189 (0,5%)** al resolver el ancla. Es poco, pero un camino de código que no existe no se puede testear, y CP-INF-03 lo exige.

**Decisión:** la serie `148.3_INIVELNAL_DICI_M_26` de `apis.datos.gob.ar` (IPC Nivel General Nacional, base dic-2016, publicada por la Subsecretaría de Programación Macroeconómica sobre el IPC del INDEC, licencia CC-BY 4.0) se commitea en `motor/src/motor/datos/ipc_indec.csv` y se lee con `motor.datos.ipc.cargar_ipc()`.

1. **Viaja dentro del paquete** (`[tool.setuptools.package-data]`), no como archivo de configuración externo: si la rueda se construye sin él, la cascada se queda sin fondo en producción y el fallo aparece recién en el 0,5% de los casos.
2. **Es inyectable**: `TransformadorDeflacion(ipc=...)` acepta otra serie. El CSV es el default, no un acoplamiento.
3. **No lo alcanza ADR-006.** La regla prohíbe datos **del cliente**; esto es dato público del Estado y no dice nada de DFV. Es la única excepción a "en el repo no entran datos", y es una excepción aparente, no real.
4. **Se vence, y falla fuerte.** Un corte posterior al último mes del CSV levanta `IpcDesactualizado`. Devolver el último dato disponible subestimaría la inflación **en silencio** y achicaría los montos deflactados de todo el tramo faltante — el tipo de error que no se encuentra nunca. Actualizarlo es re-correr un `curl` documentado en el docstring del módulo.
5. **La base (dic-2016 = 100) se conserva tal como la publica la fuente.** Es arbitraria y se cancela —la deflación solo usa cocientes entre dos meses— y renormalizarla a algo más cómodo perdería la trazabilidad contra el original.

**Consecuencias:** el motor pasa a tener **un insumo externo**, cuando hasta ahora todo salía de las tablas del cliente; hay que decirlo en `arquitectura.md`. El empaquetado del job batch tiene que incluir datos de paquete, no solo código. Aparece una **tarea de mantenimiento recurrente** que hoy no tiene dueño: el CSV va quedando viejo y el motor deja de poder deflactar cortes nuevos. Mientras el batch corra sobre historia cerrada no molesta; cuando R4 lo ponga a correr sobre el mes en curso, hay que resolver si se actualiza a mano o si el ETL de R1 trae la serie como una `VARIABLE_EXTERNA` más — que probablemente sea lo correcto a largo plazo y convertiría a este ADR en transitorio.

**Alternativas descartadas:** (a) **dejar el peldaño sin insumo y devolver `NaN`** — deja 12 productos sin deflactar y, peor, una rama de la cascada que nunca se ejecuta y por lo tanto nunca se prueba; (b) **pedirlo por API en cada corrida** — mete una dependencia de red en un job batch que hoy no la tiene y hace no reproducible un backtest; (c) **usar un nivel "global" (todos los productos) en vez del IPC** — mediría precios veterinarios y sería *mejor* estimador que la inflación macro, pero cambia la cascada que fija ADR-002; si alguna vez el peldaño IPC pasa a ser relevante, esto amerita su propio ADR y no un cambio silencioso.

**Docs impactados:** `docs/arquitectura.md` (§Flujo de datos: el motor tiene un insumo externo; §Entorno: el empaquetado incluye package-data), `motor/README.md` (§Interfaces — hecho), `motor/src/motor/deflacion/README.md` (hecho), `motor/roadmap-motor.md` §6.1 (hecho), Acta/DER si se decide que el IPC pase a ser `VARIABLE_EXTERNA` en R1 — registrado como pendiente del Analista Funcional en `planning/roadmap.md`.

---

## ADR-012 — El obsequio se identifica por el precio del renglón, no por el flag del producto; `disabled` es estado actual y no se aplica hacia atrás
**Estado:** **Aceptada (2026-08-02)** por el ML Specialist. Es regla de universo del extract del motor —qué renglón es una venta y qué producto entra al backtest— y no cambia hechos persistidos ni obliga a nadie más. El impacto sobre el contrato de ingesta y los documentos UTN queda como **pendiente informativo** del Analista Funcional en `planning/roadmap.md`, no como condición para aplicarla.

**Contexto:** al resolver la decisión abierta de M2.1 (deflactores absurdos por precios propios ínfimos) apareció que la causa no era del transformador de deflación sino del **universo**: el extract de M1.8a nunca excluyó obsequios ni productos descontinuados, porque el EDA no los había relevado. Medido sobre el snap el 2026-08-02:

- **Obsequios.** El ERP exige `precio > 0`, así que un obsequio se factura con un centinela de **$0,01**. Son **3.638 renglones / 4.067 unidades** desde 2018-07. Los facturados en `0` —200.334 renglones, 767.882 unidades— ya salían por el filtro `precio > 0` que el extract heredó de cotizaciones; el centinela se colaba.
- **El flag `producto.obsequio` existe** (`bit(1)`, 682 en el catálogo, 48 en el universo) **pero no sirve como filtro**: los 48 cargan **0,92% del revenue** y 12 de ellos venden a precio real (máximo, mediana $4.717). Y al revés: 22 productos que facturan siempre a $0,01 **no** están marcados.
- **Descontinuados.** La convención de prefijar con "." vive en `producto.descripcion` (460 en el catálogo, 73 en el universo), **no** en `producto.id` — el `REGEXP '^[0-9]+$'` del extract no los tocaba. Los 73 son **subconjunto exacto** de los 313 `disabled`.
- **`disabled` no tiene fecha**: `fecha_ultima_modificacion` es NULL en 7.398 de 7.947 y es un timestamp genérico. Y no significa "dejó de venderse": 116 de los 313 del universo vendieron en 2026.

**Decisión:**

1. **El obsequio se corta a nivel renglón, por precio**, con `UMBRAL_PRECIO_OBSEQUIO = 0,05` en `motor/scripts/extraer_snap.py`. No se corta por producto: eso borraría 0,92% de revenue real.
2. **El umbral absoluto es válido acá, y solo acá.** En una economía con ×79 de inflación en la ventana un piso en pesos normalmente no significa nada, pero **$0,01 no es un precio, es un centinela**: el tramo va de 0,01 a 0,05 en *todos* los años sin deriva inflacionaria, y entre $0,05 y $5 quedan 5 a 90 renglones por año en 1 a 9 productos. Cualquier valor de ese hueco separa igual.
3. **El flag `obsequio` queda como contraste, no como filtro**: 84% de los renglones que el umbral descarta caen en productos marcados. Que coincidan valida la lectura; que no coincidan del todo es lo que impide usar el flag solo.
4. **Los descontinuados no se excluyen del backtest.** `disabled` es estado de hoy, como el stock de ADR-004. Aplicarlo a cortes históricos es **sesgo de supervivencia**: al corte 2024-12, 184 productos hoy-`disabled` vendían y valían 2,82% del revenue de esa ventana; excluirlos borra justamente los productos que después murieron e infla el piso. Para el backtest rige el criterio empírico ya validado (`roadmap-motor.md` §12.1: silencio final que supere el hueco más largo del propio producto, 5,8% real). El flag se usa **solo en la corrida productiva**, donde "hoy" es efectivamente hoy.
5. **No se agrega regla para el ".":** al ser subconjunto de `disabled` no aporta información. Se documenta la equivalencia para que nadie la escriba dos veces.

**Consecuencias:** el universo baja de 2.189 a **2.128 productos** y el extract de 137.399 a 135.409 filas. **El piso de M1.8 (`backtests/baselines-real-2026-07-31.md`) queda medido sobre otro universo** y hay que re-congelarlo antes de que M2.5 compare contra él; el efecto en las métricas debería ser chico (los obsequios son 0,016% de las unidades y WAPE es `Σ|e|/Σ|y|`, ponderado por magnitud) pero eso **hay que medirlo, no suponerlo**. El ETL de R1 se come las mismas dos trampas: va a sumar obsequios como ventas y a leer el "." como parte del nombre.

6. **El deflactor directo se acota contra el nivel, y el IPC no cuenta como nivel.** Sacar los obsequios bajó el deflactor máximo de 1.227.361 a 13.821, pero quedaban **55 filas en 7 productos** por precios de $0,07–$0,10, otro centinela apenas arriba del umbral (subirlo a $1 dejaba 7 filas y tampoco cerraba). Se agrega `LIMITE_DESVIO_NIVEL = 10`: se acota `q = d / d_nivel` a `[1/10, 10]` y se reconstruye `d = clip(q) × d_nivel`.

   **No se puede acotar `d` directo** porque su magnitud legítima crece con la distancia al corte —mediana 1,02 en el año en curso contra 54,4 a ocho años, máximos legítimos ~560—, así que cualquier cota fija recorta inflación real. `q` en cambio es adimensional (mediana 0,980, p99 2,22) y **es inmune a los eventos macro**: una devaluación mueve numerador y denominador juntos, que es justo lo que obligó a `LIMITE_RELATIVO` a subir hasta 3.

   **El contraste se hace solo contra categoría y laboratorio, nunca contra el IPC.** Los dos primeros se construyen con los relativos de los propios productos del cliente, así que despegarse de ellos es señal; el IPC es un índice macro que no tiene por qué seguir precios veterinarios, y recortar contra él castigaría al producto por no seguir a la inflación general. Esa distinción es lo que hace que el recorte **no contradiga a ADR-002**: la cascada de ADR-002 sirve para *estimar un precio que falta*, y esto es otra operación, *validar uno que se observó*. Y es lo que mantiene intacta la garantía de **CP-INF-01** — verificado: con el recorte aplicado también al IPC, el caso de aceptación falla.

   Medido sobre el extract: **0 filas con deflactor > 1.000** (eran 55), máximo **319**, revenue real total **−0,32%** y la serie anual sin cambios de 2021 en adelante.

**Alternativas descartadas:** (a) **excluir por `producto.obsequio`** — borra 0,92% de revenue real de 12 productos que venden de verdad; (b) **excluir por precio a nivel producto** ("nunca superó $0,05") — 58 productos, pero se lleva puestos los que venden y además regalan, y deja afuera el caso inverso; (c) **excluir los `disabled` del backtest** — sesgo de supervivencia medido; (d) **regla propia para el "."** — redundante con `disabled`.

**Docs impactados:** `docs/contrato-ingesta.md` (§1/§3: el exportador tiene que decir si un renglón es obsequio, o DemandSync sigue infiriéndolo por precio), DER (`producto.obsequio` y `producto.disabled` como atributos, y que `disabled` no tiene fecha), Plan de Pruebas UTN (CP-INF-* y el universo de CP-VOL-01), `docs/datos-defeve.md` (los dos flags y la convención del "."), `motor/roadmap-motor.md` §5.4/§5.5/§6.2/§9 (hecho), `motor/scripts/README.md`. Los documentos formales los edita el Analista Funcional — registrado como pendiente en `planning/roadmap.md`.

---

## ADR-013 — El monto deflactado a grano producto es el target reescalado; la señal de precio real a ese grano es el precio relativo al nivel

**Estado:** **Aceptada (2026-08-04)** por el ML Specialist. Es regla de construcción de features del motor —qué columna lleva señal y cuál es una identidad algebraica— y no cambia hechos persistidos, ni el contrato de ingesta, ni ADR-002. El impacto sobre el Plan de Pruebas queda como **pendiente informativo** del Analista Funcional en `planning/roadmap.md`.

**Contexto:** `plan-diseno.md` §M2 especificaba, entre las features del modelo global, *"precio real deflactado y su variación"*. Al implementar M2.2 se midió esa columna sobre el extract real (`C:/dfv-extract-v2`, 2.128 productos, corte 2025-05) y resultó **degenerada por construcción**, no por un problema de datos:

1. **`precio_prom × deflactor = ancla`, en el 99,15% de las filas con precio propio utilizable.** El deflactor de ADR-002 es `d = ancla / P̂`, y cuando el mes tiene precio propio utilizable `P̂ = precio_prom`, así que el precio se cancela contra sí mismo. El CV intra-producto de esa columna da **0,0000** (el precio nominal da 1,2809): es una constante por serie, y "su variación" es una columna de ceros. **Deflactar un precio con un deflactor construido a partir de ese mismo precio es una identidad, no una medición.**
2. **`revenue_real = unidades × ancla`, en el 99,13% de las filas.** Por lo mismo: a grano producto el monto deflactado es el **target multiplicado por una constante por serie**. No es leakage —el ancla se calcula con datos ≤ corte— pero tampoco es señal independiente; alimentarlo como feature es darle al modelo su propio target reescalado.

Nada de esto contradice a ADR-002 ni la debilita. Al contrario: es su consecuencia aritmética. ADR-002 deflacta **montos observados a grano cliente×producto**, donde `revenue_cliente × d = unidades × P_hoy × (p_cliente/P_t)` conserva el descuento individual — que es exactamente el factor que se cancela cuando el "cliente" es el promedio del propio producto.

**Decisión:**

1. **Ninguna feature monetaria deflactada entra a grano producto** — ni el precio deflactado ni el revenue real. Queda fijado en dos tests (`test_el_precio_deflactado_propio_es_exactamente_el_ancla`, `test_el_monto_deflactado_es_el_target_reescalado`) para que nadie la reintroduzca creyendo que es señal.
2. **La señal de precio real a grano producto es el precio del producto contra el índice de su nivel:** `precio_rel_nivel_t = precio_prom_t × I_nivel(corte)/I_nivel(t) / ancla`. Es adimensional, no arrastra inflación y es el precio relativo del que depende la elasticidad. Medido: CV intra-producto **0,1511** (p25 0,1056, p90 0,5098) sobre 1.680 productos con ≥12 meses, cobertura **98,99%** de las filas con precio propio, y la variación a 3 meses reparte entre −0,216 (p5) y +0,237 (p95) sin una sola fila en cero.
3. **Es una feature de forma, no de nivel.** El nivel arrastra una constante por producto, porque el ancla es el promedio ponderado de 3 meses y no el precio del corte (≈1,05 en una serie que crece al 5% mensual). Lo exacto es que un producto que se movió igual que su categoría tiene la serie **plana** y uno que se encareció contra ella la tiene **creciente** — el signo se lee al revés de lo que sugiere la intuición y está fijado en un test.
4. **El contraste es contra categoría y laboratorio, nunca contra el IPC** — mismo criterio y mismo motivo que `LIMITE_DESVIO_NIVEL` (ADR-012 punto 6): los niveles del cliente son un espejo construido con sus propios productos, el IPC es un índice macro que no tiene por qué seguir precios veterinarios.
5. **A grano cliente el monto deflactado sigue siendo válido y necesario.** El RFM de M3.3 (`valor_monetario`, **CP-INF-04**) y `valor_anual_estimado` de `CLIENTE_FEATURE` se calculan sobre montos deflactados como estaba previsto: ahí el descuento individual del cliente sobrevive y el monto **no** colapsa al target. Esta decisión acota el grano producto, no la deflación.

**Consecuencias:** la lista de features de `plan-diseno.md` §M2 se corrige (y con ella se sacan otras dos cosas: `mismo_mes_año_anterior`, que a grano mensual **es** `lag 12`, y `CLIENTE_FEATURE`, diferida a M3.2 porque el extract real no tiene cliente×producto y en M2 solo se podría ejercitar en sintético). El riesgo que esta decisión evita es de los que no fallan: una feature constante no rompe nada, entrena peor y nadie se entera; una feature colineal con el target puede además **mejorar el WAPE del backtest sin mejorar la predicción**, que es la clase de buena noticia contra la que existe la red de M1.3.

**Alternativas descartadas:** (a) **construir la columna literal y documentar que es constante** — cumple la letra de la especificación y mete una columna muerta que después alguien va a intentar interpretar; (b) **normalizar el precio relativo por el precio del corte en vez del ancla**, que haría la lectura "1,0" exacta — se descartó porque el precio del corte solo existe para el 73,2% de los productos (§6.2), mientras que el ancla cascadea y cubre el 99,95%: se cambiaba interpretabilidad por cobertura; (c) **usar el deflactor contra el IPC como contraste** — rompe CP-INF-01 y contradice a ADR-002, ya medido en ADR-012 punto 6.

**Docs impactados:** `motor/plan-diseno.md` §M2 (hecho), `motor/roadmap-motor.md` §6/§6.3/§9 (hecho), `motor/src/motor/features/README.md` (hecho), `motor/src/motor/deflacion/README.md` (hecho), Plan de Pruebas UTN (CP-INF-04: dejar explícito que el monto deflactado del RFM es a grano **cliente**, donde sí conserva señal — no cambia el caso, precisa su grano). El documento formal lo edita el Analista Funcional: registrado como pendiente en `planning/roadmap.md`.

---

## ADR-014 — El clima no es feature del modelo de demanda; queda como variable de contexto mock

**Estado:** **Propuesta (2026-08-05)** — a ratificar con el **Project Manager** y el **Analista Funcional**. A diferencia de ADR-007/008/010/012/013, esta decisión **no cae bajo la autoridad técnica del ML Specialist**: toca el *Objetivo del Producto* del Acta de Proyecto aprobada y los supuestos de CU-03 y CU-09, así que es una decisión de **alcance** y la ratifica quien es dueño del alcance. El motor ya opera así desde M2.2 —no existe ninguna feature climática en el código— de modo que lo que este ADR hace no es cambiar el comportamiento sino **dejar de tener esa decisión escrita solo en documentos del motor**.

**Contexto:** cinco lugares de la documentación aprobada comprometen clima.

| Documento aprobado | Qué dice |
|---|---|
| Acta, *Objetivo del Producto* 1 | "Integrar y normalizar fuentes de datos externas (APIs) para incorporar series temporales de **condiciones climáticas** y métricas macroeconómicas" |
| Acta, *Objetivo del Producto* 2 | "Ejecutar modelos de series temporales y **Machine Learning multivariable**" |
| CU-03, *Supuestos y Dependencias* | "La **variable climática** y macroeconómica **ya está incorporada al pipeline**" |
| CU-09, pasos 4–5 | El RAG recupera "**variables climáticas**" y la plantilla de respuesta las cita como razón: "debido a [razón basada en segmento/**clima**/historial]" |
| Gantt (línea base 2026-05-26), tarea 41 | "Integración API Climática", 2026-09-22 → 2026-10-06, dentro del módulo de Ingesta |

Contra eso, la evidencia relevada en M0 (`motor/viabilidad.md` §2.6, con fuentes) dice que el clima como **driver de precisión** tiene valor modesto y de corto plazo: el caso mejor documentado logra reducciones de error grandes en porcentaje pero equivalentes a **~2% de las ventas**, y el beneficio se concentra en horizontes **≤7 días**, donde existe pronóstico meteorológico. El motor pronostica a **grano mensual, horizonte 1–12 meses**: a esa distancia el clima futuro **no se conoce**. Una feature climática solo podría usar clima *observado*, que no está disponible en el momento de predecir t+6 — y meterlo de todos modos sería exactamente el leakage que ataja la red de M1.3.

Hay además una restricción del propio proyecto que decide la cuestión de hecho: `docs/contrato-ingesta.md` §6 define `variables_externas_<AAAAMM>.json` como **series simuladas** ("mock en el MVP"), conforme a la restricción del Acta de operar contra archivos JSON. O sea que **el dato climático que el sistema va a tener en el MVP es sintético**, no medido. Entrenar sobre él no puede producir señal, por construcción.

**Decisión:**

1. **Ninguna variable climática entra como feature del modelo de demanda** en M2 ni M3. La lista de features cerrada en M2.2 (`plan-diseno.md` §M2, ADR-013) no la incluye y no se agrega.
2. **La señal climática se captura indirectamente por estacionalidad de calendario** — `mes del año`, ya implementado en M2.2 como `date_features` de `mlforecast`. Es la parte de la señal que sí es predecible a 12 meses: la campaña sanitaria de primavera ocurre todas las primaveras. Es también el orden de valor que fija `viabilidad.md` §3.4 (calendario primero, clima después).
3. **Se mantiene la ingesta mock de `variables_externas`** (contrato §6) y la tarea 41 del Gantt. Cumple el alcance académico del Acta y deja el esquema listo para APIs reales sin tocar la ingesta. Lo que este ADR niega es que el **motor la consuma**, no que exista.
4. **El asistente de explicabilidad (CU-09) no puede presentar el clima como causa de una recomendación mientras el dato sea mock.** Hoy su plantilla de respuesta lo hace de forma explícita. Mostrarle a un vendedor una serie simulada como justificación de una sugerencia real es un problema de honestidad del producto, no un detalle de implementación: el vendedor va a repetirle ese argumento a la veterinaria. **Es la consecuencia más importante de este ADR** y hay que corregirla en CU-09 antes de R4.
5. **Si alguna vez el clima entra, entra con medición y ADR nuevo:** contra el piso congelado de M1, a igual cobertura, y demostrando ganancia en h=1/h=3 —los únicos horizontes donde podría tenerla—. No se agrega "porque está en el Acta".

**Consecuencias:** el Acta conserva la **ingesta** de clima y pierde el ML multivariable **sobre clima**; el modelo global sigue siendo multivariable en el sentido que importa (lags, calendario, categoría, laboratorio y precio relativo al nivel — ADR-013). CU-03 tiene que dejar de afirmar que la variable climática está incorporada al pipeline, porque hoy es falso y va a seguir siéndolo. CU-09 tiene que sacar el clima de su plantilla de respuesta o marcarlo como contexto no causal. El Gantt no cambia. **Ningún caso de prueba existente cae:** no hay CP climático, lo que de paso confirma que el compromiso nunca tuvo criterio de verificación.

**Alternativas descartadas:** (a) **clima real como feature del modelo** — a 6–12 meses exigiría pronóstico climático de una precisión que no existe, y a h=1 el beneficio medido es ~2% de ventas contra el costo de una dependencia externa viva en el batch nocturno; (b) **clima solo en el modelo de h=1** — parte el pipeline multi-horizonte directo de M2.3 en dos configuraciones distintas por ~2% de ventas, y M2.5 dejaría de comparar una sola cosa; (c) **sacar el clima de todo el alcance, incluido el mock** — rompe un objetivo del Acta sin necesidad, cuando el mock cuesta poco y mantiene el esquema abierto; (d) **dejar la decisión donde estaba**, solo en `viabilidad.md` §3.4 y `roadmap-motor.md` §13 — es el statu quo que este ADR viene a cerrar: dos documentos aprobados afirman lo contrario y nadie fuera del motor lo sabe.

**Docs impactados:** **Acta de Proyecto UTN** (*Objetivo del Producto* 1 y 2: precisar que el clima se ingiere y se muestra, no que se modela), **Casos de Uso UTN** (**CU-03** *Supuestos*: retirar "la variable climática ya está incorporada al pipeline"; **CU-09** pasos 4–5: retirar el clima de la plantilla de respuesta o marcarlo como contexto no causal), **Plan de Pruebas UTN** (no cae ningún caso; conviene agregar uno negativo: que el asistente no atribuya causalidad al clima mock), `docs/vision-y-alcance.md` §1 (dice "más fuentes externas (clima, macroeconomía)" — precisar el rol), `motor/viabilidad.md` §3.4 y `motor/roadmap-motor.md` §13 (hecho: pasan a citar este ADR). Los documentos formales los editan el **PM** (Acta) y el **Analista Funcional** (CU, Plan de Pruebas) — registrado como pendiente en `planning/roadmap.md`.

---

## ADR-015 — El compromiso de precisión se acota por horizonte: punto en h=1/h=3, intervalo en h=6/h=12

**Estado:** **Propuesta (2026-08-05)** — a ratificar con el **Project Manager** y el **Analista Funcional**. Es la invocación explícita del **Riesgo 5 del Acta**, que ya pre-autoriza esta mitigación, pero mueve un **criterio de aceptación del Release 2** y el contenido de CU-03, así que no la ratifica el ML Specialist por su cuenta. **El gate interno de M2 no se relaja** — ver punto 5, que es la parte que no hay que leer al revés.

> ⚠️ **Actualización del 2026-08-05, el mismo día, ANTES de ratificar — la evidencia de abajo cambió. Léase junto con ADR-016.**
>
> El contexto de este ADR es la tabla de sesgo del piso **retrospectivo**. Ese mismo día, M1.9 re-congeló el piso con selección **prospectiva** sobre los mismos datos y los mismos checkpoints, y el sesgo a nivel total pasó a **+0,0077 / +0,0203 / −0,0100 / −0,0090** (h=1/3/6/12): **cumple el ±5% en los cuatro horizontes**. Más de la mitad de esa corrección ocurre antes de aplicar la cascada, así que **no** es un efecto de cobertura — el sub-pronóstico de horizonte largo era, en su mayor parte, del criterio de selección y no de los baselines (`roadmap-motor.md` §5.6.2).
>
> **Qué se cae y qué queda en pie.** Se cae la premisa *"los baselines sub-pronostican sistemáticamente en horizonte largo"*, y con ella el argumento del sesgo. **Queda en pie —y reforzado— el argumento de la varianza:** el WAPE a grano producto empeora justamente en horizonte largo (h=6: 0,3114 → **0,4001**), que es lo que sostiene el punto 2 (intervalo calibrado en vez de punto) y el punto 4 (CU-03). También quedan intactos los puntos 3, 5 y 6.
>
> **Esto no lo resuelve el ML Specialist:** el ADR toca el Acta aprobada y sigue en `Propuesta`. Se deja la actualización acá para que el PM y el Analista ratifiquen —o reescriban— sabiendo el número corregido, en vez de ratificar sobre evidencia ya superada. Registrado en `planning/roadmap.md`.

**Contexto:** el piso de baselines quedó congelado el 2026-08-03 sobre datos reales (corrida `a79a9b23676b`, 2.128 productos × 18 cortes, `motor/backtests/baselines-real-2026-08-03.md`). Contra el ±5% de sesgo a nivel total que fija ADR-008:

| horizonte | sesgo total | ¿dentro de ±5%? |
|---|---|---|
| 1 | −0,0338 | sí |
| 3 | −0,0260 | sí |
| 6 | −0,0517 | **no, apenas** |
| 12 | −0,0597 | **no** |

Los baselines **sub-pronostican sistemáticamente en horizonte largo**. Tres cosas hacen que este número sea confiable y no un accidente:

- **Ya se corrigió una vez en la dirección incómoda.** La corrida anterior daba −1,4% a h=12 y `roadmap-motor.md` §5.6 concluyó que "los baselines ya cumplen el gate". Era artefacto de un mes incompleto: 2026-06 entró como mes evaluado con 32% de las unidades, lo que achica `real` y corre `pred − real` hacia arriba, enmascarando el sub-pronóstico. Sacándolo, h=12 pasó de −1,1% a **−8,2%** (§5.6.1).
- **No es efecto de la cobertura.** Rellenando con `WindowAverage` las filas del horizonte truncado, h=12 mejora solo a −0,0530: sigue afuera. El de h=6 sí es de borde (entra a −0,0464).
- **Estaba previsto desde M0, antes de medirlo.** `viabilidad.md` §4 ya listaba como anti-alcance "precisión alta *garantizada* a 12 meses en el contexto macro argentino: se promete el intervalo y el proceso de mejora continua, no un MAPE bajo", y §3.3 ya remitía al Riesgo 5 del Acta.

Y la documentación aprobada dejó la salida escrita:

| Documento aprobado | Qué dice |
|---|---|
| Acta, *Riesgos Identificados* 5 | "Si a largo plazo la varianza es insalvable, **se acotarán las métricas de éxito dándole mayor peso operativo al horizonte de 1 mes**" |
| CU-03, *Problemas / Comentarios* Nota 1 | "Para horizontes de 6 y 12 meses, la varianza del modelo puede ser alta. **El sistema informará esto visualmente** para que el analista lo considere en su decisión" |
| CU-03, curso alternativo paso 4 | Ya contempla "No hay suficiente historial para proyectar este horizonte" |

**Decisión.** Se separan dos cosas que hoy están mezcladas: **qué le promete el producto al usuario** y **qué le exige el gate al modelo**.

1. **El compromiso cuantitativo de precisión del producto se fija en h=1 y h=3**: WAPE por nivel de agregación (ADR-008) y sesgo a nivel total dentro de ±5%. Es lo que se reporta como criterio de aceptación del Release 2.
2. **Para h=6 y h=12 el entregable es el intervalo calibrado, no el punto con error acotado.** El compromiso pasa a ser la **cobertura empírica** del P10–P90 (M2.4): que el intervalo contenga al real aproximadamente el 80% de las veces. Un intervalo ancho y honesto es un entregable; un punto con −6% de sesgo sistemático presentado como precisión, no.
3. **El sesgo se mide y se publica en los cuatro horizontes, siempre con su signo.** En h=6/h=12 se reporta como desvío conocido y direccional (**sub-pronóstico**); no se omite ni se promedia con los cortos. Un analista de compras que sabe que el sistema tira bajo a 12 meses puede corregirlo; uno que no lo sabe, no.
4. **CU-03 Nota 1 sube de nota a criterio verificable.** "El sistema informará esto visualmente" deja de ser una observación y pasa a ser requisito: la vista de h=6/h=12 muestra el intervalo y la advertencia de varianza, no un número seco. Esto además **le da reemplazo al badge de MAPE de CU-03**, que ADR-008 dejó sin implementación y sin dueño (`roadmap-motor.md` §12.3): el indicador de confianza pasa a ser el intervalo, que el motor sí produce.
5. **El gate interno de M2 NO se relaja.** Sigue exigiendo que el modelo global **corrija** el sub-pronóstico de horizonte largo, no que se le perdone: en h=6/h=12 el gate pide empatar el WAPE del piso **y** reportar cobertura empírica del intervalo, y el sesgo del global se compara contra el del piso. Este ADR acota **lo que el producto promete**, no la vara del modelo. Si el global cierra el ±5% en h=6/h=12, tanto mejor y se comunica; lo que no se hace es prometerlo antes de tenerlo.
6. **Se decide ahora, con el número medido y antes de M2.3.** Fijar el criterio de aceptación después de ver si el modelo lo pasa es elegir la vara según el resultado.

**Consecuencias:** el hito de validación del Release 2 en el Acta ("las métricas de error de los modelos predictivos están documentadas") queda cumplible y verificable, con la salvedad de horizonte declarada por escrito en vez de descubierta en la demo. CU-03 gana un requisito (intervalo + advertencia en h=6/h=12) y pierde el badge de MAPE. El Plan de Pruebas del R2 tiene que expresar criterios de aceptación **por horizonte** y no en un número único. **Lo que este ADR no hace:** no saca h=6 ni h=12 del producto — CU-06 (alertas de vencimiento con horizontes 1/3/6) y CU-07 (lead time) los necesitan y el Acta los compromete; los conserva con el entregable correcto.

**Alternativas descartadas:** (a) **prometer ±5% en los cuatro horizontes** — el piso ya lo incumple en dos y no hay evidencia de que el global lo cierre; se estaría prometiendo sobre una expectativa; (b) **sacar h=6/h=12 del alcance** — rompe CU-06, CU-07 y el objetivo del Acta de predicción a 1/6/12, y además el horizonte largo con intervalo ancho **sí sirve** para planificación de compras, que es su caso de uso real; (c) **esperar a M2.5 para decidir** — descartada por el punto 6; (d) **relajar el ±5% de ADR-008 a un número más laxo en todos los horizontes** — degrada la métrica donde hoy se cumple (h=1 da −3,4%) para acomodar donde no; declarar la diferencia por horizonte es más honesto y más útil.

**Docs impactados:** **Acta de Proyecto UTN** (*Riesgos* 5: registrar que la mitigación se invocó, con fecha y número; hito de validación del Release 2: criterios por horizonte), **Casos de Uso UTN** (**CU-03**: RNF y paso 4(c) — el indicador de confianza pasa a ser el intervalo P10–P90; Nota 1 pasa de nota a criterio), **Plan de Pruebas UTN** (criterios de aceptación del R2 por horizonte: ±5% en h=1/h=3, cobertura empírica del intervalo en h=6/h=12), **Matriz de Gestión de Riesgos UTN** (la fila "la métrica de error (RMSE/MAPE) supera el umbral" pasa a WAPE/sesgo por horizonte — ver también ADR-008), `motor/plan-diseno.md` §M2 y `motor/roadmap-motor.md` §6 (gate de M2) y §5.6.1 (hecho: pasan a citar este ADR). Los documentos formales los editan el **PM** (Acta, Matriz de Riesgos) y el **Analista Funcional** (CU, Plan de Pruebas) — registrado como pendiente en `planning/roadmap.md`.

## ADR-016 — El piso contra el que se mide M2 usa selección prospectiva con cascada por disponibilidad

**Estado:** **Aceptada (2026-08-05)** — es un criterio de medición interno del motor, no toca documentación aprobada. **Pero su punto 5 sí tiene consecuencias fuera del módulo** y esas las decide el PM: corrige la evidencia sobre la que se escribió **ADR-015**, que sigue en `Propuesta`.

**Contexto.** El piso de baselines se congeló el 2026-08-03 (`motor/backtests/baselines-real-2026-08-03.md`, corrida `a79a9b23676b`) con la selección por serie que especifica `plan-diseno.md` §M1: cada producto queda con el candidato de menor MASE **promediado sobre todos los cortes** del backtest, y ese ganador se aplica también a los cortes más viejos. El modelo de cada serie se eligió, entonces, con información posterior a las filas donde después se lo mide.

No es el leakage que ataja la red de M1.3 — cada predicción individual sigue siendo limpia; lo que usa información posterior es la elección de *qué modelo* mirar. Pero `roadmap-motor.md` §12.5 lo registró desde el 2026-07-29 como decisión pendiente, con dos consecuencias medidas:

1. **El piso queda inflado**: el hindsight es un privilegio que el modelo global de M2 no tendría, así que M2.5 compararía contra una cancha inclinada.
2. **Y además pierde cobertura, lo que lo infla otra vez**: 5.655 filas (31% de las que no tienen predicción) son series jóvenes donde el ganador retrospectivo no podía cubrir el horizonte pedido aunque otros 5 o 6 candidatos sí predijeron. Las filas que se caen son las más difíciles, así que omitirlas mejora el WAPE por omisión.

Por (2) quedó descartada la mitad de la solución: darle al global el mismo trato retrospectivo no alcanza, porque el hindsight no es solo un criterio de selección más laxo sino una fuente de filas sin predicción. Nivelar hacia lo prospectivo es la única variante que hace las dos tablas comparables fila a fila.

**Decisión.**

1. **La selección del piso pasa a ser prospectiva:** el ganador de cada serie se reelige en cada corte. `motor.modelado.seleccion.elegir_mejor_por_corte`.
2. **Regla de observabilidad, estricta:** en el corte `t` la selección solo puede usar el error de las filas cuyo mes objetivo ya ocurrió (`anio_mes <= t`). Un pronóstico emitido en `t−1` a h=12 no se usa para elegir hasta que su mes llegue. La variante laxa —"todos los cortes anteriores completos"— parece prospectiva y no lo es: mira horizontes que en `t` todavía no se realizaron.
3. **Cascada por disponibilidad:** si el modelo elegido no produce predicción para una celda, se baja al siguiente mejor **de su propio ranking** que sí la produzca. Si **ningún** candidato predijo, la celda queda vacía: eso es arranque en frío genuino y no se inventa un número.
4. **La misma regla rige para el modelo global en M2.5.** Si el champion/challenger eligiera por serie con hindsight, se reabre el mismo problema del otro lado y la comparación vuelve a estar inclinada, ahora a favor del global.
5. **La tabla retrospectiva no se borra ni se corrige: deja de ser el piso.** `baselines-real-2026-08-03.md` queda como registro histórico y como base de los hallazgos de `roadmap-motor.md` §5.3 y §5.6.1 punto 4. El piso de M2.5 es `baselines-real-prospectivo-2026-08-05.md`. Cada tabla congelada declara su criterio en el encabezado; una que no lo declare no se puede comparar contra ninguna otra.

**Consecuencias.**

- **El piso baja de calidad y sube de honestidad, como estaba previsto:** WAPE a grano producto 0,287 → **0,331** en h=1 (el piso viejo reportaba un error 13% menor del alcanzable), y la cobertura a h=12 sube de 0,8880 a **0,9104**. Lo que queda sin cubrir son **12.700 filas** — exactamente las que §5.6.1 había atribuido a altas de catálogo. La cascada cerró el 100% del componente reparable.
- **La cascada resultó no ser opcional.** Sin ella, la selección prospectiva **empeora** la cobertura respecto del piso viejo (0,8651 contra 0,8880 a h=12): reelegir por corte hace que más series queden con un ganador incapaz de cubrir el horizonte.
- **El sub-pronóstico sistemático de horizonte largo era, en su mayor parte, del criterio de selección — no de los baselines.** A nivel total, el sesgo pasa de −0,0517 (h=6) y −0,0597 (h=12), que incumplían el ±5% de ADR-008, a **−0,0100 y −0,0090**. Más de la mitad del movimiento ocurre **antes** de aplicar la cascada, o sea que no es un efecto de cobertura: es que el ganador retrospectivo se aplicaba también a los tramos donde ya no era el mejor. **Esto contradice la evidencia sobre la que se escribió ADR-015** (ver abajo).
- Costo de producir el piso nuevo: **12 segundos**, reusando los checkpoints de la corrida original. Sin ellos habrían sido 294 min. Los checkpoints de una corrida no se borran hasta cerrar el análisis que dependa de ella.
- El gate de M1 no se mueve: exigía una tabla congelada con su desagregado, no que se hubiera congelado con un criterio en particular.

**Relación con ADR-015 (para el PM, no para el ML Specialist).** ADR-015 acota el compromiso de precisión del producto por horizonte —punto en h=1/h=3, intervalo calibrado en h=6/h=12— invocando el Riesgo 5 del Acta, y su contexto es la tabla de sesgo del piso **retrospectivo**. Con el piso corregido, la afirmación *"los baselines sub-pronostican sistemáticamente en horizonte largo"* **ya no se sostiene tal como está escrita**: el piso prospectivo cumple el ±5% en los cuatro horizontes. Lo que **sí** se refuerza es el otro pilar del mismo ADR: la varianza de horizonte largo, porque el WAPE a grano producto empeora justamente ahí (h=6: 0,3114 → 0,4001). ADR-015 sigue en `Propuesta` y **no se modifica ni se retira desde el motor** — se le agrega la actualización con el número nuevo para que el PM y el Analista lo ratifiquen sabiendo esto. Ratificarlo sobre una evidencia que ya se sabe superada sería peor que revisarlo.

**Alternativas descartadas:** (a) **darle al global el mismo trato retrospectivo** — descartada por §12.5: el hindsight también produce filas sin predicción, así que igualar el criterio no iguala la cobertura; (b) **burn-in de k cortes** para que la selección arranque con evidencia — medido: descartar el primer corte mueve el WAPE h=1 de 0,3305 a 0,3259 y descartar más **no mejora**, así que habría costado cortes de evaluación y roto la comparación fila a fila contra el piso congelado, sin comprar precisión; (c) **observabilidad laxa** (cortes anteriores enteros) — más evidencia por serie desde el arranque, pero usa horizontes que en el corte todavía no se realizaron: no es replicable por un pipeline real; (d) **no rellenar las celdas huérfanas y comparar sobre la intersección en M2.5** — evita inventar, pero descarta las series jóvenes, que son las más difíciles, y esconde una diferencia real de cobertura entre los dos métodos.

**Docs impactados:** `motor/plan-diseno.md` §M1 (la advertencia de selección retrospectiva pasa a citar este ADR) y §M2 (criterio de promoción: deja de decir "decisión pendiente"), `motor/roadmap-motor.md` §5.6.2 (nuevo), §5.7, §9 y §12.5 (cerrada), `motor/backtests/README.md` (el criterio de selección pasa a ser condición explícita de congelado), `motor/src/motor/modelado/seleccion.py` (docstrings). **Fuera del módulo, para el PM:** revisar **ADR-015** a la luz del punto 5 antes de ratificarlo, y con él la línea del **Acta** (*Riesgos* 5) y del **Plan de Pruebas** que ese ADR toca — registrado como pendiente en `planning/roadmap.md`.
