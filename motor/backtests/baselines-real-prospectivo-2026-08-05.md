# Piso de baselines — real-prospectivo (2026-08-05)

Selección por (serie, corte), prospectiva (M1.9) entre 7 candidatos: `SeasonalNaive`, `WindowAverage`, `AutoETS`, `AutoTheta`, `AutoARIMA`, `CrostonSBA`, `TSB`.

- **Productos:** 2128 · **cortes:** 18 · **horizonte:** 12 · **n_jobs:** 4
- **Tiempo de backtest:** 0.0 min
- **Pares (serie, corte) con ganador:** 38014

> ⚠️ **La cobertura NO es 1,0: baja hasta 0.9104 a h=12 (grano producto).** Son filas con valor real y sin predicción, y **bajan el WAPE de la tabla porque omiten series, no porque el método acierte más**. Antes de usar esta tabla como piso hay que explicar de dónde salen esas filas — `backtests/README.md` §Qué tiene que traer cada tabla, condición 4. **Con selección prospectiva la causa es única:** la cascada recorre los 7 candidatos antes de dejar una celda vacía, así que lo que queda sin cubrir es lo que **ningún** candidato pudo predecir — arranque en frío, productos cuya primera venta es posterior al corte. La tabla `origen_de_la_prediccion` trae el conteo.

> **Selección prospectiva (M1.9 / ADR-016): este piso es el que se compara contra el modelo global.** El ganador de cada serie se reelige en cada corte usando únicamente el error **ya observado** a esa altura (mes objetivo ≤ corte), y si el elegido no puede cubrir una celda se baja al siguiente candidato disponible. Es lo que un pipeline productivo puede hacer, y por eso es la única tabla comparable fila a fila contra un modelo medido prospectivamente.

> **Su WAPE es PEOR que el del piso retrospectivo, y esa es la idea: aquel estaba inflado.** Aquel elegía el método de cada serie con información posterior a las filas donde se lo medía, y además perdía cobertura por eso mismo (§5.6.1 punto 5). Las filas que la cascada recupera son series jóvenes —las más difíciles—, así que recuperarlas **empeora** el WAPE. No es una regresión del método.

## Corrida

| id | fecha_ejecucion | n_cortes | horizonte_max | columnas_id | columna_objetivo | densificado | primer_corte | ultimo_corte | datos_filas | datos_series | datos_primer_mes | datos_ultimo_mes | datos_suma_objetivo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a79a9b23676b | 2026-08-05 | 18 | 12 | ('id_producto',) | unidades | True | 2024-11-01 | 2026-04-01 | 157431 | 2128 | 2018-07-01 | 2026-05-01 | 31122141.0000 |

## Modelo ganador por cuadrante — cuenta **pares (serie, corte)**, no series (selección prospectiva, M1.9)

| modelo_ganador | erratica | intermitente | lumpy | suave | total |
|---|---|---|---|---|---|
| SeasonalNaive | 1183 | 5195 | 975 | 6296 | 13649 |
| CrostonSBA | 645 | 373 | 296 | 4634 | 5948 |
| WindowAverage | 538 | 1900 | 767 | 1830 | 5035 |
| AutoARIMA | 710 | 681 | 694 | 1944 | 4029 |
| AutoTheta | 417 | 200 | 176 | 2705 | 3498 |
| AutoETS | 471 | 182 | 141 | 2557 | 3351 |
| TSB | 338 | 170 | 135 | 1861 | 2504 |

## Por nivel de agregación y horizonte

| nivel | horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|---|
| producto | 1 | 0.3305 | 0.0099 | 36003 | 0.9927 |
| producto | 3 | 0.3767 | 0.0266 | 32235 | 0.9786 |
| producto | 6 | 0.4001 | 0.0061 | 26513 | 0.9546 |
| producto | 12 | 0.3699 | 0.0351 | 14606 | 0.9104 |
| categoria | 1 | 0.1509 | 0.0077 | 216 | 1.0000 |
| categoria | 3 | 0.1701 | 0.0203 | 192 | 1.0000 |
| categoria | 6 | 0.2063 | -0.0100 | 156 | 1.0000 |
| categoria | 12 | 0.1787 | -0.0090 | 84 | 1.0000 |
| total | 1 | 0.1205 | 0.0077 | 18 | 1.0000 |
| total | 3 | 0.1390 | 0.0203 | 16 | 1.0000 |
| total | 6 | 0.1575 | -0.0100 | 13 | 1.0000 |
| total | 12 | 0.0867 | -0.0090 | 7 | 1.0000 |

