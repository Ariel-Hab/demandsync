# Champion/challenger: global contra el piso de baselines — real (2026-08-06)

Champion/challenger de M2.5. **Ningún modelo se reajustó**: la tabla sale de cruzar los checkpoints de dos corridas que comparten `id` — el hash de corrida es de configuración + datos y no incluye el predictor.

- **Productos:** 2128 de 2128 · **cortes:** 18 · **horizonte:** 12 · **filas cruzadas:** 305309 · **44.6 s**
- **Candidatos del champion:** 7 baselines + `GlobalLGBM` + `GlobalLGBM_P50`, elegidos con **selección prospectiva + cascada** (ADR-016) — por (serie, corte), y en cada corte solo con el error de las filas cuyo mes ya ocurrió.
- **El piso usa exactamente la misma regla**, y eso es el punto: si el champion eligiera con hindsight y el piso no, la comparación estaría inclinada a favor del global, que es ADR-016 punto 4 al revés.
- **`global` y `global_P50` no seleccionan nada**: son la columna del modelo aplicada a todas las series. Sirven para separar cuánto del resultado es el modelo y cuánto es elegir por serie.
- **Las tablas estándar de abajo (por nivel, categoría, cuadrante, MASE) son del `champion`**, que es el candidato a promover. La comparación entre los cuatro está en *Cabeza a cabeza*.

> **`mejora` es `wape(campeon) - wape(retador)`: positivo favorece al retador.** Se reporta la mediana y los cuartiles, no la media: la distribución tiene colas largas y una serie con WAPE de 40 corre el promedio entero.

> **Solo se comparan las celdas donde los dos contendientes tienen la misma cobertura.** En `metricas.wape` una predicción nula aporta 0 al numerador, así que una serie **no predicha** puntúa WAPE 0,0 —perfecto— y solo la columna `cobertura` lo delata. La columna `no_comparable` cuenta lo que queda afuera.

> **Por qué la `cobertura` no es 1,0:** son las **altas de catálogo** de `roadmap-motor.md` §5.6.1 — productos cuya primera venta es posterior al corte. §6.5 verificó fila a fila que son **las mismas** en las dos corridas, así que la comparación es a igual cobertura por construcción, no por suerte.

## Corrida

| id | fecha_ejecucion | n_cortes | horizonte_max | columnas_id | columna_objetivo | densificado | primer_corte | ultimo_corte | datos_filas | datos_series | datos_primer_mes | datos_ultimo_mes | datos_suma_objetivo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a79a9b23676b | 2026-08-06 | 18 | 12 | ('id_producto',) | unidades | True | 2024-11-01 | 2026-04-01 | 157431 | 2128 | 2018-07-01 | 2026-05-01 | 31122141.0000 |

## Cabeza a cabeza por nivel y horizonte (M2.5) — **solo se comparan WAPE con la misma `cobertura`**

