# Calibración de intervalos del modelo global — real-dispersion (2026-08-07)

Modelo global LightGBM (`GlobalLGBM`) con regresión cuantílica: GlobalLGBM_P10, GlobalLGBM_P50, GlobalLGBM_P90. Configuración `precio+crudo`, la que eligió la ablación de M2.3 **+ features de dispersión (M3.0)**.

- **Productos:** 2128 de 2128 · **cortes:** 18 · **horizonte:** 12 · **21.6 min**
- **Cobertura nominal del P10–P90:** 0.80. `desvio_vs_nominal` es la empírica menos ese valor, **con signo**: negativo es sub-cobertura (el intervalo promete menos riesgo del que hay) y positivo es un intervalo más ancho de lo necesario. No son el mismo error.
- **Cobertura esperada por longitud de serie:** 0.8393 — cota superior de la cobertura del global (`mlforecast` descarta las series sin lags completos), así que una `cobertura` baja en la tabla no es necesariamente del modelo.
- **Por qué la `cobertura` no es 1,0** (regla 4 de `backtests/README.md`): son las **altas de catálogo** de `roadmap-motor.md` §5.6.1 — productos cuya primera venta es posterior al corte, que ni los baselines ni el global pueden predecir porque no existen al momento de entrenar. Son **las mismas filas** que en el piso prospectivo y en las ablaciones de M2.3 (§6.5 punto 4 lo verificó fila a fila), así que las tres tablas se comparan a igual cobertura.

> **El intervalo se mide a grano producto, que es donde se predice.** No hay cobertura por categoría ni total: **la suma de cuantiles no es el cuantil de la suma** — sumar los P90 de todo el catálogo supone que a todos los productos les va bien el mismo mes y da un rango absurdamente ancho. Un intervalo agregado hay que predecirlo a esa altura de la jerarquía (M3.1). Los cortes por cuadrante y por categoría de abajo son desagregados del **mismo** grano producto, que es otra cosa.

> **El intervalo se evalúa cerrado** (`P10 <= real <= P90`). Con 42% de series intermitentes y el panel densificado a ceros (ADR-010), la fila más frecuente es `real == 0` con `P10 == 0`, y ese es un acierto: el modelo dijo que bien podía no venderse nada.

## Corrida

| id | fecha_ejecucion | n_cortes | horizonte_max | columnas_id | columna_objetivo | densificado | primer_corte | ultimo_corte | datos_filas | datos_series | datos_primer_mes | datos_ultimo_mes | datos_suma_objetivo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a79a9b23676b | 2026-08-07 | 18 | 12 | ('id_producto',) | unidades | True | 2024-11-01 | 2026-04-01 | 157431 | 2128 | 2018-07-01 | 2026-05-01 | 31122141.0000 |

## Por nivel de agregación y horizonte

| nivel | horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|---|
| producto | 1 | 0.2964 | -0.0041 | 36003 | 0.9927 |
| producto | 3 | 0.3408 | 0.0064 | 32235 | 0.9786 |
| producto | 6 | 0.3853 | 0.0046 | 26513 | 0.9546 |
| producto | 12 | 0.3699 | 0.0343 | 14606 | 0.9104 |
| categoria | 1 | 0.1212 | -0.0063 | 216 | 1.0000 |
| categoria | 3 | 0.1432 | 0.0001 | 192 | 1.0000 |
| categoria | 6 | 0.1795 | -0.0115 | 156 | 1.0000 |
| categoria | 12 | 0.1428 | -0.0098 | 84 | 1.0000 |
| total | 1 | 0.0939 | -0.0063 | 18 | 1.0000 |
| total | 3 | 0.0915 | 0.0001 | 16 | 1.0000 |
| total | 6 | 0.1165 | -0.0115 | 13 | 1.0000 |
| total | 12 | 0.0715 | -0.0098 | 7 | 1.0000 |

## Por horizonte (grano producto)

| horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|
| 1 | 0.2964 | -0.0041 | 36003 | 0.9927 |
| 3 | 0.3408 | 0.0064 | 32235 | 0.9786 |
| 6 | 0.3853 | 0.0046 | 26513 | 0.9546 |
| 12 | 0.3699 | 0.0343 | 14606 | 0.9104 |

