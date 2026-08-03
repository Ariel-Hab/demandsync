# Piso de baselines — real (2026-08-03)

Selección por serie (M1.7) entre 7 candidatos: `SeasonalNaive`, `WindowAverage`, `AutoETS`, `AutoTheta`, `AutoARIMA`, `CrostonSBA`, `TSB`.

- **Productos:** 2128 · **cortes:** 18 · **horizonte:** 12 · **n_jobs:** 4
- **Tiempo de backtest:** 294.3 min
- **Series con ganador asignado:** 2106

> ⚠️ **La cobertura NO es 1,0 a grano producto: baja de 0,9920 (h=1) a 0,8880 (h=12).**
> Son filas con valor real y **sin predicción del modelo seleccionado**, así que el WAPE de
> esta tabla está mejorado por omitir series, no por acertar más. Condición 4 de
> `backtests/README.md`; la causa se diagnosticó antes de congelar y son **dos**, no una.
>
> **Son 18.355 filas — 6,01% del reporte de 305.309 — y se explican al 100%, en dos
> componentes con consecuencias distintas.**
>
> **(1) Altas de catálogo — 12.700 filas (69,19%), 262 productos.** Su primera venta es
> **posterior al corte**: la serie no existía todavía y **ningún** candidato predijo
> (historia 0). Un baseline univariado no puede predecir una serie que no existía; el arnés
> registra el real (densificado, ADR-010) y ninguna predicción, y la cobertura lo hace
> visible en vez de taparlo. **No es un defecto de la corrida.** De acá salen también las
> **22 series sin ganador** (2.106 de 2.128): las 22 tienen su primera venta en 2026-05,
> posterior al último corte, así que ningún candidato llegó a predecirlas nunca. Y acá está
> el `SIN CATEGORIA` a **0,4953** de cobertura a h=12: **221 de esos 262 productos (84,4%)
> no tienen categoría asignada todavía**. Leer esa fila como "la categoría se predice mal"
> sería un error — la mitad de sus filas no se predijo en absoluto.
>
> **(2) Horizonte truncado por historia corta — 5.655 filas (30,81%), 241 productos.** Acá
> la serie **sí existía** al corte, con 1 a 11 meses de historia (mediana 2), y **otros 5 o
> 6 candidatos sí predijeron**: el que no llegó fue el ganador retrospectivo de esa serie —
> `SeasonalNaive` (5.355 filas) o `WindowAverage` (300). El mecanismo es exacto y está
> verificado: **el naive estacional solo proyecta tantos meses como historia tiene**, así
> que en el **100%** de sus 5.355 filas se cumple `horizonte > meses de historia`. Las 38
> filas de `WindowAverage` que no siguen esa regla son series más cortas que su propia
> ventana, que no devuelve nada ni a h=1. Por eso la cobertura **cae con el horizonte**:
> este componente aporta 25 filas a h=1 y 682 a h=6.
>
> **La distinción es la que importa para M2.5.** El componente (1) es un hueco genuino de
> arranque en frío que **ningún baseline puede llenar** — es donde el modelo global podría
> ganar con features de categoría/laboratorio. El componente (2) es **reparable dentro de
> los propios baselines**: un pipeline prospectivo que en cada corte eligiera un modelo
> capaz de cubrir el horizonte no tendría esa brecha. O sea que parte de la cobertura que
> le falta a este piso es un artefacto de la selección retrospectiva (ver la nota de más
> abajo), no un límite de los baselines.
>
> **Cuánto lo favorece la omisión, medido:** rellenando con `WindowAverage` las filas del
> componente (2) donde está disponible (2.613 de 5.655; 0,71% de las unidades), el WAPE
> **empeora** a h=6 de 0,3114 → **0,3174** (+0,0060) y a h=12 de 0,3034 → **0,3070**
> (+0,0036); h=1 y h=3 no se mueven porque ahí casi no hay filas del componente (2). Es una
> cota ilustrativa, no el WAPE de un pipeline prospectivo. **M2.5 tiene que comparar a igual
> cobertura**, o la comparación no es justa en ninguna de las dos direcciones.
>
> Esta nota se agregó a mano tras el diagnóstico; el script solo emite la advertencia
> genérica (`_nota_de_cobertura`). **Corrige a la tabla del 2026-07-31**, que declaraba
> "100% altas de catálogo, cero filas sin explicar": ese conteo tomó solo las filas donde
> **ningún** candidato predijo (13.889) y no las que le faltan al **modelo seleccionado**
> (20.174), que es lo que mide la columna `cobertura`. El componente (2) ya estaba ahí
> —6.285 filas, 31,15%— y pasó inadvertido. La redacción de la advertencia genérica
> ("sin predicción de ningún candidato") empujaba a ese conteo y se corrigió. Ver
> `roadmap-motor.md` §5.6.1.