| contendiente | nivel | horizonte | wape | n | cobertura | sesgo |
|---|---|---|---|---|---|---|
| piso | producto | 1 | 0.3305 | 36003 | 0.9927 | 0.0099 |
| global | producto | 1 | 0.2953 | 36003 | 0.9927 | -0.0040 |
| global_P50 | producto | 1 | 0.3055 | 36003 | 0.9927 | -0.0819 |
| champion | producto | 1 | 0.3230 | 36003 | 0.9927 | -0.0009 |
| piso | producto | 3 | 0.3767 | 32235 | 0.9786 | 0.0266 |
| global | producto | 3 | 0.3435 | 32235 | 0.9786 | 0.0074 |
| global_P50 | producto | 3 | 0.3529 | 32235 | 0.9786 | -0.0853 |
| champion | producto | 3 | 0.3667 | 32235 | 0.9786 | 0.0139 |
| piso | producto | 6 | 0.4001 | 26513 | 0.9546 | 0.0061 |
| global | producto | 6 | 0.3834 | 26513 | 0.9546 | 0.0097 |
| global_P50 | producto | 6 | 0.3868 | 26513 | 0.9546 | -0.0889 |
| champion | producto | 6 | 0.3928 | 26513 | 0.9546 | 0.0013 |
| piso | producto | 12 | 0.3699 | 14606 | 0.9104 | 0.0351 |
| global | producto | 12 | 0.3746 | 14606 | 0.9104 | 0.0258 |
| global_P50 | producto | 12 | 0.3627 | 14606 | 0.9104 | -0.0903 |
| champion | producto | 12 | 0.3644 | 14606 | 0.9104 | 0.0359 |
| piso | categoria | 1 | 0.1509 | 216 | 1.0000 | 0.0077 |
| global | categoria | 1 | 0.1208 | 216 | 1.0000 | -0.0062 |
| global_P50 | categoria | 1 | 0.1735 | 216 | 1.0000 | -0.0841 |
| champion | categoria | 1 | 0.1428 | 216 | 1.0000 | -0.0031 |
| piso | categoria | 3 | 0.1701 | 192 | 1.0000 | 0.0203 |
| global | categoria | 3 | 0.1428 | 192 | 1.0000 | 0.0011 |
| global_P50 | categoria | 3 | 0.1997 | 192 | 1.0000 | -0.0915 |
| champion | categoria | 3 | 0.1648 | 192 | 1.0000 | 0.0077 |
| piso | categoria | 6 | 0.2063 | 156 | 1.0000 | -0.0100 |
| global | categoria | 6 | 0.1831 | 156 | 1.0000 | -0.0065 |
| global_P50 | categoria | 6 | 0.2245 | 156 | 1.0000 | -0.1050 |
| champion | categoria | 6 | 0.2010 | 156 | 1.0000 | -0.0149 |
| piso | categoria | 12 | 0.1787 | 84 | 1.0000 | -0.0090 |
| global | categoria | 12 | 0.1503 | 84 | 1.0000 | -0.0183 |
| global_P50 | categoria | 12 | 0.2106 | 84 | 1.0000 | -0.1344 |
| champion | categoria | 12 | 0.1754 | 84 | 1.0000 | -0.0082 |
| piso | total | 1 | 0.1205 | 18 | 1.0000 | 0.0077 |
| global | total | 1 | 0.0934 | 18 | 1.0000 | -0.0062 |
| global_P50 | total | 1 | 0.1436 | 18 | 1.0000 | -0.0841 |
| champion | total | 1 | 0.1088 | 18 | 1.0000 | -0.0031 |
| piso | total | 3 | 0.1390 | 16 | 1.0000 | 0.0203 |
| global | total | 3 | 0.0906 | 16 | 1.0000 | 0.0011 |
| global_P50 | total | 3 | 0.1547 | 16 | 1.0000 | -0.0915 |
| champion | total | 3 | 0.1294 | 16 | 1.0000 | 0.0077 |
| piso | total | 6 | 0.1575 | 13 | 1.0000 | -0.0100 |
| global | total | 6 | 0.1164 | 13 | 1.0000 | -0.0065 |
| global_P50 | total | 6 | 0.1684 | 13 | 1.0000 | -0.1050 |
| champion | total | 6 | 0.1458 | 13 | 1.0000 | -0.0149 |
| piso | total | 12 | 0.0867 | 7 | 1.0000 | -0.0090 |
| global | total | 12 | 0.0811 | 7 | 1.0000 | -0.0183 |
| global_P50 | total | 12 | 0.1344 | 7 | 1.0000 | -0.1344 |
| champion | total | 12 | 0.0881 | 7 | 1.0000 | -0.0082 |

## Cabeza a cabeza **por cuadrante** (grano producto) — leer con la columna `peso_%`: es cuánto pesa cada cuadrante en el WAPE agregado de arriba