## Por categoría y horizonte

| categoria | horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|---|
| ACCESORIO | 1 | 1.7019 | 1.0376 | 342 | 1.0000 |
| ACCESORIO | 3 | 1.7181 | 1.0219 | 304 | 1.0000 |
| ACCESORIO | 6 | 1.6814 | 0.9364 | 247 | 1.0000 |
| ACCESORIO | 12 | 1.3432 | 0.1803 | 133 | 1.0000 |
| ALIMENTO | 1 | 0.2905 | 0.0745 | 828 | 1.0000 |
| ALIMENTO | 3 | 0.2840 | 0.0376 | 736 | 1.0000 |
| ALIMENTO | 6 | 0.3176 | 0.0092 | 598 | 1.0000 |
| ALIMENTO | 12 | 0.3304 | -0.0163 | 322 | 1.0000 |
| ANTIARTROSICO | 1 | 0.2356 | -0.0430 | 774 | 1.0000 |
| ANTIARTROSICO | 3 | 0.2654 | -0.0722 | 688 | 1.0000 |
| ANTIARTROSICO | 6 | 0.2552 | -0.0903 | 559 | 1.0000 |
| ANTIARTROSICO | 12 | 0.2776 | -0.1425 | 301 | 1.0000 |
| ANTIPARASITARIO EXTERNO | 1 | 0.3164 | 0.0130 | 6284 | 0.9946 |
| ANTIPARASITARIO EXTERNO | 3 | 0.3545 | 0.0435 | 5617 | 0.9849 |
| ANTIPARASITARIO EXTERNO | 6 | 0.4090 | 0.0361 | 4606 | 0.9674 |
| ANTIPARASITARIO EXTERNO | 12 | 0.3650 | 0.1462 | 2508 | 0.9358 |
| ANTIPARASITARIO INTERNO | 1 | 0.2398 | 0.0164 | 2448 | 1.0000 |
| ANTIPARASITARIO INTERNO | 3 | 0.2482 | 0.0608 | 2176 | 1.0000 |
| ANTIPARASITARIO INTERNO | 6 | 0.2774 | 0.0967 | 1768 | 1.0000 |
| ANTIPARASITARIO INTERNO | 12 | 0.2905 | 0.1328 | 952 | 1.0000 |
| BIOLOGICO | 1 | 0.3116 | -0.0017 | 778 | 0.9987 |
| BIOLOGICO | 3 | 0.4218 | 0.0194 | 692 | 0.9957 |
| BIOLOGICO | 6 | 0.4940 | 0.0172 | 563 | 0.9929 |
| BIOLOGICO | 12 | 0.5385 | -0.0294 | 305 | 0.9869 |
| CARDIOLOGICO | 1 | 0.1701 | -0.0289 | 1134 | 1.0000 |
| CARDIOLOGICO | 3 | 0.1731 | -0.0110 | 1008 | 1.0000 |
| CARDIOLOGICO | 6 | 0.2125 | -0.0115 | 819 | 1.0000 |
| CARDIOLOGICO | 12 | 0.2536 | -0.0803 | 441 | 1.0000 |
| CLINICO | 1 | 0.2436 | -0.0256 | 13070 | 0.9995 |
| CLINICO | 3 | 0.2669 | -0.0340 | 11626 | 0.9985 |
| CLINICO | 6 | 0.2927 | -0.0378 | 9452 | 0.9970 |
| CLINICO | 12 | 0.3005 | -0.0806 | 5096 | 0.9939 |
| DESCARTABLES | 1 | 0.3874 | 0.0550 | 936 | 1.0000 |
| DESCARTABLES | 3 | 0.4003 | 0.1130 | 832 | 1.0000 |
| DESCARTABLES | 6 | 0.4421 | 0.1386 | 676 | 1.0000 |
| DESCARTABLES | 12 | 0.5302 | 0.1341 | 364 | 1.0000 |
| HIGIENE Y BELLEZA | 1 | 0.2603 | -0.0064 | 3888 | 1.0000 |
| HIGIENE Y BELLEZA | 3 | 0.2939 | -0.0072 | 3456 | 1.0000 |
| HIGIENE Y BELLEZA | 6 | 0.3083 | 0.0111 | 2808 | 1.0000 |
| HIGIENE Y BELLEZA | 12 | 0.2894 | -0.0506 | 1512 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 1 | 0.2811 | -0.1116 | 18 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 3 | 0.2868 | -0.1699 | 16 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 6 | 0.3455 | -0.2287 | 13 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 12 | 0.3954 | -0.3624 | 7 | 1.0000 |
| SIN CATEGORIA | 1 | 0.4887 | -0.1443 | 5503 | 0.9598 |
| SIN CATEGORIA | 3 | 0.6055 | -0.3203 | 5084 | 0.8849 |
| SIN CATEGORIA | 6 | 0.5995 | -0.2896 | 4404 | 0.7677 |
| SIN CATEGORIA | 12 | 0.4724 | -0.2190 | 2665 | 0.5824 |