> ⚠️ **El gate de sesgo de M2 (±5% a nivel total) este piso NO lo cumple en horizonte
> largo:** −3,4% (h=1) y −2,6% (h=3) entran, pero **−5,2% (h=6) y −6,0% (h=12) quedan
> afuera**. Los baselines sub-pronostican sistemáticamente a horizonte largo, así que el
> modelo global de M2 tiene que **corregir** ese sesgo, no solo empatar el WAPE. El −1,4%
> que reportó la corrida del 2026-07-31 no era mejor: salía de evaluar 1 de los 7 pares de
> h=12 contra un mes cargado al 32%, lo que achica `real` y corre `pred − real` hacia
> arriba. Con el relleno del componente (2) el h=6 entra al ±5% (−4,6%) pero el h=12 sigue
> afuera (−5,3%): el incumplimiento a h=12 no es un efecto de la cobertura.

> **Este piso reemplaza a `baselines-real-2026-07-31.md`** (corrida `f7af767ca7e6`), que
> midió sobre un universo con obsequios y con 2026-06 al 32% de carga (ADR-012, M1.8b).
> **Las dos tablas no son comparables número a número:** cambian a la vez el universo
> (2.189 → 2.128 productos) y la ventana de cortes (2024-12..2026-05 → 2024-11..2026-04,
> porque el extract ya no incluye el mes incompleto). La anterior queda como registro
> histórico, no como referencia.

> **La selección por serie es retrospectiva, así que este piso es optimista.** El ganador de cada serie se eligió con el MASE de todos los cortes y se aplicó también a los más viejos, es decir con información posterior a las filas donde se mide. Es lo que especifica `plan-diseno.md` §M1 y la convención para fijar una referencia fuerte, pero **no es un procedimiento prospectivo** y por lo tanto este piso está más alto que el de un pipeline que eligiera el método en cada corte con datos ≤ corte. Antes del champion/challenger de M2.5 hay que nivelar la comparación — ver `roadmap-motor.md` §12.5.

> Las predicciones individuales **sí** son limpias: el arnés garantiza historia ≤ corte en cada una (M1.3). Lo retrospectivo es la elección de *qué modelo* mirar, no lo que cada modelo vio.

## Corrida

| id | fecha_ejecucion | n_cortes | horizonte_max | columnas_id | columna_objetivo | densificado | primer_corte | ultimo_corte | datos_filas | datos_series | datos_primer_mes | datos_ultimo_mes | datos_suma_objetivo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a79a9b23676b | 2026-08-03 | 18 | 12 | ('id_producto',) | unidades | True | 2024-11-01 | 2026-04-01 | 157431 | 2128 | 2018-07-01 | 2026-05-01 | 31122141.0000 |

## Modelo ganador por cuadrante (selección por serie, M1.7)

| modelo_ganador | erratica | intermitente | lumpy | suave | total |
|---|---|---|---|---|---|
| SeasonalNaive | 46 | 218 | 19 | 198 | 481 |
| CrostonSBA | 50 | 20 | 20 | 315 | 405 |
| AutoARIMA | 43 | 70 | 59 | 123 | 295 |
| WindowAverage | 29 | 137 | 53 | 62 | 281 |
| AutoTheta | 29 | 20 | 12 | 208 | 269 |
| AutoETS | 23 | 14 | 6 | 171 | 214 |
| TSB | 19 | 9 | 8 | 125 | 161 |

## Por nivel de agregación y horizonte

