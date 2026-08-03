# `motor/src/motor/deflacion/` — Deflación read-time (M2.1, CERRADA 2026-07-31)

Implementa **ADR-002**. En la ventana del extract real la inflación acumulada es **×79,2**:
sin deflactar, cualquier feature o derivado monetario mide el calendario y no la demanda.

Dónde muerde, en concreto:

- **Features de precio de M2.2** — una variación nominal es inflación; una *real* es señal
  de demanda (si algo aumenta, se vende menos). Sin deflactar, esa señal se pierde.
- **RFM de M3.3** (`valor_monetario`, CP-INF-04) — sin deflactar, los años recientes
  aplastan a los viejos y el clustering termina segmentando por *cuándo* compró el cliente.
- **`valor_anual_estimado`** de `CLIENTE_FEATURE`.

Lo que **no** toca: el target. ADR-007 fijó unidades como target primario justamente para
que la inflación no contamine la predicción central. Esto es un transformador de features
y de derivados monetarios, no del pronóstico.

## Piezas

| Módulo | Qué hace |
|---|---|
| `precios.py` | `es_utilizable()`, `relativos_apareados()`, `ultimo_precio_utilizable()` — la puerta de entrada: qué precio implícito sirve y qué relativos mensuales salen de él. |
| `indices.py` | `indice_de_nivel()`, `clampear()`, `factor_entre()` — la maquinaria de números índice: clamp, media geométrica ponderada, encadenado por nivel. |
| `transformador.py` | `TransformadorDeflacion` — la cascada, el ancla y la matriz de deflactores. Es lo único que importa el resto del motor. |

## La fórmula, y por qué preserva el descuento

```
monto_real = revenue_c,t × (P_hoy / P_t) = unidades_c,t × P_hoy × (p_c,t / P_t)
                                                                  └─────────┘
                                                                  el descuento
```

`P_t` es el precio promedio del **producto** ese mes y `p_c,t` el que pagó ese cliente. El
promedio del producto es el índice, no el valor a deflactar, así que el cociente entre lo
que pagó el cliente y el promedio —su descuento individual— sobrevive intacto.

La forma prohibida por ADR-002, `unidades × P_hoy`, es literalmente **la misma cuenta con
ese factor forzado a 1**: le borra el descuento a todo el mundo. Y el descuento por cliente
es de las pocas señales fuertes que hay a nivel cliente×producto.

`test_la_re_tasacion_prohibida_borraria_ese_descuento` lo demuestra en dos líneas.

## Todo colapsa a una matriz de deflactores

El objeto real que se construye no es el ancla: es un deflactor por (producto, mes ≤ corte).

```
d_i,t = ancla_i / P̂_i,t          revenue_real = revenue × d_i,t
```

`P̂_i,t` es el precio estimado del producto ese mes: **el propio cuando es utilizable**, y
si no, el precio utilizable más cercano trasladado con el índice de su nivel. Cuando el mes
es utilizable el traslado vale 1, así que es una fórmula sola y no dos ramas. El ancla deja
de ser un objeto aparte: es el caso `d_i,corte = 1`.

## Uso mínimo

```python
from motor.deflacion import TransformadorDeflacion

t = TransformadorDeflacion(catalogo=catalogo).ajustar(hechos_producto, corte)

t.ancla_        # id_producto, precio_prom_hoy, fecha_calculo   → esquema C2
t.indices_      # nivel, id_nivel, anio_mes, indice             → esquema C2
t.deflactor_    # id_producto, anio_mes, deflactor
t.cobertura_    # productos por peldaño que resolvió su ancla

t.transformar(hechos_cliente_producto)   # agrega revenue_real
```

El catálogo y el IPC entran por el **constructor** (son datos de referencia que no varían
con el corte); `ajustar` recibe solo lo que sí varía. Esa separación no es estética:
`verificar_sin_leakage` invoca `calcular(datos, corte)` con exactamente dos argumentos
posicionales, así que **la firma quedó fijada en M1.3**, antes de que este módulo existiera.

