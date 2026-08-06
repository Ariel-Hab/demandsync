# Calibración de intervalos del modelo global — real (2026-08-06)

Modelo global LightGBM (`GlobalLGBM`) con regresión cuantílica: GlobalLGBM_P10, GlobalLGBM_P50, GlobalLGBM_P90. Configuración `precio+crudo`, la que eligió la ablación de M2.3.

- **Productos:** 2128 de 2128 · **cortes:** 18 · **horizonte:** 12 · **0.0 min**
- **Cobertura nominal del P10–P90:** 0.80. `desvio_vs_nominal` es la empírica menos ese valor, **con signo**: negativo es sub-cobertura (el intervalo promete menos riesgo del que hay) y positivo es un intervalo más ancho de lo necesario. No son el mismo error.
- **Cobertura esperada por longitud de serie:** 0.8393 — cota superior de la cobertura del global (`mlforecast` descarta las series sin lags completos), así que una `cobertura` baja en la tabla no es necesariamente del modelo.
- **Por qué la `cobertura` no es 1,0** (regla 4 de `backtests/README.md`): son las **altas de catálogo** de `roadmap-motor.md` §5.6.1 — productos cuya primera venta es posterior al corte, que ni los baselines ni el global pueden predecir porque no existen al momento de entrenar. Son **las mismas filas** que en el piso prospectivo y en las ablaciones de M2.3 (§6.5 punto 4 lo verificó fila a fila), así que las tres tablas se comparan a igual cobertura.

> **El intervalo se mide a grano producto, que es donde se predice.** No hay cobertura por categoría ni total: **la suma de cuantiles no es el cuantil de la suma** — sumar los P90 de todo el catálogo supone que a todos los productos les va bien el mismo mes y da un rango absurdamente ancho. Un intervalo agregado hay que predecirlo a esa altura de la jerarquía (M3.1). Los cortes por cuadrante y por categoría de abajo son desagregados del **mismo** grano producto, que es otra cosa.

> **El intervalo se evalúa cerrado** (`P10 <= real <= P90`). Con 42% de series intermitentes y el panel densificado a ceros (ADR-010), la fila más frecuente es `real == 0` con `P10 == 0`, y ese es un acierto: el modelo dijo que bien podía no venderse nada.

## Corrida

| id | fecha_ejecucion | n_cortes | horizonte_max | columnas_id | columna_objetivo | densificado | primer_corte | ultimo_corte | datos_filas | datos_series | datos_primer_mes | datos_ultimo_mes | datos_suma_objetivo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a79a9b23676b | 2026-08-06 | 18 | 12 | ('id_producto',) | unidades | True | 2024-11-01 | 2026-04-01 | 157431 | 2128 | 2018-07-01 | 2026-05-01 | 31122141.0000 |

## Por nivel de agregación y horizonte

| nivel | horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|---|
| producto | 1 | 0.2953 | -0.0040 | 36003 | 0.9927 |
| producto | 3 | 0.3435 | 0.0074 | 32235 | 0.9786 |
| producto | 6 | 0.3834 | 0.0097 | 26513 | 0.9546 |
| producto | 12 | 0.3746 | 0.0258 | 14606 | 0.9104 |
| categoria | 1 | 0.1208 | -0.0062 | 216 | 1.0000 |
| categoria | 3 | 0.1428 | 0.0011 | 192 | 1.0000 |
| categoria | 6 | 0.1831 | -0.0065 | 156 | 1.0000 |
| categoria | 12 | 0.1503 | -0.0183 | 84 | 1.0000 |
| total | 1 | 0.0934 | -0.0062 | 18 | 1.0000 |
| total | 3 | 0.0906 | 0.0011 | 16 | 1.0000 |
| total | 6 | 0.1164 | -0.0065 | 13 | 1.0000 |
| total | 12 | 0.0811 | -0.0183 | 7 | 1.0000 |

## Por horizonte (grano producto)

| horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|
| 1 | 0.2953 | -0.0040 | 36003 | 0.9927 |
| 3 | 0.3435 | 0.0074 | 32235 | 0.9786 |
| 6 | 0.3834 | 0.0097 | 26513 | 0.9546 |
| 12 | 0.3746 | 0.0258 | 14606 | 0.9104 |

