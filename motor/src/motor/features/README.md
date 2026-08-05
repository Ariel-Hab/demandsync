# `motor.features` — features del modelo global (M2.2)

Lo que M2.3 le da de comer a LightGBM. El **gate de salida de la unidad** es que
`construir_features` pase la red anti-leakage de M1.3 (`pytest -m innegociable`).

```python
from motor.features import construir_features, LAGS, LAG_TRANSFORMS, STATIC_FEATURES

features = construir_features(historia, corte, catalogo=catalogo)
```

## Dos mitades, con dueños distintos

| | Quién lo hace | Qué |
|---|---|---|
| `especificacion.py` | lo **ejecuta `mlforecast`** en M2.3 | lags (1,2,3,6,12), medias móviles (3,6,12), mes del año |
| `construccion.py` + `precio.py` | lo hace **este paquete** | lo derivado de la deflación de ADR-002, más los atributos de catálogo |

`mlforecast` ya arma lags y ventanas móviles sin leakage y M2.3 lo va a usar igual para el
multi-horizonte directo, así que reimplementarlo acá sería mantener dos copias del mismo
criterio. M2.2 se queda con la **especificación**; lo único que necesita red propia es lo
que `mlforecast` no sabe hacer.

## El precio: por qué no es "el precio deflactado"

`plan-diseno.md` §M2 pedía *"precio real deflactado y su variación"*. **Tomado literal a
grano producto es una columna constante y otra de ceros**, y es por construcción, no por un
problema de datos:

```
d = ancla / P̂        y cuando el mes tiene precio propio utilizable, P̂ = precio_prom
precio_prom × d  =  precio_prom × (ancla / precio_prom)  =  ancla
```

Medido sobre `C:/dfv-extract-v2` (corte 2025-05): se cumple en el **99,15%** de las filas
con precio propio utilizable y el CV intra-producto da **0,0000**, contra 1,2809 del precio
nominal. Lo mismo con los montos: `revenue_real = unidades × ancla` (99,13%), o sea el
target reescalado por una constante por serie. **Ninguna de las dos entra como feature** —
ver **ADR-013**.

Lo que sí tiene señal es el precio del producto llevado a pesos del corte **con el índice de
su nivel** en vez del suyo propio:

```
precio_rel_nivel_t = precio_prom_t × I_nivel(corte)/I_nivel(t) / ancla
```

**Es una feature de forma, no de nivel.** El nivel arrastra una constante por producto
(el ancla es el promedio ponderado de 3 meses, no el precio del corte: ≈1,05 en una serie
que crece al 5% mensual). Lo exacto es la forma de la serie:

| el producto… | su serie queda… |
|---|---|
| se movió igual que su categoría | **plana**, variación exactamente 0 |
| se encareció contra su categoría | **creciente** — en el pasado estaba relativamente más barato que hoy |
| se abarató contra su categoría | decreciente |

El signo se lee al revés de lo que sugiere la intuición, y por eso está fijado en
`test_un_producto_que_se_mueve_como_su_categoria_da_una_serie_plana`.

**El contraste es contra categoría y laboratorio, nunca contra el IPC.** Mismo criterio que
`LIMITE_DESVIO_NIVEL` (`deflacion/README.md`): los niveles del cliente son un espejo del
propio producto, el IPC es un índice macro que no tiene por qué seguir precios veterinarios.

## Forma de la salida

Panel a grano (`id_producto`, `anio_mes ≤ corte`): **una fila por mes visible, no una foto
del corte**. Cada fila es un **origen de pronóstico válido** — M2.3 usa las de
`anio_mes == corte` para predecir y las anteriores como orígenes de entrenamiento.

Eso es lo que permite que el precio aporte señal temporal sin necesitar valores futuros: el
precio de `corte+h` no se conoce, pero el del origen sí.

| columna | tipo |
|---|---|
| `precio_ancla` | estática por corte — la **escala** de precio (jeringa de $20 vs vacuna de $20.000) |
| `precio_rel_nivel` | temporal |
| `var_precio_rel_3m`, `var_precio_rel_12m` | temporal |
| `categoria`, `laboratorio` | categóricas estáticas |

El esquema es **estable**: sin catálogo las columnas están igual, en `NaN`. Si dependiera
del insumo, M2.3 tendría dos configuraciones de features y el champion/challenger de M2.5
compararía dos cosas distintas.

## Cobertura medida (extract real, 2.128 productos)

| corte | filas | `precio_rel_nivel` | `var_3m` | `var_12m` | `precio_ancla` |
|---|---|---|---|---|---|
| 2024-11 | 107.294 | 0,9567 | 0,8674 | 0,7379 | 0,9996 |
| 2025-05 | 116.492 | 0,9569 | 0,8702 | 0,7461 | 0,9995 |
| 2026-04 | 133.833 | 0,9563 | 0,8724 | 0,7578 | 1,0000 |

Corre en **2,5 s** sobre 116k filas. Tres cosas para leer bien esa tabla:

- **Sobre las filas con precio propio utilizable la cobertura es 0,9899.** El resto del
  hueco son los meses de neto cero (`unidades == 0`, 3,53% real), donde no hay precio
  observado. No se imputa: inventaría un precio que nadie vio.
- **`var_12m` pierde un cuarto del panel**, y es esperable — pide el mismo mes del año
  anterior, que las series jóvenes y las intermitentes no tienen.
- **El primer mes de cada panel nunca tiene `precio_rel_nivel`**: el índice de un nivel se
  construye con pares de meses consecutivos, así que el primero no tiene relativo. Es
  propiedad, no defecto, y está fijada en un test.

Las filas sin valor quedan en `NaN` y **no se descartan**. LightGBM los maneja
nativamente, y la alternativa —imputar— esconde la cobertura, que es justamente lo que el
piso de M1.8 enseñó a no hacer. `cobertura_de_features(features)` devuelve esta tabla.

## Lo que NO está, y por qué

| | Motivo |
|---|---|
| `revenue_real` y cualquier monto deflactado | Es `unidades × ancla`: el target reescalado (ADR-013) |
| `mismo_mes_año_anterior` | A grano mensual **es** `lag 12`, que ya está en `LAGS` |
| `CLIENTE_FEATURE` | **Diferida a M3.2**, que es el hito a grano cliente×producto. El extract real no tiene cliente×producto, así que acá solo se podría ejercitar en sintético — y M2.5 terminaría comparando una corrida real con una feature menos que la sintética |
| El cuadrante de intermitencia | No está en la especificación de M2.2. Si M2.3 lo quiere, entra como unidad propia con su gate |

## Trampas

- **No densifica.** La densificación de ADR-010 es del arnés, que ya la hace antes de
  invocar al predictor. Hacerla también acá dejaría el criterio de calendario en dos lugares.
- **Un transformador ajustado a otro corte corta la corrida.** Es leakage que la red de M1.3
  **no vería**, porque llegaría contaminado desde afuera. Pasá `transformador=None` o
  ajustalo al mismo corte.
- **Las variaciones se alinean por calendario, no por filas.** En una serie intermitente,
  tres filas atrás pueden ser ocho meses, y `shift(3)` mediría "la antepenúltima vez que
  vendió" con cara de variación trimestral.