## Por cuadrante de intermitencia y horizonte

| cuadrante | horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|---|
| erratica | 1 | 0.4348 | -0.0023 | 4221 | 0.9955 |
| erratica | 3 | 0.5167 | 0.0104 | 3772 | 0.9873 |
| erratica | 6 | 0.6016 | -0.0050 | 3087 | 0.9741 |
| erratica | 12 | 0.5662 | 0.0433 | 1673 | 0.9474 |
| intermitente | 1 | 1.5831 | 1.0960 | 7867 | 0.9865 |
| intermitente | 3 | 2.2584 | 1.7497 | 7093 | 0.9578 |
| intermitente | 6 | 3.1512 | 2.7608 | 5901 | 0.9110 |
| intermitente | 12 | 3.4188 | 3.1353 | 3333 | 0.8266 |
| lumpy | 1 | 1.3312 | 0.7692 | 3142 | 0.9981 |
| lumpy | 3 | 2.0826 | 1.5220 | 2798 | 0.9943 |
| lumpy | 6 | 3.1218 | 2.4998 | 2281 | 0.9868 |
| lumpy | 12 | 4.9516 | 4.3910 | 1237 | 0.9741 |
| suave | 1 | 0.2640 | -0.0132 | 20773 | 0.9937 |
| suave | 3 | 0.2981 | -0.0087 | 18572 | 0.9823 |
| suave | 6 | 0.3298 | -0.0151 | 15244 | 0.9626 |
| suave | 12 | 0.3131 | 0.0081 | 8363 | 0.9269 |

## Calibración del intervalo P10–P90 por horizonte (M2.4) — nominal **0,80**

| horizonte | cobertura_empirica | desvio_vs_nominal | amplitud_relativa | n | cobertura | tasa_de_cruce |
|---|---|---|---|---|---|---|
| 1 | 0.6376 | -0.1624 | 0.8115 | 36003 | 0.9927 | 0.0285 |
| 3 | 0.7784 | -0.0216 | 1.0652 | 32235 | 0.9786 | 0.0074 |
| 6 | 0.8100 | 0.0100 | 1.1546 | 26513 | 0.9546 | 0.0057 |
| 12 | 0.8015 | 0.0015 | 1.1987 | 14606 | 0.9104 | 0.0057 |

## Pérdida pinball por cuantil y horizonte (normalizada)

| cuantil | horizonte | pinball | n | cobertura |
|---|---|---|---|---|
| 0.1000 | 1 | 0.0563 | 36003 | 0.9927 |
| 0.1000 | 3 | 0.0667 | 32235 | 0.9786 |
| 0.1000 | 6 | 0.0721 | 26513 | 0.9546 |
| 0.1000 | 12 | 0.0754 | 14606 | 0.9104 |
| 0.5000 | 1 | 0.1530 | 36003 | 0.9927 |
| 0.5000 | 3 | 0.1786 | 32235 | 0.9786 |
| 0.5000 | 6 | 0.1958 | 26513 | 0.9546 |
| 0.5000 | 12 | 0.1867 | 14606 | 0.9104 |
| 0.9000 | 1 | 0.1002 | 36003 | 0.9927 |
| 0.9000 | 3 | 0.1343 | 32235 | 0.9786 |
| 0.9000 | 6 | 0.1433 | 26513 | 0.9546 |
| 0.9000 | 12 | 0.1260 | 14606 | 0.9104 |

