# Normalización de Precios Históricos a Valor Presente (Inflación)

> Creado: 2026-06-21. Etapa: diseño conceptual.
> Contexto: el training set va de 2018 a hoy (~96 meses) en contexto inflacionario argentino.
> Los montos nominales de 2018 no son comparables con los de 2026 → hay que llevarlos a "precio de hoy"
> antes de sacar estadística/features para la predicción.
> Relacionado: ver [00_brainstorming.md](00_brainstorming.md) (feature pipeline, gap de dm_ventas_mensual, decisión abierta #4).

---

## Marco: dos preguntas distintas

Antes de elegir método, definir qué se mide (dan números diferentes):

| Pregunta | Qué mide | Método |
|---|---|---|
| **(A)** "¿Cuánto gastó el cliente en pesos de hoy?" | Valor real / poder adquisitivo | **Deflactar** el monto nominal por un índice |
| **(B)** "¿Cuánto valdría hoy lo que compró?" | Volumen físico a precio actual | **Re-tasar**: cantidad × precio de hoy |

Para estadística de consumo y features de predicción usamos **(A) deflactar** — permite comparar el gasto
de 2019 vs 2025 en términos reales. Clave: la forma elegida (abajo) **preserva los descuentos individuales**,
que es justo lo que se quiere para modelar comportamiento por cliente.

---

## Fuente del índice: precio implícito, NO precio de lista

El precio de lista **histórico no existe** en el ecosistema:
- Snap MySQL (`producto`): solo precio de lista **vigente**, sin historia.
- PG `aumentos_precio`: solo **~2 meses** de profundidad y registra únicamente subas ≥0.5% → inservible para años.

La única fuente interna que llega tan atrás como las ventas es el **precio implícito de las transacciones**:

```
precio_prom_producto,t = sum(revenue) / sum(unidades)   -- en el mes t, sobre TODOS los clientes
```

Es un promedio **ponderado por cantidad** (no simple — el simple sobre-pesa pedidos chicos).
Resume todas las ventas del mes → ya contempla descuentos individuales y ofertas temporales.

**Fuente de datos:** `dm_ventas_mensual` da revenue + unidades por mes, pero **solo tiene ~25 meses**
(ver gap crítico en el brainstorming). Para los 96 meses hay que computar el implícito desde el extract
histórico del snap (`producto_factura` + `factura` desde 2018) → atado a la **decisión abierta #4** (backfill).

---

## PARTE A — Plan de Ingesta

**Regla de fondo:** los hechos mensuales son **inmutables**; "llevar a hoy" es función del momento en que se
saca la estadística. Por eso la ingesta **solo guarda hechos, NO deflacta**.

Tablas de hechos a ingestar (**append por mes, nunca mutan**):

| Tabla | Granularidad | Campos |
|---|---|---|
| Precio producto | `(producto, año_mes)` | `unidades`, `revenue`, `precio_prom = revenue/unidades` (ponderado) |
| Consumo cliente | `(cliente, producto, año_mes)` | `unidades`, `revenue` |

El `precio_prom` del producto sirve después como **índice/ancla** para deflactar. El revenue por cliente
es lo que efectivamente se deflacta.

> **Por qué separar ingesta de deflación:** "hoy" se mueve; los valores deflactados no son hechos estables,
> solo los nominales mensuales lo son. Guardar crudo permite recalcular a precio de hoy en cualquier momento
> (incluso meses después) sin re-ingestar.

---

## PARTE B — Proceso de Armado de la Estadística (deflación a hoy)

Se aplica en **read-time**, al armar el dataset/features para la predicción. Si se recalcula meses después,
da precios al nuevo "hoy" automáticamente. Solo se recalculan el **ancla** y los coeficientes; los hechos de
la Parte A no se tocan.

### Fórmula clave

```
monto_real_cliente = monto_pagado_cliente,t × ( precio_prom_producto_hoy / precio_prom_producto,t )
```

- El **promedio del producto** (sobre todos los clientes) es el **ÍNDICE/ancla**, NO el valor a deflactar.
- Deflactar el **monto real de cada cliente** por ese ratio **preserva el descuento individual**, porque el
  término `precio_cliente,t / precio_prom,t` (cuánto por debajo/encima del promedio pagó ese cliente)
  sobrevive a la operación.

Desarrollado:
```
= unidades × precio_prom_hoy × ( precio_cliente,t / precio_prom,t )
                                 └────── se preserva (descuento individual) ──────┘
```

### ⚠️ Error a evitar

Re-tasar como `unidades × precio_prom_hoy` **CANCELA** el descuento individual (el ancla es el propio promedio
del producto) → borra exactamente lo que se quería conservar. NO hacerlo así.

### Qué es "precio_prom_hoy"

El último tramo de la **misma serie implícita** (`revenue/unidades`), tomado de una **ventana reciente estable**
(último 1–3 meses, no un mes suelto con pico de oferta). **No** usar el precio de lista: mezclar
lista-sin-descuento con implícito-con-descuento rompe la consistencia.

### Fallback de ancla

Producto sin ventas recientes → no tiene "precio de hoy" propio (también aplica al pasado profundo sin dato):
tomar el último precio conocido e inflarlo a hoy con el índice del nivel superior:

```
producto → categoría → laboratorio → IPC INDEC (red de seguridad final)
```

Los índices por categoría/lab se arman agregando los relativos de precio de sus productos, mejor con
**media geométrica ponderada** (Törnqvist/Laspeyres geométrico) para controlar el efecto mix.

### Sanidad

Clamp de ratios al calcular relativos (ya existe el criterio `PPP ≤ precio×3`; cuidado con precios basura
tipo `0.01` / `3.20`) para que un precio roto no dispare el índice de toda la categoría.

---

## Qué se recalcula cada mes

| Cosa | Cuándo | Muta |
|---|---|---|
| `(producto, mes) → unidades, revenue, precio_prom` | ingest, append por mes | nunca |
| `(cliente, producto, mes) → unidades, revenue` | ingest, append por mes | nunca |
| `precio_prom_hoy` por producto + índice categoría/lab | al armar la estadística | sí (avanza con "hoy") |

---

## Combinación temporal de fuentes (futuro)

- **Pasado profundo (2018→):** índice implícito desde transacciones (única fuente con esa profundidad).
- **Presente/futuro:** a medida que `aumentos_precio` gane profundidad, para períodos recientes se puede usar
  el índice de **precio de lista** (limpio, sin ruido de descuentos) y dejar el implícito para el pasado.

---

## Pendientes / enganches con el resto del proyecto

- [ ] Resolver decisión abierta #4 (backfill snap 2018→ para los 96 meses) — habilita el índice implícito completo.
- [ ] Definir granularidad de las tablas de hechos en el storage del predictor (producto + cliente×producto).
- [ ] Implementar el cálculo de `precio_prom_hoy` + índice categoría/lab con su fallback.
- [ ] Decidir si los features de revenue del modelo usan valor **real (deflactado)** — recomendado, para que los
      lags (`ventas_t-12`, `mismo_mes_anio_anterior`) sean comparables y no estén dominados por la inflación.