Sin catálogo la cascada es `producto → IPC`. El IPC sale de `motor.datos.ipc` si no se
inyecta uno.

## Por qué no se promedian precios (lo que hace no trivial al fallback)

Para deflactar un producto sin ancla propia hay que saber cuánto se movió su categoría. La
tentación es promediar los precios de la categoría, y está mal: una categoría mezcla una
jeringa de $20 con una vacuna de $20.000, así que ese promedio se mueve cada vez que cambia
**qué** se vendió, sin que ningún precio haya cambiado. Con 42% de series intermitentes
(EDA §3), el mix cambia todos los meses.

La salida es la clásica de números índice: promediar **variaciones** en vez de niveles y
encadenarlas. Geométrica y no aritmética porque los relativos son multiplicativos (subir
100% y bajar 50% tiene que volver al punto de partida; la media aritmética de 2,0 y 0,5 da
1,25, o sea 25% de inflación inventada).

`test_el_indice_no_se_mueve_cuando_cambia_el_mix` es el test que justifica el diseño
entero: si esa propiedad no se cumpliera, promediar precios sería más simple y daría lo
mismo.

**La cascada presta el índice, no el nivel.** Un producto sin precio propio no hereda el
*precio* de su categoría —sería disparatado con esa dispersión— sino su *movimiento*:
conserva su último precio propio y le aplica cuánto se movió el vecindario.

## Las constantes se midieron, no se eligieron a ojo

`LIMITE_RELATIVO = 3`, sobre las 125.078 muestras apareadas del extract real:

| clamp | pares recortados | **en el peor mes** |
|---|---|---|
| 1,5 | 1,841% | **31,35%** |
| 2 | 0,613% | 3,05% |
| **3** | **0,325%** | **0,77%** |
| 5 | 0,221% | 0,63% |

Decide la última columna: con 1,5 y con 2 el clamp reacciona a la devaluación de dic-2023
(el IPC hizo +25,47% ese mes), o sea que está recortando inflación real. En 3 el peor mes
cae al nivel del promedio — dejó de ser sensible a eventos macro y solo corta cola.

Que la cola sea basura está verificado: de los 276 pares con `r > 5` o `r < 1/5`, **167
tienen algún precio por debajo de $5** y su revenue mediano es $1.148 contra $53.335 del
par típico — 46 veces más chicos.

`MUESTRA_MINIMA = 3` pares para que un nivel tenga índice en un mes: un "índice" de un solo
producto es el ruido de ese producto. El valor exacto no es crítico (con 2 el IPC atendería
0,22% de las celdas y con 5 el 0,40%); lo que importa es que exista.

**Las dos son constantes a propósito.** Derivarlas de cuantiles de cada corte sería
leakage: el umbral dependería del futuro. Se midieron una vez, offline, sobre todo el
histórico.

## Cuánto usa cada peldaño (extract real, corte 2026-06)

| peldaño | productos | |
|---|---|---|
| producto (ancla propia) | 1.602 | **73,2%** — el EDA §4 esperaba 74,6% |
| categoría | 574 | 26,2% |
| IPC | 12 | 0,5% |
| laboratorio | **1** | 0,0% |

**El peldaño laboratorio lo usa un producto de 2.189.** Es más granular que la categoría
(82 valores contra 12), así que tiene menos muestra justo cuando se lo necesita. No es
inútil —es el peldaño de los productos que caen en categorías diminutas— pero **los datos
reales no lo ejercitan: CP-INF-03 lo cubre con un caso construido a mano o esa rama queda
sin testear**.

## Anti-leakage

Para el corte `t`, el ancla y todos los índices se calculan solo con datos ≤ `t`. El
síntoma de hacerlo mal es un error de backtest sospechosamente bajo — se manifiesta como
una buena noticia, por eso hace falta una red automática y no "prestar atención".