## Calibración del intervalo por cuadrante y horizonte

| cuadrante | horizonte | cobertura_empirica | desvio_vs_nominal | amplitud_relativa | n | cobertura |
|---|---|---|---|---|---|---|
| erratica | 1 | 0.6802 | -0.1198 | 1.0095 | 4221 | 0.9955 |
| erratica | 3 | 0.7172 | -0.0828 | 1.3631 | 3772 | 0.9873 |
| erratica | 6 | 0.6997 | -0.1003 | 1.4152 | 3087 | 0.9741 |
| erratica | 12 | 0.6782 | -0.1218 | 1.3928 | 1673 | 0.9474 |
| intermitente | 1 | 0.3859 | -0.4141 | 1.6622 | 7867 | 0.9865 |
| intermitente | 3 | 0.8007 | 0.0007 | 3.2409 | 7093 | 0.9578 |
| intermitente | 6 | 0.9217 | 0.1217 | 4.9902 | 5901 | 0.9110 |
| intermitente | 12 | 0.9002 | 0.1002 | 5.8707 | 3333 | 0.8266 |
| lumpy | 1 | 0.3932 | -0.4068 | 2.4624 | 3142 | 0.9981 |
| lumpy | 3 | 0.7804 | -0.0196 | 4.9021 | 2798 | 0.9943 |
| lumpy | 6 | 0.8587 | 0.0587 | 7.2086 | 2281 | 0.9868 |
| lumpy | 12 | 0.8241 | 0.0241 | 10.4198 | 1237 | 0.9741 |
| suave | 1 | 0.7607 | -0.0393 | 0.7700 | 20773 | 0.9937 |
| suave | 3 | 0.7822 | -0.0178 | 0.9957 | 18572 | 0.9823 |
| suave | 6 | 0.7842 | -0.0158 | 1.0784 | 15244 | 0.9626 |
| suave | 12 | 0.7881 | -0.0119 | 1.1230 | 8363 | 0.9269 |

## Calibración del intervalo por categoría y horizonte