| nivel | horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|---|
| producto | 1 | 0.2870 | -0.0314 | 36003 | 0.9920 |
| producto | 3 | 0.2954 | -0.0143 | 32235 | 0.9653 |
| producto | 6 | 0.3114 | -0.0190 | 26513 | 0.9288 |
| producto | 12 | 0.3034 | 0.0055 | 14606 | 0.8880 |
| categoria | 1 | 0.1283 | -0.0338 | 216 | 1.0000 |
| categoria | 3 | 0.1321 | -0.0260 | 192 | 1.0000 |
| categoria | 6 | 0.1691 | -0.0517 | 156 | 1.0000 |
| categoria | 12 | 0.1654 | -0.0597 | 84 | 1.0000 |
| total | 1 | 0.1029 | -0.0338 | 18 | 1.0000 |
| total | 3 | 0.1005 | -0.0260 | 16 | 1.0000 |
| total | 6 | 0.1191 | -0.0517 | 13 | 1.0000 |
| total | 12 | 0.0954 | -0.0597 | 7 | 1.0000 |

## Por horizonte (grano producto)

| horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|
| 1 | 0.2870 | -0.0314 | 36003 | 0.9920 |
| 3 | 0.2954 | -0.0143 | 32235 | 0.9653 |
| 6 | 0.3114 | -0.0190 | 26513 | 0.9288 |
| 12 | 0.3034 | 0.0055 | 14606 | 0.8880 |

## Por categoría y horizonte

| categoria | horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|---|
| ACCESORIO | 1 | 0.8949 | -0.3086 | 342 | 1.0000 |
| ACCESORIO | 3 | 0.8939 | -0.3433 | 304 | 1.0000 |
| ACCESORIO | 6 | 0.7858 | -0.4477 | 247 | 1.0000 |
| ACCESORIO | 12 | 0.7700 | -0.4975 | 133 | 1.0000 |
| ALIMENTO | 1 | 0.2437 | 0.0094 | 828 | 1.0000 |
| ALIMENTO | 3 | 0.2341 | -0.0180 | 736 | 1.0000 |
| ALIMENTO | 6 | 0.2389 | -0.0512 | 598 | 1.0000 |
| ALIMENTO | 12 | 0.2817 | -0.0340 | 322 | 1.0000 |
| ANTIARTROSICO | 1 | 0.2206 | -0.0765 | 774 | 1.0000 |
| ANTIARTROSICO | 3 | 0.2320 | -0.1035 | 688 | 1.0000 |
| ANTIARTROSICO | 6 | 0.2537 | -0.1584 | 559 | 1.0000 |
| ANTIARTROSICO | 12 | 0.2752 | -0.1938 | 301 | 1.0000 |
| ANTIPARASITARIO EXTERNO | 1 | 0.3269 | -0.0270 | 6284 | 0.9940 |
| ANTIPARASITARIO EXTERNO | 3 | 0.3305 | -0.0025 | 5617 | 0.9731 |
| ANTIPARASITARIO EXTERNO | 6 | 0.3523 | 0.0241 | 4606 | 0.9392 |
| ANTIPARASITARIO EXTERNO | 12 | 0.3088 | 0.1181 | 2508 | 0.9043 |
| ANTIPARASITARIO INTERNO | 1 | 0.2084 | -0.0005 | 2448 | 1.0000 |
| ANTIPARASITARIO INTERNO | 3 | 0.2135 | 0.0191 | 2176 | 1.0000 |
| ANTIPARASITARIO INTERNO | 6 | 0.2266 | 0.0257 | 1768 | 1.0000 |
| ANTIPARASITARIO INTERNO | 12 | 0.2385 | 0.0349 | 952 | 1.0000 |
| BIOLOGICO | 1 | 0.3109 | 0.0024 | 778 | 0.9987 |
| BIOLOGICO | 3 | 0.3626 | 0.0403 | 692 | 0.9913 |
| BIOLOGICO | 6 | 0.3833 | -0.0090 | 563 | 0.9840 |
| BIOLOGICO | 12 | 0.4705 | -0.0495 | 305 | 0.9639 |
| CARDIOLOGICO | 1 | 0.1571 | -0.0327 | 1134 | 1.0000 |
| CARDIOLOGICO | 3 | 0.1616 | -0.0366 | 1008 | 1.0000 |
| CARDIOLOGICO | 6 | 0.1716 | -0.0626 | 819 | 1.0000 |
| CARDIOLOGICO | 12 | 0.1859 | -0.0913 | 441 | 1.0000 |
| CLINICO | 1 | 0.2090 | -0.0461 | 13070 | 0.9994 |
| CLINICO | 3 | 0.2153 | -0.0530 | 11626 | 0.9978 |
| CLINICO | 6 | 0.2292 | -0.0739 | 9452 | 0.9956 |
| CLINICO | 12 | 0.2353 | -0.1108 | 5096 | 0.9922 |
| DESCARTABLES | 1 | 0.3190 | 0.0096 | 936 | 1.0000 |
| DESCARTABLES | 3 | 0.3201 | 0.0108 | 832 | 1.0000 |
| DESCARTABLES | 6 | 0.3500 | 0.0149 | 676 | 1.0000 |
| DESCARTABLES | 12 | 0.4169 | 0.0499 | 364 | 1.0000 |
| HIGIENE Y BELLEZA | 1 | 0.2085 | -0.0179 | 3888 | 1.0000 |
| HIGIENE Y BELLEZA | 3 | 0.2161 | -0.0243 | 3456 | 1.0000 |
| HIGIENE Y BELLEZA | 6 | 0.2334 | -0.0386 | 2808 | 1.0000 |
| HIGIENE Y BELLEZA | 12 | 0.2221 | -0.0687 | 1512 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 1 | 0.2413 | -0.0033 | 18 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 3 | 0.2545 | -0.0321 | 16 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 6 | 0.2583 | -0.0748 | 13 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 12 | 0.3055 | -0.1197 | 7 | 1.0000 |
| SIN CATEGORIA | 1 | 0.4404 | -0.1986 | 5503 | 0.9564 |
| SIN CATEGORIA | 3 | 0.3946 | -0.1361 | 5084 | 0.8161 |
| SIN CATEGORIA | 6 | 0.3323 | -0.2202 | 4404 | 0.6467 |
| SIN CATEGORIA | 12 | 0.2797 | -0.2011 | 2665 | 0.4953 |

