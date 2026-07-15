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

## 1. `ventas_<AAAAMM>.json` — ventas unificadas

> **Frontera de responsabilidad (2026-07-15):** el cliente entrega un feed de **ventas ya consolidado**. La unión factura/remito, la deduplicación, los criterios estadísticos del ERP (`estadistica`, productos no numéricos) y el neteo lógico son responsabilidad del **exportador del lado cliente** (se diseña en su sistema satélite; contrato a refinar con ese equipo). DemandSync **no conoce ni le importa** el tipo de comprobante de origen y NO re-deduplica.

Una entrada por venta, con renglones embebidos:

| Campo JSON | Tipo | Nota |
|---|---|---|
| `venta_ref` | string | Identificador único y estable de la venta en el origen (opaco para DemandSync; habilita idempotencia y re-export) |
| `fecha` | date | |
| `cliente_id` | string | Código ERP del cliente |
| `total` | decimal | Para validación de consistencia contra renglones |
| `zona` | string/null | Dimensión geográfica opcional |
| `vendedor_id` | string/null | Opcional (analítica comercial) |
| `renglones` | array | ≥1 |

Renglón:

| Campo JSON | Tipo | Nota |
|---|---|---|
| `producto_id` | string | Código del vademécum del ERP |
| `cantidad` | decimal | **Negativa para devoluciones/notas de crédito** — DemandSync suma con signo al mensualizar |
| `precio` | decimal | Precio unitario **efectivo** (con descuento aplicado) — garantía del exportador (P3) |
| `fecha_vencimiento` | date/null | Vencimiento por renglón; completitud a medir (EDA §7) |

**Garantías del exportador (lado cliente — parte del contrato):**
1. Sin doble conteo factura/remito (dedup resuelta en origen).
2. Solo renglones estadísticos según los criterios del propio ERP (excluye `estadistica ∈ {P,N}`, servicios/conceptos no numéricos).
3. `precio` = unitario efectivo con descuento; `precio > 0`.
4. Devoluciones/notas de crédito incluidas con `cantidad` negativa (~9,5% de los comprobantes son NC).
5. El mes exportado está contablemente cerrado; re-export del mismo mes reemplaza al anterior (idempotencia por `venta_ref`).

**Reglas de ingesta (DemandSync, testeables):**
1. Validar esquema, tipos y rangos; rechazar y loguear en `PROCESO_INGESTA` lo inválido.
2. Validación de consistencia: `Σ renglones ≈ total` por venta (tolerancia por IVA/redondeo a definir con datos) + totales del mes contra resumen declarado por el exportador.
3. Materializar `HECHO_VENTA_MENSUAL_PRODUCTO` y `HECHO_VENTA_MENSUAL_CLIENTE_PRODUCTO` (ADR-001) tras validar el mes.
4. **No re-deduplicar ni re-filtrar por reglas del ERP**: si una garantía del exportador falla, la ingesta rechaza el archivo y lo reporta — no lo "arregla" en silencio.

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
| P1 | Diseño del **exportador de ventas unificadas** en el sistema del cliente (dedup interna, semántica de `estadistica`, generación de `venta_ref`) — fuera del alcance de DemandSync; v1.0 se congela junto con la primera versión del exportador | Lado cliente | §1 completo |
| P2 | Fuente real de lotes/vencimientos: ¿tabla de lotes trazables? ¿completitud de `fecha_vencimiento` por renglón? | Lado cliente | §4 `lotes`, CU-06 |
| P3 | Garantía "precio efectivo con descuento": confirmar si `precio` de renglón ya lo incluye (validar `Σ renglones` vs `total`) | Lado cliente + Analista | Exactitud del índice implícito |
| P4 | Criterio de `activo` en clientes | Analista | §2 |

Cerrados estos cuatro puntos, este documento pasa a **v1.0 — CONGELADO** y cualquier cambio posterior es versionado (v1.1, v2.0) con actualización del ETL y de los docs UTN (regla "Documentación del TP siempre al día", CLAUDE.md §6).