| contendiente | cuadrante | horizonte | wape | n | cobertura | sesgo | peso_% |
|---|---|---|---|---|---|---|---|
| piso | erratica | 1 | 0.4748 | 4221 | 0.9955 | 0.0390 | 13.3324 |
| global | erratica | 1 | 0.4426 | 4221 | 0.9955 | 0.0220 | 13.3324 |
| global_P50 | erratica | 1 | 0.4404 | 4221 | 0.9955 | -0.1233 | 13.3324 |
| champion | erratica | 1 | 0.4585 | 4221 | 0.9955 | 0.0264 | 13.3324 |
| piso | erratica | 3 | 0.5764 | 3772 | 0.9873 | 0.0571 | 13.0671 |
| global | erratica | 3 | 0.5247 | 3772 | 0.9873 | 0.0240 | 13.0671 |
| global_P50 | erratica | 3 | 0.5468 | 3772 | 0.9873 | -0.1341 | 13.0671 |
| champion | erratica | 3 | 0.5573 | 3772 | 0.9873 | 0.0350 | 13.0671 |
| piso | erratica | 6 | 0.6400 | 3087 | 0.9741 | -0.0411 | 13.3105 |
| global | erratica | 6 | 0.6174 | 3087 | 0.9741 | 0.0167 | 13.3105 |
| global_P50 | erratica | 6 | 0.6027 | 3087 | 0.9741 | -0.1505 | 13.3105 |
| champion | erratica | 6 | 0.6341 | 3087 | 0.9741 | -0.0398 | 13.3105 |
| piso | erratica | 12 | 0.5535 | 1673 | 0.9474 | -0.0322 | 13.8407 |
| global | erratica | 12 | 0.5789 | 1673 | 0.9474 | 0.0496 | 13.8407 |
| global_P50 | erratica | 12 | 0.5486 | 1673 | 0.9474 | -0.1555 | 13.8407 |
| champion | erratica | 12 | 0.5575 | 1673 | 0.9474 | -0.0084 | 13.8407 |
| piso | intermitente | 1 | 0.9616 | 7867 | 0.9865 | 0.2107 | 0.4634 |
| global | intermitente | 1 | 0.9603 | 7867 | 0.9865 | 0.4574 | 0.4634 |
| global_P50 | intermitente | 1 | 0.5856 | 7867 | 0.9865 | -0.0941 | 0.4634 |
| champion | intermitente | 1 | 0.9149 | 7867 | 0.9865 | 0.1779 | 0.4634 |
| piso | intermitente | 3 | 0.9381 | 7093 | 0.9578 | 0.1838 | 0.4604 |
| global | intermitente | 3 | 1.8750 | 7093 | 0.9578 | 1.3699 | 0.4604 |
| global_P50 | intermitente | 3 | 0.7002 | 7093 | 0.9578 | -0.0919 | 0.4604 |
| champion | intermitente | 3 | 0.9007 | 7093 | 0.9578 | 0.1554 | 0.4604 |
| piso | intermitente | 6 | 1.1460 | 5901 | 0.9110 | 0.3370 | 0.4332 |
| global | intermitente | 6 | 2.7000 | 5901 | 0.9110 | 2.2977 | 0.4332 |
| global_P50 | intermitente | 6 | 0.9925 | 5901 | 0.9110 | 0.2355 | 0.4332 |
| champion | intermitente | 6 | 1.2150 | 5901 | 0.9110 | 0.4284 | 0.4332 |
| piso | intermitente | 12 | 1.2254 | 3333 | 0.8266 | 0.3646 | 0.4002 |
| global | intermitente | 12 | 3.4260 | 3333 | 0.8266 | 3.0806 | 0.4002 |
| global_P50 | intermitente | 12 | 1.4719 | 3333 | 0.8266 | 0.6450 | 0.4002 |
| champion | intermitente | 12 | 1.3426 | 3333 | 0.8266 | 0.6131 | 0.4002 |
| piso | lumpy | 1 | 1.2052 | 3142 | 0.9981 | 0.3596 | 0.3269 |
| global | lumpy | 1 | 1.1783 | 3142 | 0.9981 | 0.5914 | 0.3269 |
| global_P50 | lumpy | 1 | 0.7900 | 3142 | 0.9981 | -0.0120 | 0.3269 |
| champion | lumpy | 1 | 1.2073 | 3142 | 0.9981 | 0.3744 | 0.3269 |
| piso | lumpy | 3 | 1.5863 | 2798 | 0.9943 | 0.6532 | 0.2905 |
| global | lumpy | 3 | 2.0442 | 2798 | 0.9943 | 1.4522 | 0.2905 |
| global_P50 | lumpy | 3 | 1.0328 | 2798 | 0.9943 | 0.1191 | 0.2905 |
| champion | lumpy | 3 | 1.5816 | 2798 | 0.9943 | 0.6730 | 0.2905 |
| piso | lumpy | 6 | 1.9245 | 2281 | 0.9868 | 0.7809 | 0.2519 |
| global | lumpy | 6 | 3.0773 | 2281 | 0.9868 | 2.4415 | 0.2519 |
| global_P50 | lumpy | 6 | 1.7592 | 2281 | 0.9868 | 0.7035 | 0.2519 |
| champion | lumpy | 6 | 2.0069 | 2281 | 0.9868 | 0.8989 | 0.2519 |
| piso | lumpy | 12 | 2.5491 | 1237 | 0.9741 | 1.3620 | 0.2008 |
| global | lumpy | 12 | 5.6294 | 1237 | 0.9741 | 5.1088 | 0.2008 |
| global_P50 | lumpy | 12 | 2.8458 | 1237 | 0.9741 | 1.7926 | 0.2008 |
| champion | lumpy | 12 | 2.7709 | 1237 | 0.9741 | 1.6158 | 0.2008 |
| piso | suave | 1 | 0.3013 | 20773 | 0.9937 | 0.0030 | 85.8774 |
| global | suave | 1 | 0.2654 | 20773 | 0.9937 | -0.0128 | 85.8774 |
| global_P50 | suave | 1 | 0.2812 | 20773 | 0.9937 | -0.0756 | 85.8774 |
| champion | suave | 1 | 0.2954 | 20773 | 0.9937 | -0.0075 | 85.8774 |
| piso | suave | 3 | 0.3393 | 18572 | 0.9823 | 0.0190 | 86.1820 |
| global | suave | 3 | 0.3022 | 18572 | 0.9823 | -0.0073 | 86.1820 |
| global_P50 | suave | 3 | 0.3194 | 18572 | 0.9823 | -0.0785 | 86.1820 |
| champion | suave | 3 | 0.3309 | 18572 | 0.9823 | 0.0077 | 86.1820 |
| piso | suave | 6 | 0.3547 | 15244 | 0.9626 | 0.0095 | 86.0043 |
| global | suave | 6 | 0.3276 | 15244 | 0.9626 | -0.0101 | 86.0043 |
| global_P50 | suave | 6 | 0.3463 | 15244 | 0.9626 | -0.0833 | 86.0043 |
| champion | suave | 6 | 0.3466 | 15244 | 0.9626 | 0.0029 | 86.0043 |
| piso | suave | 12 | 0.3310 | 8363 | 0.9269 | 0.0413 | 85.5582 |
| global | suave | 12 | 0.3149 | 8363 | 0.9269 | -0.0043 | 85.5582 |
| global_P50 | suave | 12 | 0.3216 | 8363 | 0.9269 | -0.0877 | 85.5582 |
| champion | suave | 12 | 0.3229 | 8363 | 0.9269 | 0.0367 | 85.5582 |

