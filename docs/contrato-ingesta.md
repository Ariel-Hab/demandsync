# Contrato de Ingesta — DemandSync ⇄ Cliente 1 (v0.9, borrador para congelar)

**Fecha:** 2026-07-15
**Estado:** BORRADOR v0.9 — campo a campo completo, con mapeo al esquema real del ERP (relevado + EDA 2026-07-15). Falta para congelar (v1.0): confirmar la regla de dedup (semántica del flag `estadistica`) y la fuente de lotes (§Pendientes).
**Regla del acta:** el esquema se congela antes del Release 1; cambios posteriores requieren versionar el contrato y actualizar el pipeline ETL (CU-08, Nota 1).

## Convenciones

- Un archivo JSON por entidad, UTF-8, array raíz de objetos.
- Nombres de archivo: `<entidad>_<AAAAMM>.json` para incrementales mensuales; `<entidad>_full.json` para el backfill inicial.
- Fechas `AAAA-MM-DD`; decimales con punto; `null` explícito para ausentes.
- El export es "tonto": vuelca datos con transformación mínima. **Las reglas de negocio (filtros, dedup, neteo de notas de crédito) viven en la ingesta de DemandSync**, donde son testeables (casos CP-*).
- Cadencia: backfill inicial completo (2018-07 →) una única vez; después export mensual del mes cerrado + foto de stock y padrones completos (upsert por código ERP).

---

## 1. `ventas_<AAAAMM>.json` — comprobantes de venta (cabecera + renglones)

Una entrada por comprobante, con renglones embebidos. Cubre **dos fuentes** del ERP: facturas y remitos.

| Campo JSON | Tipo | Origen ERP | Nota |
|---|---|---|---|
| `tipo_comprobante` | string | fuente: `"factura"` \| `"remito"` | Obligatorio (ADR-003) |
| `tipo` | string | `factura.tipo` / `remito.tipo` | Parte de la clave del comprobante en el ERP |
| `numero` | int | `factura.numero` / `remito.numero` | Clave junto con `tipo` |
| `fecha` | date | `factura.fecha` | |
| `cliente_id` | string | `factura.cliente_id` | Código ERP del cliente |
| `nota_credito` | bool | `factura.nota_credito` | `true` → las cantidades restan (~9,5% de facturas) |
| `total` | decimal | `factura.total` | Para validación de consistencia contra renglones |
| `zona` | string/null | `factura.zona` | Dimensión geográfica opcional |
| `vendedor_id` | string/null | `factura.vendedor_id` | Opcional (analítica comercial) |
| `renglones` | array | `producto_factura` / `producto_remito` | ≥1 |

Renglón:

| Campo JSON | Tipo | Origen ERP | Nota |
|---|---|---|---|
| `producto_id` | string | `pf.producto_id` | Alfanuméricos = servicios/conceptos → la ingesta los descarta (regla: solo numéricos) |
| `cantidad` | decimal | `pf.cantidad` | |
| `precio` | decimal | `pf.precio` | Precio unitario efectivo aplicado (con descuento) |
| `descuento` | decimal/null | `pf.descuento` | Informativo; validar si `precio` ya lo incluye (§Pendientes P3) |
| `bonificacion` | decimal/null | `pf.bonificacion` | Idem |
| `estadistica` | string/null | `pf.estadistica` | `''`/`S`/`P`/`N` — la ingesta excluye `P` y `N` (regla del ERP) |
| `fecha_vencimiento` | date/null | `pf.fecha_vencimiento` | Vencimiento por renglón; completitud a medir (EDA §7) |

**Reglas de ingesta (DemandSync, testeables):**
1. Descartar renglones con `producto_id` no numérico, `estadistica ∈ {P, N}`, `precio ≤ 0`.
2. `nota_credito = true` → cantidad y revenue restan.
3. **Dedup factura/remito:** regla exacta pendiente de confirmación con el dueño del ERP (ver Pendientes P1). Mientras tanto vale el criterio del propio ERP: unión de ambas fuentes con los filtros de arriba.
4. Materializar `HECHO_VENTA_MENSUAL_PRODUCTO` y `HECHO_VENTA_MENSUAL_CLIENTE_PRODUCTO` (ADR-001) tras validar el mes.
5. Validación de consistencia: `Σ renglones ≈ total` de cabecera (tolerancia por IVA/redondeo a definir con datos).

## 2. `clientes_full.json` — padrón (upsert)

