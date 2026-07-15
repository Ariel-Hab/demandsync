# Corrección del DER — DemandSync

**Fecha:** 2026-07-05
**Autor:** Equipo DFV (validación desde el sistema fuente)
**Documento corregido:** *Especificación del Modelo de Datos (DER) — UTN 2026* (25 entidades, 9 módulos, 35 relaciones)
**Base de la corrección:** validación del DER contra el sistema real que alimentará a DemandSync — snap MySQL (réplica de solo lectura del ERP), módulo Analytics de Cotizaciones y el diseño interno del predictor (`00_brainstorming.md`, `01_normalizacion_precios_inflacion.md`).

---

## 0. Contexto de la corrección

DemandSync es la **formalización externa** del módulo predictor de ventas de DFV. El DER fue elaborado por relevamiento, **sin acceso directo** al sistema fuente. Estas correcciones lo alinean con lo que DFV **realmente puede alimentar** y con decisiones de diseño ya tomadas internamente. El modelado relacional en sí es correcto; los ajustes son sobre **qué datos existen** y **qué falta para que el predictor funcione**.

Confirmaciones del lado DFV que enmarcan todo:
- El histórico de ventas real arranca en **sept-2018 (~96 meses ≈ 8 años)** — el horizonte de 5-10 años del plan es realista.
- El snap expone **stock y lotes con vencimiento vigentes (dato actual), pero NO histórico de movimientos de stock.**
- DFV ya tiene una **segmentación operacional determinística** propia (no RFM+K-Means).
- La deflación por inflación **debe implementarse** (decisión tomada) con el índice implícito por producto.

---

## 1. Mapa entidad → realidad DFV

| Entidad DER | ¿La alimenta DFV? | Fuente real | Nota |
|---|---|---|---|
| ROL / USUARIO / SESION | No (propias) | — | Auth interna de DemandSync. OK, sin cambios. |
| CLIENTE | ✅ Sí | snap: padrón de clientes (~1.500) | `codigo_erp` ↔ código cliente del ERP. |
| CATEGORIA_PRODUCTO | ✅ Sí | snap: rubros/categorías | OK. |
| PROVEEDOR | ⚠️ Parcial | snap: laboratorios | `lead_time_dias` **no** está en el snap (es parámetro de compras) → cargar por config. |
| PRODUCTO | ⚠️ Parcial | snap: vademécum | `precio_lista` vigente ✅; `margen_rentabilidad` y `stock_seguridad` son config, no vienen del snap. |
| LOTE | ⚠️ Actual sí, histórico no | snap: stock/lote **vigente** | `cantidad_disponible`/`fecha_vencimiento` actuales ✅; **sin serie histórica de stock**. |
| VENTA | ✅ Sí | snap: `factura` (+ `remito`) desde 2018 | Falta discriminar tipo de comprobante (ver C6). |
| DETALLE_VENTA | ✅ Sí | snap: `producto_factura` (+ `producto_remito`) | `precio_unitario` real con descuento ✅; `id_lote` por renglón **probablemente no** existe. |
| FUENTE_DATOS / VARIABLE_EXTERNA | No (mock) | — | Clima/macro simulados. OK. |
| PROCESO_INGESTA / EJECUCION_MODELO | No (propias) | — | Bitácoras internas. OK. |
| SEGMENTO / CLIENTE_SEGMENTO | Genera DemandSync | ML propio | Reconciliar con la segmentación operacional DFV (C4). |
| PREDICCION_DEMANDA | Genera DemandSync | modelo | OK. |
| RECOMENDACION | Genera DemandSync | modelo | `margen` depende de costo → `dm_costos_ppp` (C3). |
| ALERTA_VENCIMIENTO | Genera DemandSync | LOTE **actual** + demanda | Funciona con stock actual real. OK. |
| SUGERENCIA_REDISTRIBUCION | Genera DemandSync | modelo | OK. |
| BORRADOR_ORDEN_COMPRA / DETALLE_BORRADOR | Genera DemandSync | stock actual + demanda + `lead_time` | `lead_time` por config (ver PROVEEDOR). |
| PARAMETRO_SISTEMA | No (propia) | — | OK. |
| CONSULTA_ASISTENTE / FRAGMENTO_RAG | No (propias) | pgvector | OK. |

---

## 2. Correcciones estructurales (agregar al modelo)

### C1 — Capa de hechos mensuales agregados (faltante, crítico)

El DER llega solo al **grano transaccional crudo** (VENTA/DETALLE_VENTA). El predictor necesita una capa de **hechos mensuales inmutables** por encima. Agregar dos entidades **derivadas** (materializadas desde DETALLE_VENTA, append-only, nunca mutan):