## ¿En cuántas series le gana el global al piso? `mejora = wape(piso) − wape(global)`, positivo favorece al global

| cuadrante | horizonte | series | no_comparable | gana_retador | %_gana_retador | mejora_mediana | mejora_p25 | mejora_p75 |
|---|---|---|---|---|---|---|---|---|
| erratica | 1 | 239 | 0 | 128 | 53.6000 | 0.0214 | -0.1280 | 0.1445 |
| erratica | 2 | 239 | 0 | 147 | 61.5000 | 0.0466 | -0.0953 | 0.1566 |
| erratica | 3 | 239 | 0 | 128 | 53.6000 | 0.0199 | -0.1261 | 0.1592 |
| erratica | 4 | 239 | 0 | 123 | 51.5000 | 0.0140 | -0.1801 | 0.1314 |
| erratica | 5 | 239 | 0 | 116 | 48.5000 | -0.0063 | -0.1855 | 0.1358 |
| erratica | 6 | 239 | 0 | 116 | 48.5000 | -0.0201 | -0.2278 | 0.1215 |
| erratica | 7 | 239 | 0 | 115 | 48.1000 | -0.0233 | -0.2370 | 0.1128 |
| erratica | 8 | 237 | 2 | 102 | 43.0000 | -0.0632 | -0.2935 | 0.1079 |
| erratica | 9 | 236 | 3 | 96 | 40.7000 | -0.0369 | -0.2522 | 0.0747 |
| erratica | 10 | 236 | 3 | 102 | 43.2000 | -0.0357 | -0.3040 | 0.0816 |
| erratica | 11 | 235 | 4 | 103 | 43.8000 | -0.0334 | -0.2579 | 0.0805 |
| erratica | 12 | 231 | 8 | 106 | 45.9000 | -0.0464 | -0.3118 | 0.1212 |
| intermitente | 1 | 488 | 0 | 64 | 13.1000 | -2.1360 | -5.4452 | -0.1831 |
| intermitente | 2 | 479 | 9 | 43 | 9.0000 | -4.5771 | -15.5261 | -0.6721 |
| intermitente | 3 | 476 | 12 | 33 | 6.9000 | -4.8758 | -18.3101 | -0.5833 |
| intermitente | 4 | 476 | 12 | 34 | 7.1000 | -5.0607 | -19.4591 | -0.7244 |
| intermitente | 5 | 466 | 22 | 24 | 5.2000 | -5.2082 | -19.3348 | -0.7812 |
| intermitente | 6 | 460 | 28 | 28 | 6.1000 | -5.9931 | -21.7963 | -0.7509 |
| intermitente | 7 | 445 | 43 | 23 | 5.2000 | -6.1770 | -28.1271 | -0.9566 |
| intermitente | 8 | 437 | 51 | 23 | 5.3000 | -5.9318 | -23.3078 | -0.8348 |
| intermitente | 9 | 433 | 55 | 23 | 5.3000 | -4.0915 | -20.8903 | -0.6642 |
| intermitente | 10 | 427 | 61 | 20 | 4.7000 | -3.9733 | -17.4385 | -0.6823 |
| intermitente | 11 | 419 | 69 | 19 | 4.5000 | -4.2249 | -15.0921 | -0.6903 |
| intermitente | 12 | 407 | 81 | 18 | 4.4000 | -3.8074 | -15.9075 | -0.5365 |
| lumpy | 1 | 177 | 0 | 35 | 19.8000 | -0.7360 | -2.3157 | -0.0069 |
| lumpy | 2 | 177 | 0 | 35 | 19.8000 | -0.8848 | -2.7583 | 0.0009 |
| lumpy | 3 | 177 | 0 | 29 | 16.4000 | -0.9271 | -3.4728 | -0.0332 |
| lumpy | 4 | 177 | 0 | 33 | 18.6000 | -1.2683 | -4.8931 | -0.0246 |
| lumpy | 5 | 177 | 0 | 33 | 18.6000 | -1.2400 | -5.1577 | -0.0241 |
| lumpy | 6 | 175 | 2 | 29 | 16.6000 | -1.9833 | -6.3782 | -0.0700 |
| lumpy | 7 | 175 | 2 | 29 | 16.6000 | -2.3083 | -6.0405 | -0.0469 |
| lumpy | 8 | 174 | 3 | 30 | 17.2000 | -2.3503 | -7.8432 | -0.0073 |
| lumpy | 9 | 174 | 3 | 25 | 14.4000 | -2.6326 | -6.6882 | -0.2305 |
| lumpy | 10 | 174 | 3 | 26 | 14.9000 | -2.6881 | -7.2614 | -0.0875 |
| lumpy | 11 | 174 | 3 | 23 | 13.2000 | -2.1291 | -10.2483 | -0.0718 |
| lumpy | 12 | 173 | 4 | 24 | 13.9000 | -2.5222 | -10.6347 | -0.0154 |
| suave | 1 | 1202 | 22 | 679 | 56.5000 | 0.0087 | -0.0342 | 0.0437 |
| suave | 2 | 1196 | 28 | 736 | 61.5000 | 0.0151 | -0.0255 | 0.0544 |
| suave | 3 | 1193 | 31 | 676 | 56.7000 | 0.0104 | -0.0392 | 0.0507 |
| suave | 4 | 1192 | 32 | 670 | 56.2000 | 0.0105 | -0.0508 | 0.0564 |
| suave | 5 | 1185 | 39 | 660 | 55.7000 | 0.0094 | -0.0548 | 0.0541 |
| suave | 6 | 1171 | 53 | 642 | 54.8000 | 0.0087 | -0.0528 | 0.0510 |
| suave | 7 | 1164 | 60 | 615 | 52.8000 | 0.0042 | -0.0647 | 0.0536 |
| suave | 8 | 1156 | 68 | 618 | 53.5000 | 0.0077 | -0.0681 | 0.0570 |
| suave | 9 | 1147 | 77 | 616 | 53.7000 | 0.0076 | -0.0572 | 0.0554 |
| suave | 10 | 1144 | 80 | 619 | 54.1000 | 0.0067 | -0.0606 | 0.0553 |
| suave | 11 | 1140 | 84 | 571 | 50.1000 | 0.0009 | -0.0611 | 0.0515 |
| suave | 12 | 1130 | 94 | 591 | 52.3000 | 0.0054 | -0.0643 | 0.0623 |