| Campo JSON | Tipo | Origen ERP | Nota |
|---|---|---|---|
| `codigo_erp` | string | `cliente.id` | Clave |
| `razon_social` | string | `cliente.razon_social` (fallback `nombre`) | |
| `cuit` | string/null | `cliente.cuit` | |
| `direccion` | string/null | `cliente.domicilio` | |
| `localidad` | string/null | `cliente.localidad` | |
| `zona` | string/null | `cliente.zona` | |
| `tipo` | string/null | `cliente.tipo` | |
| `mayorista` | bool/null | `cliente.mayorista` | |
| `condicion_pago` | string/null | `cliente.condicion_pago` | |
| `activo` | bool | derivado (`ultima_venta` reciente / no deshabilitado) | Criterio a fijar con el ERP |
| `fecha_alta` | date/null | **NO EXISTE en el ERP** → proxy: `MIN(fecha)` de su primer comprobante | Hallazgo EDA §7; el DER debe anotarlo |

## 3. `productos_full.json` — catálogo/vademécum (upsert)

| Campo JSON | Tipo | Origen ERP | Nota |
|---|---|---|---|
| `sku` | string | `producto.id` | Clave |
| `nombre` | string | `producto.descripcion` | |
| `categoria_erp_id` | string/null | `producto.categoria_id` | |
| `familia` | string/null | `producto.nombre_familia` (+ `familia_id`) | Nivel de agregación para índices y jerarquía |
| `proveedor_erp_id` | string/null | `producto.proveedor_id` | Laboratorio |
| `accion_terapeutica` | string/null | `producto.accion_terapeutica` | Clasificación terapéutica (CU-06/R3) |
| `principio_activo` | string/null | `producto.principio_activo` | |
| `precio_lista` | decimal | `producto.precio_lista` | Vigente (sin historia — ADR-002) |
| `iva` | decimal/null | `producto.iva` | |
| `unidad_medida` | string/null | `producto.tipo_paquete_id` (mapear) | |
| `requiere_frio` | bool/null | a confirmar (¿`trazable`? ¿otra columna?) | Pendiente P2 |
| `activo` | bool | `NOT producto.disabled` | |

El catálogo completo tiene ~10,5k entradas pero solo ~2,2–2,4k con venta reciente; se exporta completo y DemandSync decide qué modela.

## 4. `stock_<AAAAMM>.json` — foto de stock (reemplazo completo por corrida)

| Campo JSON | Tipo | Origen ERP | Nota |
|---|---|---|---|
| `producto_sku` | string | `producto.id` | |
| `stock_actual` | decimal | `producto.stock_actual` | Foto al momento del export (ADR-004) |
| `stock_reservado` | decimal/null | `producto.stock_reservado` | |
| `stock_pedido` | decimal/null | `producto.stock_pedido` | |
| `fecha_foto` | date | generado por el export | |
| `lotes` | array/null | **fuente a confirmar** (Pendiente P2) | `[{nro_lote, fecha_vencimiento, cantidad_disponible}]` |

## 5. `cliente_features_<AAAAMM>.json` — features del módulo Analytics del cliente

| Campo JSON | Tipo | Nota |
|---|---|---|
| `codigo_erp` | string | Clave |
| `segmento_operacional` | string | Segmentación determinística del cliente 1 (feature + oráculo CP-SEG-01, ADR-005) |
| `categoria_principal` | string/null | |
| `frecuencia_compra` | string/null | |
| `volumen_anual` | decimal/null | |
| `recency_dias` | int/null | |
| `fecha_calculo` | date | |

## 6. `variables_externas_<AAAAMM>.json` — clima/macro (mock en el MVP)

`[{fuente, tipo, fecha, valor, region}]` — series simuladas según la restricción del acta; el esquema es el real para que el paso a APIs verdaderas no cambie la ingesta.

---

## Pendientes para congelar v1.0

| # | Pendiente | Responsable | Bloquea |
|---|---|---|---|
| P1 | Semántica del flag `estadistica` y ciclo remito→facturación → regla de dedup definitiva (hoy: criterio del ERP, unión con filtros) | Lado cliente (acceso al ERP) | Regla 3 de ingesta |
| P2 | Fuente real de lotes/vencimientos: ¿tabla de lotes trazables? ¿completitud de `fecha_vencimiento` por renglón? | Lado cliente | §4 `lotes`, CU-06 |
| P3 | Confirmar si `precio` de renglón ya incluye descuento/bonificación (validar `Σ renglones` vs `total`) | Lado cliente + Analista | Exactitud del índice implícito |
| P4 | Criterio de `activo` en clientes | Analista | §2 |

Cerrados estos cuatro puntos, este documento pasa a **v1.0 — CONGELADO** y cualquier cambio posterior es versionado (v1.1, v2.0) con actualización del ETL y de los docs UTN (regla "Documentación del TP siempre al día", CLAUDE.md §6).