## Por categoría y horizonte

| categoria | horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|---|
| ACCESORIO | 1 | 1.4616 | 0.7340 | 342 | 1.0000 |
| ACCESORIO | 3 | 1.5468 | 0.8018 | 304 | 1.0000 |
| ACCESORIO | 6 | 1.5222 | 0.8243 | 247 | 1.0000 |
| ACCESORIO | 12 | 1.2560 | 0.1363 | 133 | 1.0000 |
| ALIMENTO | 1 | 0.2804 | 0.0541 | 828 | 1.0000 |
| ALIMENTO | 3 | 0.2753 | 0.0282 | 736 | 1.0000 |
| ALIMENTO | 6 | 0.3081 | 0.0039 | 598 | 1.0000 |
| ALIMENTO | 12 | 0.3148 | -0.0185 | 322 | 1.0000 |
| ANTIARTROSICO | 1 | 0.2362 | -0.0481 | 774 | 1.0000 |
| ANTIARTROSICO | 3 | 0.2656 | -0.0782 | 688 | 1.0000 |
| ANTIARTROSICO | 6 | 0.2619 | -0.1028 | 559 | 1.0000 |
| ANTIARTROSICO | 12 | 0.2803 | -0.1502 | 301 | 1.0000 |
| ANTIPARASITARIO EXTERNO | 1 | 0.3194 | 0.0198 | 6284 | 0.9946 |
| ANTIPARASITARIO EXTERNO | 3 | 0.3641 | 0.0489 | 5617 | 0.9849 |
| ANTIPARASITARIO EXTERNO | 6 | 0.4070 | 0.0503 | 4606 | 0.9674 |
| ANTIPARASITARIO EXTERNO | 12 | 0.3753 | 0.1432 | 2508 | 0.9358 |
| ANTIPARASITARIO INTERNO | 1 | 0.2303 | 0.0054 | 2448 | 1.0000 |
| ANTIPARASITARIO INTERNO | 3 | 0.2416 | 0.0531 | 2176 | 1.0000 |
| ANTIPARASITARIO INTERNO | 6 | 0.2702 | 0.0714 | 1768 | 1.0000 |
| ANTIPARASITARIO INTERNO | 12 | 0.2897 | 0.0961 | 952 | 1.0000 |
| BIOLOGICO | 1 | 0.3155 | 0.0072 | 778 | 0.9987 |
| BIOLOGICO | 3 | 0.4225 | 0.0250 | 692 | 0.9957 |
| BIOLOGICO | 6 | 0.5036 | 0.0415 | 563 | 0.9929 |
| BIOLOGICO | 12 | 0.5478 | -0.0475 | 305 | 0.9869 |
| CARDIOLOGICO | 1 | 0.1683 | -0.0296 | 1134 | 1.0000 |
| CARDIOLOGICO | 3 | 0.1711 | -0.0151 | 1008 | 1.0000 |
| CARDIOLOGICO | 6 | 0.2030 | -0.0167 | 819 | 1.0000 |
| CARDIOLOGICO | 12 | 0.2565 | -0.0683 | 441 | 1.0000 |
| CLINICO | 1 | 0.2400 | -0.0345 | 13070 | 0.9995 |
| CLINICO | 3 | 0.2648 | -0.0363 | 11626 | 0.9985 |
| CLINICO | 6 | 0.2881 | -0.0435 | 9452 | 0.9970 |
| CLINICO | 12 | 0.2958 | -0.0854 | 5096 | 0.9939 |
| DESCARTABLES | 1 | 0.3770 | 0.0455 | 936 | 1.0000 |
| DESCARTABLES | 3 | 0.3853 | 0.0974 | 832 | 1.0000 |
| DESCARTABLES | 6 | 0.4375 | 0.1250 | 676 | 1.0000 |
| DESCARTABLES | 12 | 0.5321 | 0.1456 | 364 | 1.0000 |
| HIGIENE Y BELLEZA | 1 | 0.2513 | -0.0155 | 3888 | 1.0000 |
| HIGIENE Y BELLEZA | 3 | 0.2951 | -0.0185 | 3456 | 1.0000 |
| HIGIENE Y BELLEZA | 6 | 0.3029 | 0.0005 | 2808 | 1.0000 |
| HIGIENE Y BELLEZA | 12 | 0.2854 | -0.0673 | 1512 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 1 | 0.2775 | -0.1088 | 18 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 3 | 0.2669 | -0.1467 | 16 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 6 | 0.3535 | -0.1991 | 13 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 12 | 0.3837 | -0.3404 | 7 | 1.0000 |
| SIN CATEGORIA | 1 | 0.4563 | -0.1767 | 5503 | 0.9598 |
| SIN CATEGORIA | 3 | 0.5835 | -0.3316 | 5084 | 0.8849 |
| SIN CATEGORIA | 6 | 0.5894 | -0.3181 | 4404 | 0.7677 |
| SIN CATEGORIA | 12 | 0.4730 | -0.2374 | 2665 | 0.5824 |