## ¿Paga elegir por serie? `mejora = wape(global) − wape(champion)`, positivo favorece a la selección

| cuadrante | horizonte | series | no_comparable | gana_retador | %_gana_retador | mejora_mediana | mejora_p25 | mejora_p75 |
|---|---|---|---|---|---|---|---|---|
| erratica | 1 | 239 | 0 | 113 | 47.3000 | -0.0064 | -0.1343 | 0.1286 |
| erratica | 2 | 239 | 0 | 94 | 39.3000 | -0.0413 | -0.1388 | 0.0886 |
| erratica | 3 | 239 | 0 | 113 | 47.3000 | -0.0127 | -0.1197 | 0.1186 |
| erratica | 4 | 239 | 0 | 120 | 50.2000 | 0.0049 | -0.1056 | 0.1647 |
| erratica | 5 | 239 | 0 | 131 | 54.8000 | 0.0175 | -0.1091 | 0.1994 |
| erratica | 6 | 239 | 0 | 129 | 54.0000 | 0.0240 | -0.0936 | 0.2365 |
| erratica | 7 | 239 | 0 | 132 | 55.2000 | 0.0382 | -0.0876 | 0.2361 |
| erratica | 8 | 237 | 2 | 134 | 56.5000 | 0.0529 | -0.0815 | 0.3131 |
| erratica | 9 | 236 | 3 | 141 | 59.7000 | 0.0275 | -0.0555 | 0.2488 |
| erratica | 10 | 236 | 3 | 132 | 55.9000 | 0.0322 | -0.0693 | 0.2996 |
| erratica | 11 | 235 | 4 | 135 | 57.4000 | 0.0393 | -0.0746 | 0.2579 |
| erratica | 12 | 231 | 8 | 128 | 55.4000 | 0.0363 | -0.0857 | 0.3204 |
| intermitente | 1 | 488 | 0 | 254 | 52.0000 | 2.1023 | 0.1744 | 5.4856 |
| intermitente | 2 | 479 | 9 | 268 | 55.9000 | 4.7168 | 0.6980 | 15.6222 |
| intermitente | 3 | 476 | 12 | 257 | 54.0000 | 4.8893 | 0.6464 | 18.4827 |
| intermitente | 4 | 476 | 12 | 247 | 51.9000 | 5.2091 | 0.7443 | 19.5267 |
| intermitente | 5 | 466 | 22 | 233 | 50.0000 | 5.2190 | 0.7812 | 19.3348 |
| intermitente | 6 | 460 | 28 | 217 | 47.2000 | 5.7664 | 0.6927 | 20.2527 |
| intermitente | 7 | 445 | 43 | 190 | 42.7000 | 6.3492 | 0.9203 | 25.7541 |
| intermitente | 8 | 437 | 51 | 163 | 37.3000 | 5.7542 | 0.8396 | 22.8453 |
| intermitente | 9 | 433 | 55 | 143 | 33.0000 | 4.1120 | 0.6818 | 20.7312 |
| intermitente | 10 | 427 | 61 | 127 | 29.7000 | 3.9733 | 0.6823 | 16.8187 |
| intermitente | 11 | 419 | 69 | 122 | 29.1000 | 4.0158 | 0.7268 | 15.0921 |
| intermitente | 12 | 407 | 81 | 113 | 27.8000 | 3.6692 | 0.6843 | 15.9075 |
| lumpy | 1 | 177 | 0 | 106 | 59.9000 | 0.7383 | 0.0003 | 2.3157 |
| lumpy | 2 | 177 | 0 | 105 | 59.3000 | 0.8328 | 0.0233 | 3.1682 |
| lumpy | 3 | 177 | 0 | 105 | 59.3000 | 1.0631 | 0.0283 | 3.7251 |
| lumpy | 4 | 177 | 0 | 105 | 59.3000 | 1.3305 | 0.0516 | 5.0755 |
| lumpy | 5 | 177 | 0 | 100 | 56.5000 | 1.3652 | 0.0030 | 5.1577 |
| lumpy | 6 | 175 | 2 | 108 | 61.7000 | 2.1823 | 0.2272 | 6.3701 |
| lumpy | 7 | 175 | 2 | 99 | 56.6000 | 2.0456 | 0.1556 | 5.6441 |
| lumpy | 8 | 174 | 3 | 92 | 52.9000 | 2.3339 | 0.0334 | 7.0859 |
| lumpy | 9 | 174 | 3 | 96 | 55.2000 | 2.6729 | 0.3272 | 6.5794 |
| lumpy | 10 | 174 | 3 | 84 | 48.3000 | 2.5968 | 0.0374 | 7.2312 |
| lumpy | 11 | 174 | 3 | 78 | 44.8000 | 2.2855 | 0.0287 | 9.1738 |
| lumpy | 12 | 173 | 4 | 81 | 46.8000 | 2.3100 | 0.1320 | 10.7382 |
| suave | 1 | 1202 | 22 | 513 | 42.7000 | -0.0085 | -0.0396 | 0.0333 |
| suave | 2 | 1196 | 28 | 463 | 38.7000 | -0.0141 | -0.0500 | 0.0255 |
| suave | 3 | 1193 | 31 | 526 | 44.1000 | -0.0090 | -0.0453 | 0.0408 |
| suave | 4 | 1192 | 32 | 518 | 43.5000 | -0.0097 | -0.0477 | 0.0497 |
| suave | 5 | 1185 | 39 | 529 | 44.6000 | -0.0094 | -0.0491 | 0.0551 |
| suave | 6 | 1171 | 53 | 539 | 46.0000 | -0.0068 | -0.0454 | 0.0539 |
| suave | 7 | 1164 | 60 | 555 | 47.7000 | -0.0037 | -0.0511 | 0.0669 |
| suave | 8 | 1156 | 68 | 551 | 47.7000 | -0.0053 | -0.0508 | 0.0654 |
| suave | 9 | 1147 | 77 | 525 | 45.8000 | -0.0062 | -0.0516 | 0.0555 |
| suave | 10 | 1144 | 80 | 528 | 46.2000 | -0.0055 | -0.0512 | 0.0594 |
| suave | 11 | 1140 | 84 | 573 | 50.3000 | 0.0005 | -0.0489 | 0.0592 |
| suave | 12 | 1130 | 94 | 529 | 46.8000 | -0.0067 | -0.0596 | 0.0593 |