**`HECHO_VENTA_MENSUAL_PRODUCTO`**
| Atributo | Tipo | Nota |
|---|---|---|
| id_producto (FK) | INT | → PRODUCTO |
| anio_mes | DATE | primer día del mes; PK compuesta con id_producto |
| unidades | DECIMAL(14,2) | Σ cantidad del mes |
| revenue | DECIMAL(16,2) | Σ subtotal del mes (nominal) |
| precio_prom | DECIMAL(14,4) | `revenue / unidades` = promedio **ponderado por cantidad** |

**`HECHO_VENTA_MENSUAL_CLIENTE_PRODUCTO`**
| Atributo | Tipo | Nota |
|---|---|---|
| id_cliente (FK) | INT | → CLIENTE |
| id_producto (FK) | INT | → PRODUCTO |
| anio_mes | DATE | PK compuesta |
| unidades | DECIMAL(14,2) | |
| revenue | DECIMAL(16,2) | nominal |

**Por qué:**
1. `precio_prom` mensual por producto es el **ancla** de la deflación (C2).
2. Resuelve la prueba de volumen `<2s`: no se agregan 8 años de renglones al vuelo.
3. Inmutables → habilitan recalcular a "precio de hoy" en cualquier momento sin re-ingestar.

> Valores **nominales**, sin deflactar. La deflación es un paso de lectura (C2), no se persiste sobre los hechos.

### C2 — Mecanismo de normalización por inflación (deflación a hoy)

El DER solo tiene la serie de **IPC macro** (`VARIABLE_EXTERNA` tipo "inflación"). No alcanza: en 8 años de historia en pesos, los montos nominales no son comparables, y deflactar con IPC macro **borra el descuento individual** de cada cliente — justo lo que el predictor necesita conservar.

**Regla de fondo:** los hechos mensuales quedan nominales e inmutables; "llevar a hoy" se aplica en **read-time** al armar las features del modelo.

**Fórmula (por cada `(cliente, producto, mes)`):**
```
monto_real = revenue_cliente,t × ( precio_prom_producto_hoy / precio_prom_producto,t )
```
- Ancla = `precio_prom` del **producto** (sobre todos los clientes), NO el monto del cliente.
- Preserva el descuento individual: el término `precio_cliente,t / precio_prom,t` sobrevive a la operación.
- **Error a evitar:** re-tasar como `unidades × precio_prom_hoy` cancela el descuento. NO hacerlo así.

**Agregar entidades derivadas (refresco mensual / read-time, mutan con "hoy"):**

**`ANCLA_PRECIO_PRODUCTO`** — `id_producto`, `precio_prom_hoy` (última ventana estable de 1-3 meses de la serie implícita), `fecha_calculo`.

**`INDICE_PRECIO_NIVEL`** — índice para el **fallback** cuando el producto no tiene ventas recientes: `nivel` (categoría/laboratorio), `id_nivel`, `anio_mes`, `indice` (media geométrica ponderada de los relativos de sus productos). Cadena de fallback:
```
producto → categoría → laboratorio → IPC INDEC (VARIABLE_EXTERNA, red de seguridad final)
```

**Sanidad:** clamp de ratios (criterio existente `PPP ≤ precio×3`; cuidado con precios basura `0.01`/`3.20`) para que un precio roto no dispare el índice de toda la categoría.

> **Rol del IPC macro:** `VARIABLE_EXTERNA` inflación queda como **fallback final**, no como deflactor primario. Aplica tanto al histórico como a los datos futuros que se vayan ingiriendo.

### C3 — Features del cliente que consume el modelo (faltante)

El DER no tiene dónde guardar los **features por cliente** que el predictor usa como entrada — hoy los produce el módulo Analytics de DFV. Agregar `CLIENTE_FEATURE` (o columnas en CLIENTE), poblado por la ingesta:

`id_cliente`, `categoria_principal`, `frecuencia_compra`, `volumen_anual`, `valor_anual_estimado`, `tendencia_volumen_3m`, `recency_dias`, `fecha_calculo`.

Son las variables que alimentan el modelo de demanda y el prior de clientes nuevos (< 6 meses de historial → usar el promedio del segmento más cercano).

### C4 — Segmentación: reconciliar con la operacional de DFV