## Por cuadrante de intermitencia y horizonte

| cuadrante | horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|---|
| erratica | 1 | 0.4426 | 0.0220 | 4221 | 0.9955 |
| erratica | 3 | 0.5247 | 0.0240 | 3772 | 0.9873 |
| erratica | 6 | 0.6174 | 0.0167 | 3087 | 0.9741 |
| erratica | 12 | 0.5789 | 0.0496 | 1673 | 0.9474 |
| intermitente | 1 | 0.9603 | 0.4574 | 7867 | 0.9865 |
| intermitente | 3 | 1.8750 | 1.3699 | 7093 | 0.9578 |
| intermitente | 6 | 2.7000 | 2.2977 | 5901 | 0.9110 |
| intermitente | 12 | 3.4260 | 3.0806 | 3333 | 0.8266 |
| lumpy | 1 | 1.1783 | 0.5914 | 3142 | 0.9981 |
| lumpy | 3 | 2.0442 | 1.4522 | 2798 | 0.9943 |
| lumpy | 6 | 3.0773 | 2.4415 | 2281 | 0.9868 |
| lumpy | 12 | 5.6294 | 5.1088 | 1237 | 0.9741 |
| suave | 1 | 0.2654 | -0.0128 | 20773 | 0.9937 |
| suave | 3 | 0.3022 | -0.0073 | 18572 | 0.9823 |
| suave | 6 | 0.3276 | -0.0101 | 15244 | 0.9626 |
| suave | 12 | 0.3149 | -0.0043 | 8363 | 0.9269 |

## Calibración del intervalo P10–P90 por horizonte (M2.4) — nominal **0,80**

| horizonte | cobertura_empirica | desvio_vs_nominal | amplitud_relativa | n | cobertura | tasa_de_cruce |
|---|---|---|---|---|---|---|
| 1 | 0.7798 | -0.0202 | 0.8197 | 36003 | 0.9927 | 0.0120 |
| 3 | 0.8199 | 0.0199 | 1.1111 | 32235 | 0.9786 | 0.0022 |
| 6 | 0.8130 | 0.0130 | 1.2046 | 26513 | 0.9546 | 0.0036 |
| 12 | 0.8085 | 0.0085 | 1.2655 | 14606 | 0.9104 | 0.0035 |

## Pérdida pinball por cuantil y horizonte (normalizada)

| cuantil | horizonte | pinball | n | cobertura |
|---|---|---|---|---|
| 0.1000 | 1 | 0.0571 | 36003 | 0.9927 |
| 0.1000 | 3 | 0.0685 | 32235 | 0.9786 |
| 0.1000 | 6 | 0.0741 | 26513 | 0.9546 |
| 0.1000 | 12 | 0.0781 | 14606 | 0.9104 |
| 0.5000 | 1 | 0.1531 | 36003 | 0.9927 |
| 0.5000 | 3 | 0.1776 | 32235 | 0.9786 |
| 0.5000 | 6 | 0.1966 | 26513 | 0.9546 |
| 0.5000 | 12 | 0.1897 | 14606 | 0.9104 |
| 0.9000 | 1 | 0.0995 | 36003 | 0.9927 |
| 0.9000 | 3 | 0.1295 | 32235 | 0.9786 |
| 0.9000 | 6 | 0.1407 | 26513 | 0.9546 |
| 0.9000 | 12 | 0.1270 | 14606 | 0.9104 |