## Modelo ganador del champion por cuadrante (pares serie×corte)

| modelo_ganador | erratica | intermitente | lumpy | suave | total |
|---|---|---|---|---|---|
| SeasonalNaive | 1061 | 5106 | 905 | 5967 | 13039 |
| CrostonSBA | 510 | 312 | 231 | 3778 | 4831 |
| WindowAverage | 342 | 1565 | 606 | 1289 | 3802 |
| GlobalLGBM_P50 | 542 | 755 | 472 | 1743 | 3512 |
| AutoARIMA | 572 | 542 | 574 | 1541 | 3229 |
| AutoETS | 384 | 103 | 103 | 2128 | 2718 |
| GlobalLGBM | 411 | 92 | 114 | 2081 | 2698 |
| AutoTheta | 310 | 103 | 101 | 2102 | 2616 |
| TSB | 170 | 123 | 78 | 1198 | 1569 |

## Modelo ganador del piso por cuadrante, para contrastar

| modelo_ganador | erratica | intermitente | lumpy | suave | total |
|---|---|---|---|---|---|
| SeasonalNaive | 1183 | 5195 | 975 | 6296 | 13649 |
| CrostonSBA | 645 | 373 | 296 | 4634 | 5948 |
| WindowAverage | 538 | 1900 | 767 | 1830 | 5035 |
| AutoARIMA | 710 | 681 | 694 | 1944 | 4029 |
| AutoTheta | 417 | 200 | 176 | 2705 | 3498 |
| AutoETS | 471 | 182 | 141 | 2557 | 3351 |
| TSB | 338 | 170 | 135 | 1861 | 2504 |

