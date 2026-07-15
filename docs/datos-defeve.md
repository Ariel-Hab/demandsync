# Datos del Cliente 1 (DFV / ERP defeve) — Fuente de Verdad

> Qué datos existen **de verdad** en el primer cliente, validado contra su sistema el 2026-07-05 (ver `referencias/02_correccion_der_demandsync.md`). Todo diseño de ingesta y modelado se contrasta contra este documento, no contra supuestos.
> Última actualización: 2026-07-15.

## Origen de los datos

- El ERP del cliente ("defeve", sistema legacy) replica su base a una **réplica MySQL de solo lectura** ("snap"). De ahí salen los exports.
- El cliente además tiene un sistema satélite (Cotizaciones) con un **módulo Analytics** que ya calcula features por cliente (segmento operacional, frecuencia, volumen, etc.) — DemandSync las recibe calculadas, no las recalcula.

## Qué HAY (confirmado)

| Dato | Detalle | Profundidad |
|---|---|---|
| Ventas históricas | `factura` + `producto_factura`, `remito` + `producto_remito` (renglón: producto, cantidad, precio real con descuento) | **Desde jul-2018 → 96 meses completos** (EDA 2026-07-15); 1,14M facturas / 5,46M renglones |
| Padrón de clientes | 5.057 clientes en padrón; **1.399 activos** últimos 12m (1.779 en 36m) | Completo |
| Catálogo / vademécum | 10.533 entradas (incluye deshabilitados/servicios); **~2.200–2.400 productos con venta reciente**; categoría, familia, laboratorio, acción terapéutica, precio de lista **vigente** | Completo |
| Stock y lotes | `stock_actual/reservado/pedido` por producto (foto); `fecha_vencimiento` por renglón de venta (completitud a medir) | Solo dato actual |
| Features de cliente | Segmento operacional determinístico, categoría principal, frecuencia, volumen anual, etc. (módulo Analytics) | Calculadas a demanda |

> Perfil estadístico completo (intermitencia, cobertura de ancla, dedup): `../motor/eda/eda-2026-07-15.md`.

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

1. **Doble conteo factura/remito**: una misma venta podría existir como remito y luego factura. Hallazgo EDA 2026-07-15: no hay FK remito→factura en el esquema; el propio ERP computa estadística como **unión de ambas fuentes** filtrando el flag `estadistica ∈ {P,N}`, y el share de remitos cayó de ~80% (2018-2020) a ~5-15% (2024+). La regla definitiva de dedup queda pendiente de confirmar la semántica de `estadistica` con el dueño del ERP (contrato P1; ADR-003, caso CP-DEDUP-01).
2. **Inflación argentina**: 8 años de montos nominales en pesos no son comparables. Deflactar con IPC macro **borra los descuentos individuales por cliente** — usar el índice implícito por producto (ADR-002, casos CP-INF-*).
3. **Precios basura**: existen precios rotos (`0.01`, `3.20`). Clamp de ratios al construir índices para que un precio roto no dispare el índice de una categoría entera.
4. **Eventos históricos**: el período 2018–2026 incluye COVID (2020), devaluaciones y picos inflacionarios. El motor debe poder marcar/excluir períodos anómalos (dummies de evento).

## Contrato de ingesta (a congelar antes del Release 1)

**El contrato campo a campo, con mapeo al esquema real del ERP, está en [`contrato-ingesta.md`](contrato-ingesta.md) (v0.9).** Para congelar v1.0 faltan 4 confirmaciones del lado del ERP (P1 dedup, P2 lotes, P3 semántica de `precio`, P4 criterio de `activo`).

Notas:
- El histórico completo 2018-07→ se exporta **una vez** (backfill); después, export incremental mensual.
- Quién genera los exports: el lado DFV (acceso al snap). El equipo DemandSync recibe además una versión **sintética/anonimizada** para desarrollo (ver `datasets/README.md`).
- Alternativa a archivos para producción futura: feed vía API con api-key (el cliente ya tiene ese mecanismo); no cambia el esquema lógico.

## Escala esperada (calibrada con EDA 2026-07-15)

- Hechos mensuales por producto: ~2.400 activos × 96 ≈ **230 mil filas**.
- Hechos mensuales cliente×producto: 319 mil pares con actividad en 36m, mayoría con 1–2 meses de compra → orden de **1–2 millones de filas** para los 96 meses. PostgreSQL lo maneja sin arquitectura especial; el `<2s` se garantiza consultando las tablas mensuales, nunca el crudo.
