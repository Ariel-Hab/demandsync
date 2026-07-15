# Datos del Cliente 1 (DFV / ERP defeve) — Fuente de Verdad

> Qué datos existen **de verdad** en el primer cliente, validado contra su sistema el 2026-07-05 (ver `referencias/02_correccion_der_demandsync.md`). Todo diseño de ingesta y modelado se contrasta contra este documento, no contra supuestos.
> Última actualización: 2026-07-15.

## Origen de los datos

- El ERP del cliente ("defeve", sistema legacy) replica su base a una **réplica MySQL de solo lectura** ("snap"). De ahí salen los exports.
- El cliente además tiene un sistema satélite (Cotizaciones) con un **módulo Analytics** que ya calcula features por cliente (segmento operacional, frecuencia, volumen, etc.) — DemandSync las recibe calculadas, no las recalcula.

## Qué HAY (confirmado)

| Dato | Detalle | Profundidad |
|---|---|---|
| Ventas históricas | `factura` + `producto_factura`, `remito` + `producto_remito` (renglón: producto, cantidad, precio real con descuento) | **Desde sept-2018 (~96 meses ≈ 8 años)** |
| Padrón de clientes | ~1.500 clientes con código ERP, zona, alta | Completo |
| Catálogo / vademécum | Productos con categoría, laboratorio, precio de lista **vigente** | Completo (orden de magnitud: ~2.600 productos) |
| Stock y lotes | Cantidad disponible y fecha de vencimiento **vigentes** (foto actual) | Solo dato actual |
| Features de cliente | Segmento operacional determinístico, categoría principal, frecuencia, volumen anual, etc. (módulo Analytics) | Calculadas a demanda |

## Qué NO HAY (confirmado — diseñar alrededor de esto)

| Faltante | Consecuencia | Adecuación decidida |
|---|---|---|
| **Histórico de movimientos de stock** | No se puede modelar rotación pasada ni detectar quiebres históricos (demanda censurada) | Alertas y redistribución operan sobre stock **actual** + demanda predicha (ADR-004). Limitación documentada: ventas ≈ demanda |
| **Precio de lista histórico** | No hay serie de precios para deflactar 8 años de inflación | Índice **implícito** por producto: `precio_prom = revenue/unidades` mensual (ADR-002) |
| Registro de aumentos con profundidad | La tabla de aumentos del cliente tiene ~2 meses y solo subas ≥0.5% | Inservible para el histórico; utilizable a futuro como índice de lista para períodos recientes |
| Lote por renglón de venta | No se sabe qué lote salió en cada venta | Relación LOTE–DETALLE_VENTA queda opcional (0..1) |
| Lead time por proveedor | No está en el ERP | Parámetro de configuración (CU-10) |
| Margen / stock de seguridad por producto | No vienen del snap | Configuración + ingesta de costos si el cliente la provee |

## Trampas de los datos (obligatorio mitigarlas en la ingesta)

1. **Doble conteo factura/remito**: una misma venta puede existir como remito y luego factura. La ingesta DEBE deduplicar (`tipo_comprobante` + regla factura-anula-remito). Sin esto, toda la serie temporal queda inflada (ADR-003, caso CP-DEDUP-01).
2. **Inflación argentina**: 8 años de montos nominales en pesos no son comparables. Deflactar con IPC macro **borra los descuentos individuales por cliente** — usar el índice implícito por producto (ADR-002, casos CP-INF-*).
3. **Precios basura**: existen precios rotos (`0.01`, `3.20`). Clamp de ratios al construir índices para que un precio roto no dispare el índice de una categoría entera.
4. **Eventos históricos**: el período 2018–2026 incluye COVID (2020), devaluaciones y picos inflacionarios. El motor debe poder marcar/excluir períodos anómalos (dummies de evento).

## Contrato de ingesta (a congelar antes del Release 1)

Export JSON desde el snap, por entidad. Esquema preliminar (el detalle campo a campo se define con el Analista Funcional):

| Archivo | Granularidad | Contenido mínimo |
|---|---|---|
| `ventas_YYYYMM.json` | Renglón de comprobante | tipo_comprobante, nro, fecha, cliente_erp, producto_sku, cantidad, precio_unitario, subtotal, remito_asociado (si factura) |
| `clientes.json` | Cliente | codigo_erp, razón social, zona, localidad, fecha_alta, activo |
| `productos.json` | Producto | sku, nombre, categoría, laboratorio, precio_lista vigente, unidad, requiere_frio, activo |
| `stock_lotes.json` | Lote (foto actual) | producto_sku, nro_lote, vencimiento, ingreso, cantidad_disponible, fecha_foto |
| `cliente_features.json` | Cliente | segmento_operacional, categoria_principal, frecuencia_compra, volumen_anual, recency_dias, fecha_calculo |

Notas:
- El histórico completo 2018→ se exporta **una vez** (backfill); después, export incremental mensual.
- Quién genera los exports: el lado DFV (acceso al snap). El equipo DemandSync recibe además una versión **sintética/anonimizada** para desarrollo (ver `datasets/README.md`).
- Alternativa a archivos para producción futura: feed vía API con api-key (el cliente ya tiene ese mecanismo); no cambia el esquema lógico.

## Escala esperada

- Hechos mensuales por producto: ~2.600 × 96 ≈ **250 mil filas**.
- Hechos mensuales cliente×producto: acotado por combinaciones con venta (sparse); estimación gruesa < 2–3 millones de filas. PostgreSQL lo maneja sin arquitectura especial; el `<2s` se garantiza consultando las tablas mensuales, nunca el crudo.