## Cambios de ganador del champion a lo largo de los cortes

| cambios | n_series | % |
|---|---|---|
| 0 | 335 | 15.7000 |
| 1 | 153 | 7.2000 |
| 2 | 58 | 2.7000 |
| 3 | 72 | 3.4000 |
| 4 | 89 | 4.2000 |
| 5 | 145 | 6.8000 |
| 6 | 143 | 6.7000 |
| 7 | 168 | 7.9000 |
| 8 | 188 | 8.8000 |
| 9 | 218 | 10.2000 |
| 10 | 179 | 8.4000 |
| 11 | 140 | 6.6000 |
| 12 | 115 | 5.4000 |
| 13 | 70 | 3.3000 |
| 14 | 35 | 1.6000 |
| 15 | 14 | 0.7000 |
| 16 | 4 | 0.2000 |
| 17 | 2 | 0.1000 |

## Origen de cada predicción del champion (ganador / cascada / nadie)

| origen | filas | % |
|---|---|---|
| ganador del corte | 284574 | 93.2100 |
| sin predicción (ningún candidato) | 12700 | 4.1600 |
| cascada | 8035 | 2.6300 |

## Por nivel de agregación y horizonte

| nivel | horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|---|
| producto | 1 | 0.3230 | -0.0009 | 36003 | 0.9927 |
| producto | 3 | 0.3667 | 0.0139 | 32235 | 0.9786 |
| producto | 6 | 0.3928 | 0.0013 | 26513 | 0.9546 |
| producto | 12 | 0.3644 | 0.0359 | 14606 | 0.9104 |
| categoria | 1 | 0.1428 | -0.0031 | 216 | 1.0000 |
| categoria | 3 | 0.1648 | 0.0077 | 192 | 1.0000 |
| categoria | 6 | 0.2010 | -0.0149 | 156 | 1.0000 |
| categoria | 12 | 0.1754 | -0.0082 | 84 | 1.0000 |
| total | 1 | 0.1088 | -0.0031 | 18 | 1.0000 |
| total | 3 | 0.1294 | 0.0077 | 16 | 1.0000 |
| total | 6 | 0.1458 | -0.0149 | 13 | 1.0000 |
| total | 12 | 0.0881 | -0.0082 | 7 | 1.0000 |

## Por horizonte (grano producto)

| horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|
| 1 | 0.3230 | -0.0009 | 36003 | 0.9927 |
| 3 | 0.3667 | 0.0139 | 32235 | 0.9786 |
| 6 | 0.3928 | 0.0013 | 26513 | 0.9546 |
| 12 | 0.3644 | 0.0359 | 14606 | 0.9104 |

## Por categoría y horizonte