DFV **ya tiene** segmentación operacional **determinística** (percentiles P33/P67, reglas). La `SEGMENTO`/`CLIENTE_SEGMENTO` de DemandSync (RFM+K-Means) es un **segundo** sistema. Corrección:
- Mantenerlos **distintos y bien nombrados**: la operacional de DFV entra como *feature* (C3); la de DemandSync es agrupamiento ML propio para el predictor.
- **Caveat ADR-014:** `SEGMENTO` versionado por `EJECUCION_MODELO` está **bien** (cada corrida es un snapshot, no reusa `cluster_id` estable). **Pero** `id_segmento` **no debe entrar como feature de entrenamiento** del modelo entre corridas (los IDs cambian de significado → corrompen el historial). En `PREDICCION_DEMANDA` el `id_segmento` es solo dimensión de **salida** (scoping) — el DER ya lo tiene opcional, correcto; confirmar que se respeta.
- Recomendación de método: para el clustering, **Ward jerárquico** (determinístico) es preferible a K-Means por reproducibilidad. Si se mantiene K-Means, fijar semilla y versionar por corrida (ya lo hace).

### C5 — Inventario: ajustar a "stock actual sí, histórico no"

- `LOTE.cantidad_disponible` / `fecha_vencimiento` / `fecha_ingreso`: **datos reales actuales** del snap ✅. Mantener.
- **Sin serie histórica de stock** → no modelar rotación pasada ni lags de stock. `ALERTA_VENCIMIENTO` y `SUGERENCIA_REDISTRIBUCION` operan sobre **stock actual + demanda predicha**, que es exactamente lo que necesitan. OK.
- `LOTE`–`DETALLE_VENTA` (0..1): **mantener opcional.** El snap casi seguro no informa el lote por renglón de venta. **No** pasarla a obligatoria (contradice su propia nota "a validar con el cliente" — acá está validada: queda 0..1).

### C6 — VENTA: tipo de comprobante + deduplicación

El snap tiene **dos** fuentes de venta: `factura` y `remito`. Una misma venta puede aparecer como remito y luego como factura → **riesgo de doble conteo** que distorsiona toda la serie. Corrección:
- Agregar a `VENTA`: `tipo_comprobante` VARCHAR (`factura` / `remito`).
- Definir en la ingesta la **regla de deduplicación** (p. ej. factura anula remito asociado) para no sumar dos veces.

### C7 — PROVEEDOR ↔ PRODUCTO

- La nota del DER es correcta: DFV tiene productos con **más de un laboratorio**. Si se busca precisión, introducir la tabla puente **`PRODUCTO_PROVEEDOR`** (`lead_time`, precio por proveedor). Para el MVP, 1:N es aceptable si se documenta.
- `lead_time_dias`: no viene del snap → cargar por config/parámetro.

### C8 — Contrato de ingesta

`PROCESO_INGESTA.ruta_origen` (path JSON) asume **ingesta por archivos**. Documentar el contrato real:
- DFV exporta JSON desde el snap: **crudo de ventas 2018→** (`factura`/`producto_factura` + `remito`/`producto_remito`), **catálogo** (cliente, producto, categoría, laboratorio), **stock/lote actual**, y **features de cliente** (C3).
- Alternativa a archivos: el mecanismo **`api_keys`** externo que DFV ya expone, para un feed en vivo en lugar de batch por archivos.

---

## 3. Resumen de cambios

| # | Cambio | Tipo | Prioridad |
|---|---|---|---|
| C1 | Agregar `HECHO_VENTA_MENSUAL_PRODUCTO` y `..._CLIENTE_PRODUCTO` (derivadas, inmutables) | Nuevas entidades | 🔴 Alta |
| C2 | Agregar deflación: `ANCLA_PRECIO_PRODUCTO` + `INDICE_PRECIO_NIVEL`, read-time, IPC como fallback | Nuevas entidades + regla | 🔴 Alta |
| C3 | Agregar `CLIENTE_FEATURE` (features del modelo desde Analytics) | Nueva entidad | 🔴 Alta |
| C4 | Reconciliar segmentación con la operacional DFV + caveat ADR-014 | Regla de diseño | 🟠 Media |
| C5 | Inventario: mantener actual, no modelar histórico; `LOTE–DETALLE` opcional | Ajuste | 🟠 Media |
| C6 | `VENTA.tipo_comprobante` + regla de deduplicación factura/remito | Atributo + regla | 🔴 Alta |
| C7 | `PRODUCTO_PROVEEDOR` (multi-lab) + `lead_time` por config | Ajuste | 🟢 Baja |
| C8 | Documentar contrato de ingesta (JSON export / api_keys) | Documentación | 🟠 Media |

**Sin cambios (correctos):** módulo Seguridad, Datos Externos (mock), Procesamiento, Configuración, RAG, inmutabilidad del histórico, versionado por `EJECUCION_MODELO`, `precio_lista` vigente único.