## Por horizonte (grano producto)

| horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|
| 1 | 0.3305 | 0.0099 | 36003 | 0.9927 |
| 3 | 0.3767 | 0.0266 | 32235 | 0.9786 |
| 6 | 0.4001 | 0.0061 | 26513 | 0.9546 |
| 12 | 0.3699 | 0.0351 | 14606 | 0.9104 |

## Por categoría y horizonte

| categoria | horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|---|
| ACCESORIO | 1 | 1.0129 | -0.1325 | 342 | 1.0000 |
| ACCESORIO | 3 | 1.0146 | -0.2401 | 304 | 1.0000 |
| ACCESORIO | 6 | 0.9931 | -0.4952 | 247 | 1.0000 |
| ACCESORIO | 12 | 1.0600 | -0.7764 | 133 | 1.0000 |
| ALIMENTO | 1 | 0.3143 | 0.0284 | 828 | 1.0000 |
| ALIMENTO | 3 | 0.2694 | -0.0304 | 736 | 1.0000 |
| ALIMENTO | 6 | 0.3035 | -0.0574 | 598 | 1.0000 |
| ALIMENTO | 12 | 0.3144 | -0.1152 | 322 | 1.0000 |
| ANTIARTROSICO | 1 | 0.2467 | -0.0603 | 774 | 1.0000 |
| ANTIARTROSICO | 3 | 0.2607 | -0.0895 | 688 | 1.0000 |
| ANTIARTROSICO | 6 | 0.2663 | -0.1337 | 559 | 1.0000 |
| ANTIARTROSICO | 12 | 0.3039 | -0.1995 | 301 | 1.0000 |
| ANTIPARASITARIO EXTERNO | 1 | 0.3742 | 0.0525 | 6284 | 0.9946 |
| ANTIPARASITARIO EXTERNO | 3 | 0.4430 | 0.1032 | 5617 | 0.9849 |
| ANTIPARASITARIO EXTERNO | 6 | 0.4708 | 0.0950 | 4606 | 0.9674 |
| ANTIPARASITARIO EXTERNO | 12 | 0.3891 | 0.2087 | 2508 | 0.9358 |
| ANTIPARASITARIO INTERNO | 1 | 0.2521 | 0.0297 | 2448 | 1.0000 |
| ANTIPARASITARIO INTERNO | 3 | 0.2452 | 0.0303 | 2176 | 1.0000 |
| ANTIPARASITARIO INTERNO | 6 | 0.2849 | 0.0441 | 1768 | 1.0000 |
| ANTIPARASITARIO INTERNO | 12 | 0.2882 | 0.0430 | 952 | 1.0000 |
| BIOLOGICO | 1 | 0.3520 | -0.0020 | 778 | 0.9987 |
| BIOLOGICO | 3 | 0.4336 | -0.0136 | 692 | 0.9957 |
| BIOLOGICO | 6 | 0.4585 | -0.0763 | 563 | 0.9929 |
| BIOLOGICO | 12 | 0.5350 | -0.1006 | 305 | 0.9869 |
| CARDIOLOGICO | 1 | 0.1767 | -0.0259 | 1134 | 1.0000 |
| CARDIOLOGICO | 3 | 0.1950 | -0.0325 | 1008 | 1.0000 |
| CARDIOLOGICO | 6 | 0.2077 | -0.0633 | 819 | 1.0000 |
| CARDIOLOGICO | 12 | 0.2292 | -0.1214 | 441 | 1.0000 |
| CLINICO | 1 | 0.2418 | -0.0392 | 13070 | 0.9995 |
| CLINICO | 3 | 0.2572 | -0.0540 | 11626 | 0.9985 |
| CLINICO | 6 | 0.2735 | -0.0735 | 9452 | 0.9970 |
| CLINICO | 12 | 0.2822 | -0.1115 | 5096 | 0.9939 |
| DESCARTABLES | 1 | 0.3976 | 0.0762 | 936 | 1.0000 |
| DESCARTABLES | 3 | 0.3748 | 0.0386 | 832 | 1.0000 |
| DESCARTABLES | 6 | 0.4226 | 0.0373 | 676 | 1.0000 |
| DESCARTABLES | 12 | 0.5163 | 0.0511 | 364 | 1.0000 |
| HIGIENE Y BELLEZA | 1 | 0.2451 | -0.0203 | 3888 | 1.0000 |
| HIGIENE Y BELLEZA | 3 | 0.2596 | -0.0176 | 3456 | 1.0000 |
| HIGIENE Y BELLEZA | 6 | 0.2902 | -0.0248 | 2808 | 1.0000 |
| HIGIENE Y BELLEZA | 12 | 0.2644 | -0.0795 | 1512 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 1 | 0.2445 | -0.0627 | 18 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 3 | 0.3000 | -0.1056 | 16 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 6 | 0.3500 | -0.1712 | 13 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 12 | 0.3806 | -0.3043 | 7 | 1.0000 |
| SIN CATEGORIA | 1 | 0.5239 | -0.1901 | 5503 | 0.9598 |
| SIN CATEGORIA | 3 | 0.5283 | -0.1889 | 5084 | 0.8849 |
| SIN CATEGORIA | 6 | 0.4917 | -0.2417 | 4404 | 0.7677 |
| SIN CATEGORIA | 12 | 0.3785 | -0.2360 | 2665 | 0.5824 |