| categoria | horizonte | cobertura_empirica | desvio_vs_nominal | amplitud_relativa | n | cobertura |
|---|---|---|---|---|---|---|
| ACCESORIO | 1 | 0.4561 | -0.3439 | 2.1152 | 342 | 1.0000 |
| ACCESORIO | 3 | 0.6546 | -0.1454 | 2.1289 | 304 | 1.0000 |
| ACCESORIO | 6 | 0.6518 | -0.1482 | 1.6894 | 247 | 1.0000 |
| ACCESORIO | 12 | 0.6316 | -0.1684 | 0.8295 | 133 | 1.0000 |
| ALIMENTO | 1 | 0.7428 | -0.0572 | 0.7850 | 828 | 1.0000 |
| ALIMENTO | 3 | 0.8207 | 0.0207 | 0.9171 | 736 | 1.0000 |
| ALIMENTO | 6 | 0.8612 | 0.0612 | 1.1143 | 598 | 1.0000 |
| ALIMENTO | 12 | 0.8758 | 0.0758 | 1.3317 | 322 | 1.0000 |
| ANTIARTROSICO | 1 | 0.6693 | -0.1307 | 0.6790 | 774 | 1.0000 |
| ANTIARTROSICO | 3 | 0.7849 | -0.0151 | 0.7884 | 688 | 1.0000 |
| ANTIARTROSICO | 6 | 0.7907 | -0.0093 | 0.8303 | 559 | 1.0000 |
| ANTIARTROSICO | 12 | 0.7375 | -0.0625 | 0.8732 | 301 | 1.0000 |
| ANTIPARASITARIO EXTERNO | 1 | 0.6432 | -0.1568 | 0.8796 | 6284 | 0.9946 |
| ANTIPARASITARIO EXTERNO | 3 | 0.7587 | -0.0413 | 1.2115 | 5617 | 0.9849 |
| ANTIPARASITARIO EXTERNO | 6 | 0.7781 | -0.0219 | 1.3029 | 4606 | 0.9674 |
| ANTIPARASITARIO EXTERNO | 12 | 0.7997 | -0.0003 | 1.4122 | 2508 | 0.9358 |
| ANTIPARASITARIO INTERNO | 1 | 0.6324 | -0.1676 | 0.7265 | 2448 | 1.0000 |
| ANTIPARASITARIO INTERNO | 3 | 0.8038 | 0.0038 | 0.9585 | 2176 | 1.0000 |
| ANTIPARASITARIO INTERNO | 6 | 0.8433 | 0.0433 | 1.0788 | 1768 | 1.0000 |
| ANTIPARASITARIO INTERNO | 12 | 0.8372 | 0.0372 | 1.1375 | 952 | 1.0000 |
| BIOLOGICO | 1 | 0.6654 | -0.1346 | 0.8897 | 778 | 0.9987 |
| BIOLOGICO | 3 | 0.7881 | -0.0119 | 1.2683 | 692 | 0.9957 |
| BIOLOGICO | 6 | 0.8140 | 0.0140 | 1.4012 | 563 | 0.9929 |
| BIOLOGICO | 12 | 0.7674 | -0.0326 | 1.2960 | 305 | 0.9869 |
| CARDIOLOGICO | 1 | 0.7522 | -0.0478 | 0.6048 | 1134 | 1.0000 |
| CARDIOLOGICO | 3 | 0.8264 | 0.0264 | 0.7109 | 1008 | 1.0000 |
| CARDIOLOGICO | 6 | 0.8193 | 0.0193 | 0.7912 | 819 | 1.0000 |
| CARDIOLOGICO | 12 | 0.7959 | -0.0041 | 0.8092 | 441 | 1.0000 |
| CLINICO | 1 | 0.6807 | -0.1193 | 0.6636 | 13070 | 0.9995 |
| CLINICO | 3 | 0.7937 | -0.0063 | 0.7876 | 11626 | 0.9985 |
| CLINICO | 6 | 0.8259 | 0.0259 | 0.8510 | 9452 | 0.9970 |
| CLINICO | 12 | 0.8116 | 0.0116 | 0.8764 | 5096 | 0.9939 |
| DESCARTABLES | 1 | 0.5011 | -0.2989 | 0.8814 | 936 | 1.0000 |
| DESCARTABLES | 3 | 0.7632 | -0.0368 | 1.0278 | 832 | 1.0000 |
| DESCARTABLES | 6 | 0.7722 | -0.0278 | 1.1680 | 676 | 1.0000 |
| DESCARTABLES | 12 | 0.6511 | -0.1489 | 1.0886 | 364 | 1.0000 |
| HIGIENE Y BELLEZA | 1 | 0.6592 | -0.1408 | 0.7487 | 3888 | 1.0000 |
| HIGIENE Y BELLEZA | 3 | 0.7986 | -0.0014 | 0.9237 | 3456 | 1.0000 |
| HIGIENE Y BELLEZA | 6 | 0.8447 | 0.0447 | 1.0014 | 2808 | 1.0000 |
| HIGIENE Y BELLEZA | 12 | 0.8459 | 0.0459 | 0.9831 | 1512 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 1 | 0.8333 | 0.0333 | 0.6565 | 18 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 3 | 0.7500 | -0.0500 | 0.8004 | 16 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 6 | 0.8462 | 0.0462 | 0.8049 | 13 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 12 | 0.7143 | -0.0857 | 0.8333 | 7 | 1.0000 |
| SIN CATEGORIA | 1 | 0.4962 | -0.3038 | 0.8239 | 5503 | 0.9598 |
| SIN CATEGORIA | 3 | 0.7264 | -0.0736 | 0.7147 | 5084 | 0.8849 |
| SIN CATEGORIA | 6 | 0.7717 | -0.0283 | 0.7360 | 4404 | 0.7677 |
| SIN CATEGORIA | 12 | 0.7610 | -0.0390 | 0.9182 | 2665 | 0.5824 |