## Por cuadrante de intermitencia y horizonte

| cuadrante | horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|---|
| erratica | 1 | 0.4313 | -0.0607 | 4221 | 0.9950 |
| erratica | 3 | 0.4677 | -0.0528 | 3772 | 0.9783 |
| erratica | 6 | 0.4866 | -0.0894 | 3087 | 0.9495 |
| erratica | 12 | 0.4659 | -0.0766 | 1673 | 0.9187 |
| intermitente | 1 | 0.7225 | 0.0193 | 7867 | 0.9856 |
| intermitente | 3 | 0.6963 | 0.0888 | 7093 | 0.9296 |
| intermitente | 6 | 0.7601 | 0.1412 | 5901 | 0.8553 |
| intermitente | 12 | 1.0417 | 0.2899 | 3333 | 0.7723 |
| lumpy | 1 | 0.8111 | -0.0987 | 3142 | 0.9962 |
| lumpy | 3 | 0.9347 | -0.0625 | 2798 | 0.9893 |
| lumpy | 6 | 1.1466 | -0.0028 | 2281 | 0.9798 |
| lumpy | 12 | 1.4369 | 0.1801 | 1237 | 0.9588 |
| suave | 1 | 0.2602 | -0.0269 | 20773 | 0.9932 |
| suave | 3 | 0.2650 | -0.0089 | 18572 | 0.9727 |
| suave | 6 | 0.2796 | -0.0090 | 15244 | 0.9455 |
| suave | 12 | 0.2710 | 0.0171 | 8363 | 0.9175 |

## MASE por horizonte

| horizonte | mase_medio | mase_mediana | n |
|---|---|---|---|
| 1 | 0.6847 | 0.4720 | 35741 |
| 3 | 0.7019 | 0.4933 | 31544 |
| 6 | 0.7132 | 0.5146 | 25308 |
| 12 | 0.7438 | 0.5306 | 13297 |