| categoria | horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|---|
| ACCESORIO | 1 | 1.0519 | -0.0651 | 342 | 1.0000 |
| ACCESORIO | 3 | 0.9067 | -0.3040 | 304 | 1.0000 |
| ACCESORIO | 6 | 0.9266 | -0.4926 | 247 | 1.0000 |
| ACCESORIO | 12 | 1.0151 | -0.7055 | 133 | 1.0000 |
| ALIMENTO | 1 | 0.3126 | 0.0278 | 828 | 1.0000 |
| ALIMENTO | 3 | 0.2649 | -0.0346 | 736 | 1.0000 |
| ALIMENTO | 6 | 0.3005 | -0.0677 | 598 | 1.0000 |
| ALIMENTO | 12 | 0.3207 | -0.1153 | 322 | 1.0000 |
| ANTIARTROSICO | 1 | 0.2448 | -0.0598 | 774 | 1.0000 |
| ANTIARTROSICO | 3 | 0.2596 | -0.0962 | 688 | 1.0000 |
| ANTIARTROSICO | 6 | 0.2631 | -0.1362 | 559 | 1.0000 |
| ANTIARTROSICO | 12 | 0.3039 | -0.2043 | 301 | 1.0000 |
| ANTIPARASITARIO EXTERNO | 1 | 0.3595 | 0.0321 | 6284 | 0.9946 |
| ANTIPARASITARIO EXTERNO | 3 | 0.4277 | 0.0757 | 5617 | 0.9849 |
| ANTIPARASITARIO EXTERNO | 6 | 0.4513 | 0.0740 | 4606 | 0.9674 |
| ANTIPARASITARIO EXTERNO | 12 | 0.3833 | 0.2080 | 2508 | 0.9358 |
| ANTIPARASITARIO INTERNO | 1 | 0.2510 | 0.0261 | 2448 | 1.0000 |
| ANTIPARASITARIO INTERNO | 3 | 0.2446 | 0.0266 | 2176 | 1.0000 |
| ANTIPARASITARIO INTERNO | 6 | 0.2779 | 0.0420 | 1768 | 1.0000 |
| ANTIPARASITARIO INTERNO | 12 | 0.2919 | 0.0426 | 952 | 1.0000 |
| BIOLOGICO | 1 | 0.3492 | -0.0054 | 778 | 0.9987 |
| BIOLOGICO | 3 | 0.4170 | -0.0029 | 692 | 0.9957 |
| BIOLOGICO | 6 | 0.4764 | -0.0402 | 563 | 0.9929 |
| BIOLOGICO | 12 | 0.5116 | -0.0938 | 305 | 0.9869 |
| CARDIOLOGICO | 1 | 0.1794 | -0.0281 | 1134 | 1.0000 |
| CARDIOLOGICO | 3 | 0.1930 | -0.0358 | 1008 | 1.0000 |
| CARDIOLOGICO | 6 | 0.2072 | -0.0592 | 819 | 1.0000 |
| CARDIOLOGICO | 12 | 0.2322 | -0.1199 | 441 | 1.0000 |
| CLINICO | 1 | 0.2418 | -0.0388 | 13070 | 0.9995 |
| CLINICO | 3 | 0.2546 | -0.0547 | 11626 | 0.9985 |
| CLINICO | 6 | 0.2717 | -0.0702 | 9452 | 0.9970 |
| CLINICO | 12 | 0.2819 | -0.1092 | 5096 | 0.9939 |
| DESCARTABLES | 1 | 0.4014 | 0.0606 | 936 | 1.0000 |
| DESCARTABLES | 3 | 0.3688 | 0.0306 | 832 | 1.0000 |
| DESCARTABLES | 6 | 0.4091 | 0.0346 | 676 | 1.0000 |
| DESCARTABLES | 12 | 0.5135 | 0.0470 | 364 | 1.0000 |
| HIGIENE Y BELLEZA | 1 | 0.2424 | -0.0269 | 3888 | 1.0000 |
| HIGIENE Y BELLEZA | 3 | 0.2624 | -0.0282 | 3456 | 1.0000 |
| HIGIENE Y BELLEZA | 6 | 0.2966 | -0.0347 | 2808 | 1.0000 |
| HIGIENE Y BELLEZA | 12 | 0.2668 | -0.0822 | 1512 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 1 | 0.2598 | -0.0780 | 18 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 3 | 0.3000 | -0.1056 | 16 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 6 | 0.3500 | -0.1712 | 13 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 12 | 0.3806 | -0.3043 | 7 | 1.0000 |
| SIN CATEGORIA | 1 | 0.5236 | -0.1915 | 5503 | 0.9598 |
| SIN CATEGORIA | 3 | 0.5264 | -0.1931 | 5084 | 0.8849 |
| SIN CATEGORIA | 6 | 0.4911 | -0.2409 | 4404 | 0.7677 |
| SIN CATEGORIA | 12 | 0.3776 | -0.2367 | 2665 | 0.5824 |

## Por cuadrante de intermitencia y horizonte

| cuadrante | horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|---|
| erratica | 1 | 0.4585 | 0.0264 | 4221 | 0.9955 |
| erratica | 3 | 0.5573 | 0.0350 | 3772 | 0.9873 |
| erratica | 6 | 0.6341 | -0.0398 | 3087 | 0.9741 |
| erratica | 12 | 0.5575 | -0.0084 | 1673 | 0.9474 |
| intermitente | 1 | 0.9149 | 0.1779 | 7867 | 0.9865 |
| intermitente | 3 | 0.9007 | 0.1554 | 7093 | 0.9578 |
| intermitente | 6 | 1.2150 | 0.4284 | 5901 | 0.9110 |
| intermitente | 12 | 1.3426 | 0.6131 | 3333 | 0.8266 |
| lumpy | 1 | 1.2073 | 0.3744 | 3142 | 0.9981 |
| lumpy | 3 | 1.5816 | 0.6730 | 2798 | 0.9943 |
| lumpy | 6 | 2.0069 | 0.8989 | 2281 | 0.9868 |
| lumpy | 12 | 2.7709 | 1.6158 | 1237 | 0.9741 |
| suave | 1 | 0.2954 | -0.0075 | 20773 | 0.9937 |
| suave | 3 | 0.3309 | 0.0077 | 18572 | 0.9823 |
| suave | 6 | 0.3466 | 0.0029 | 15244 | 0.9626 |
| suave | 12 | 0.3229 | 0.0367 | 8363 | 0.9269 |