## Calibración del intervalo por cuadrante y horizonte

| cuadrante | horizonte | cobertura_empirica | desvio_vs_nominal | amplitud_relativa | n | cobertura |
|---|---|---|---|---|---|---|
| erratica | 1 | 0.6790 | -0.1210 | 0.9832 | 4221 | 0.9955 |
| erratica | 3 | 0.6992 | -0.1008 | 1.3342 | 3772 | 0.9873 |
| erratica | 6 | 0.6771 | -0.1229 | 1.3899 | 3087 | 0.9741 |
| erratica | 12 | 0.6700 | -0.1300 | 1.3701 | 1673 | 0.9474 |
| intermitente | 1 | 0.8572 | 0.0572 | 1.6477 | 7867 | 0.9865 |
| intermitente | 3 | 0.9230 | 0.1230 | 3.2476 | 7093 | 0.9578 |
| intermitente | 6 | 0.9111 | 0.1111 | 5.1467 | 5901 | 0.9110 |
| intermitente | 12 | 0.9071 | 0.1071 | 8.3358 | 3333 | 0.8266 |
| lumpy | 1 | 0.7089 | -0.0911 | 2.1281 | 3142 | 0.9981 |
| lumpy | 3 | 0.8537 | 0.0537 | 5.1031 | 2798 | 0.9943 |
| lumpy | 6 | 0.8370 | 0.0370 | 7.8945 | 2281 | 0.9868 |
| lumpy | 12 | 0.8257 | 0.0257 | 13.4695 | 1237 | 0.9741 |
| suave | 1 | 0.7820 | -0.0180 | 0.7849 | 20773 | 0.9937 |
| suave | 3 | 0.8010 | 0.0010 | 1.0527 | 18572 | 0.9823 |
| suave | 6 | 0.8012 | 0.0012 | 1.1377 | 15244 | 0.9626 |
| suave | 12 | 0.7990 | -0.0010 | 1.1867 | 8363 | 0.9269 |

## Calibración del intervalo por categoría y horizonte