El recorte se hace **una sola vez**, en `ajustar`, y todo lo de abajo es puro. Esa única
línea es lo que sostiene el anti-leakage: sacándola fallan las tres salidas verificadas
(comprobado por mutación). Las otras dos precauciones son las que la red no podría atrapar
sola: no hay ningún promedio global sobre toda la historia —el caso que el docstring de
`leakage.py` señala como el realista— y los umbrales del clamp son constantes medidas
offline, no cuantiles de la corrida.

```bash
pytest -m innegociable     # corré esto antes de tocar cualquier cosa de acá
```

> **Un motivo que estaba mal escrito y se corrigió.** La primera versión documentaba la
> base del encadenado en el primer mes como protección anti-leakage. Es falso con este
> cableado: el transformador recorta antes de encadenar y después solo usa *cocientes*, así
> que una constante por corrida se cancela y `verificar_sin_leakage` **no** detecta el
> cambio de base. La base en el primer mes sigue siendo lo correcto, pero por otra razón:
> mantiene pura a `indice_de_nivel` frente a quien la llame sin recortar antes. Lo detecta
> `test_agregar_meses_futuros_no_cambia_el_indice_de_los_meses_previos`.

## Limitación conocida: el clamp no cubre el deflactor directo

El clamp protege el índice *de nivel*. Cuando el producto **sí** tiene precio propio ese
mes, el deflactor es `ancla / precio_propio` y un precio basura de $0,01 lo hace explotar:
sobre el extract son **93 filas de 7 productos** (0,068%) con deflactor de hasta 1,2
millones.

No mueve nada monetario —aportan 1,3 M sobre 294.733 M de revenue real, o sea 0,000%,
porque su revenue también es ≈ 0— y por eso no se tocó dentro de M2.1: arreglarlo bien
exige elegir **otro** umbral con su propia medición, y no se inventa una constante para
corregir un 0,000%. Pero la columna `deflactor` queda con valores sin sentido, y **eso sí
importa para las features de M2.2**.

Está fijado en `test_un_precio_propio_basura_infla_su_deflactor_pero_no_mueve_el_agregado`,
que asegura las dos mitades del hecho. **Decidir antes de M2.2.**

## La validación que más convence

Deflactando el extract completo, el revenue anual **en pesos del corte** queda entre 36.000
y 40.700 millones de 2019 a 2025, mientras el nominal se multiplica por 29 en el mismo
tramo. Una distribuidora en marcha tiene que verse plana en términos reales, y se ve plana.

Corre en **2,1 s** sobre 137.399 filas y 2.189 productos.

## Nada de esto se persiste

ADR-001: los hechos mensuales son inmutables y nominales, y toda conversión a "precio de
hoy" es un paso de **lectura**. `ancla_` e `indices_` respetan el esquema C2 del
diccionario para que M4 pueda materializarlas cuando corresponda, pero el transformador no
escribe.

## Casos de prueba

| Caso | Dónde |
|---|---|
| CP-INF-01 — dos ventas idénticas de 2019 y 2025 se normalizan a valores comparables | `test_deflacion_transformador.py::TestCpInf01` |
| CP-INF-02 — la deflación preserva el descuento individual | `::TestCpInf02` |
| CP-INF-03 — fallback de ancla por los tres peldaños | `::TestCpInf03Cascada` |
| CP-INF-04 — RFM sobre montos deflactados | **M3.3**, no está acá |
| CP-INF-05 — un precio basura clampeado no dispara el índice de la categoría | `test_deflacion_indices.py::TestClamp` |
| §5.5 #6 — precio implícito no utilizable (NaN y ≤ 0) | `test_deflacion_precios.py`, `::TestPreciosNoUtilizables` |
| Anti-leakage sobre las tres salidas | `test_leakage_deflacion.py` |