## Por cuadrante de intermitencia y horizonte

| cuadrante | horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|---|
| erratica | 1 | 0.4748 | 0.0390 | 4221 | 0.9955 |
| erratica | 3 | 0.5764 | 0.0571 | 3772 | 0.9873 |
| erratica | 6 | 0.6400 | -0.0411 | 3087 | 0.9741 |
| erratica | 12 | 0.5535 | -0.0322 | 1673 | 0.9474 |
| intermitente | 1 | 0.9616 | 0.2107 | 7867 | 0.9865 |
| intermitente | 3 | 0.9381 | 0.1838 | 7093 | 0.9578 |
| intermitente | 6 | 1.1460 | 0.3370 | 5901 | 0.9110 |
| intermitente | 12 | 1.2254 | 0.3646 | 3333 | 0.8266 |
| lumpy | 1 | 1.2052 | 0.3596 | 3142 | 0.9981 |
| lumpy | 3 | 1.5863 | 0.6532 | 2798 | 0.9943 |
| lumpy | 6 | 1.9245 | 0.7809 | 2281 | 0.9868 |
| lumpy | 12 | 2.5491 | 1.3620 | 1237 | 0.9741 |
| suave | 1 | 0.3013 | 0.0030 | 20773 | 0.9937 |
| suave | 3 | 0.3393 | 0.0190 | 18572 | 0.9823 |
| suave | 6 | 0.3547 | 0.0095 | 15244 | 0.9626 |
| suave | 12 | 0.3310 | 0.0413 | 8363 | 0.9269 |

## MASE por horizonte

| horizonte | mase_medio | mase_mediana | n |
|---|---|---|---|
| 1 | 0.8454 | 0.5867 | 35741 |
| 3 | 0.8564 | 0.6088 | 31544 |
| 6 | 0.8660 | 0.6321 | 25308 |
| 12 | 0.8972 | 0.6580 | 13297 |

## Origen de cada predicción (ganador / cascada / nadie)

| origen | filas | % |
|---|---|---|
| ganador del corte | 284574 | 93.2100 |
| sin predicción (ningún candidato) | 12700 | 4.1600 |
| cascada | 8035 | 2.6300 |

## Cambios de ganador por serie a lo largo de los cortes

| cambios | n_series | % |
|---|---|---|
| 0 | 335 | 15.7000 |
| 1 | 165 | 7.8000 |
| 2 | 66 | 3.1000 |
| 3 | 87 | 4.1000 |
| 4 | 112 | 5.3000 |
| 5 | 174 | 8.2000 |
| 6 | 174 | 8.2000 |
| 7 | 192 | 9.0000 |
| 8 | 174 | 8.2000 |
| 9 | 195 | 9.2000 |
| 10 | 142 | 6.7000 |
| 11 | 136 | 6.4000 |
| 12 | 89 | 4.2000 |
| 13 | 48 | 2.3000 |
| 14 | 30 | 1.4000 |
| 15 | 8 | 0.4000 |
| 16 | 1 | 0.0000 |