| categoria | horizonte | cobertura_empirica | desvio_vs_nominal | amplitud_relativa | n | cobertura |
|---|---|---|---|---|---|---|
| ACCESORIO | 1 | 0.7485 | -0.0515 | 2.1958 | 342 | 1.0000 |
| ACCESORIO | 3 | 0.7401 | -0.0599 | 1.8836 | 304 | 1.0000 |
| ACCESORIO | 6 | 0.6842 | -0.1158 | 1.5057 | 247 | 1.0000 |
| ACCESORIO | 12 | 0.6692 | -0.1308 | 1.3735 | 133 | 1.0000 |
| ALIMENTO | 1 | 0.8068 | 0.0068 | 0.8124 | 828 | 1.0000 |
| ALIMENTO | 3 | 0.8370 | 0.0370 | 0.9776 | 736 | 1.0000 |
| ALIMENTO | 6 | 0.8779 | 0.0779 | 1.1413 | 598 | 1.0000 |
| ALIMENTO | 12 | 0.8944 | 0.0944 | 1.3874 | 322 | 1.0000 |
| ANTIARTROSICO | 1 | 0.7468 | -0.0532 | 0.6720 | 774 | 1.0000 |
| ANTIARTROSICO | 3 | 0.8023 | 0.0023 | 0.8318 | 688 | 1.0000 |
| ANTIARTROSICO | 6 | 0.7746 | -0.0254 | 0.8823 | 559 | 1.0000 |
| ANTIARTROSICO | 12 | 0.7243 | -0.0757 | 0.9426 | 301 | 1.0000 |
| ANTIPARASITARIO EXTERNO | 1 | 0.7467 | -0.0533 | 0.8861 | 6284 | 0.9946 |
| ANTIPARASITARIO EXTERNO | 3 | 0.7862 | -0.0138 | 1.2529 | 5617 | 0.9849 |
| ANTIPARASITARIO EXTERNO | 6 | 0.7864 | -0.0136 | 1.3578 | 4606 | 0.9674 |
| ANTIPARASITARIO EXTERNO | 12 | 0.8100 | 0.0100 | 1.4802 | 2508 | 0.9358 |
| ANTIPARASITARIO INTERNO | 1 | 0.8060 | 0.0060 | 0.7384 | 2448 | 1.0000 |
| ANTIPARASITARIO INTERNO | 3 | 0.8621 | 0.0621 | 0.9905 | 2176 | 1.0000 |
| ANTIPARASITARIO INTERNO | 6 | 0.8529 | 0.0529 | 1.1415 | 1768 | 1.0000 |
| ANTIPARASITARIO INTERNO | 12 | 0.8351 | 0.0351 | 1.1964 | 952 | 1.0000 |
| BIOLOGICO | 1 | 0.7786 | -0.0214 | 0.8961 | 778 | 0.9987 |
| BIOLOGICO | 3 | 0.8244 | 0.0244 | 1.3325 | 692 | 0.9957 |
| BIOLOGICO | 6 | 0.8050 | 0.0050 | 1.4450 | 563 | 0.9929 |
| BIOLOGICO | 12 | 0.7641 | -0.0359 | 1.3835 | 305 | 0.9869 |
| CARDIOLOGICO | 1 | 0.8139 | 0.0139 | 0.6131 | 1134 | 1.0000 |
| CARDIOLOGICO | 3 | 0.8651 | 0.0651 | 0.7850 | 1008 | 1.0000 |
| CARDIOLOGICO | 6 | 0.8571 | 0.0571 | 0.8662 | 819 | 1.0000 |
| CARDIOLOGICO | 12 | 0.8027 | 0.0027 | 0.9474 | 441 | 1.0000 |
| CLINICO | 1 | 0.7985 | -0.0015 | 0.6689 | 13070 | 0.9995 |
| CLINICO | 3 | 0.8330 | 0.0330 | 0.8351 | 11626 | 0.9985 |
| CLINICO | 6 | 0.8280 | 0.0280 | 0.8989 | 9452 | 0.9970 |
| CLINICO | 12 | 0.8134 | 0.0134 | 0.9271 | 5096 | 0.9939 |
| DESCARTABLES | 1 | 0.6944 | -0.1056 | 0.8557 | 936 | 1.0000 |
| DESCARTABLES | 3 | 0.8029 | 0.0029 | 1.0224 | 832 | 1.0000 |
| DESCARTABLES | 6 | 0.7648 | -0.0352 | 1.1515 | 676 | 1.0000 |
| DESCARTABLES | 12 | 0.7005 | -0.0995 | 1.1514 | 364 | 1.0000 |
| HIGIENE Y BELLEZA | 1 | 0.8014 | 0.0014 | 0.7293 | 3888 | 1.0000 |
| HIGIENE Y BELLEZA | 3 | 0.8414 | 0.0414 | 0.9469 | 3456 | 1.0000 |
| HIGIENE Y BELLEZA | 6 | 0.8486 | 0.0486 | 1.0281 | 2808 | 1.0000 |
| HIGIENE Y BELLEZA | 12 | 0.8565 | 0.0565 | 1.0116 | 1512 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 1 | 0.7778 | -0.0222 | 0.6786 | 18 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 3 | 0.8125 | 0.0125 | 0.8130 | 16 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 6 | 0.8462 | 0.0462 | 0.8129 | 13 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 12 | 0.8571 | 0.0571 | 0.9036 | 7 | 1.0000 |
| SIN CATEGORIA | 1 | 0.7556 | -0.0444 | 0.9229 | 5503 | 0.9598 |
| SIN CATEGORIA | 3 | 0.7886 | -0.0114 | 0.7921 | 5084 | 0.8849 |
| SIN CATEGORIA | 6 | 0.7601 | -0.0399 | 0.7706 | 4404 | 0.7677 |
| SIN CATEGORIA | 12 | 0.7726 | -0.0274 | 1.0074 | 2665 | 0.5824 |
