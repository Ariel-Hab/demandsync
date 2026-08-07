# Selección por (cuadrante, corte) contra por (serie, corte) — real (2026-08-07)

M3.1a (`roadmap-motor.md` §7.1). **Ningún modelo se reajustó**: la tabla sale de cruzar los checkpoints de dos corridas que comparten `id` y de reelegir sobre predicciones ya calculadas.

- **Productos:** 2128 de 2128 · **cortes:** 18 · **horizonte:** 12 · **filas cruzadas:** 305309 · **137.5 s**
- **Candidatos:** 7 baselines + `GlobalLGBM` + `GlobalLGBM_P50`, los mismos 9 de M2.5.
- **Los cuatro contendientes usan la misma regla de observabilidad** (ADR-016): en el corte `t` solo entra el error de las filas cuyo mes ya ocurrió. Lo único que cambia entre `champion` y `champion_cuadrante` es **con cuánta evidencia se rankea**: ~2.100 decisiones por corte contra ~5.
- **El cuadrante se calcula con `hasta=corte`** (`clasificacion.clasificar_por_corte`). Con el default —último mes de los datos— la decisión miraría el futuro (§12.2).
- **`sin_actividad` es un grupo más**, con su propio ranking aprendido: mandarlo a una regla fija sería el enrutamiento por teoría que M1.7 midió peor.
- **El `champion` se recalcula acá**, no se lee de `global-vs-baselines-real-2026-08-06.md`: el gate compara fila a fila dentro de una misma corrida, que es la disciplina de §5.6.2.

> **El gate de M3.1a pide los cuatro horizontes.** `champion_cuadrante` se adopta solo si le gana al `champion` en WAPE producto a h=1/3/6/12 **y** mantiene el sesgo total dentro del ±5% (ADR-008). Ganar en algunos y perder en otros es resultado negativo: elegir el criterio por horizonte mirando esta tabla es el hindsight que ADR-016 sacó del piso.

> **Ninguna decisión se toma con el agregado.** El WAPE total es 86% del cuadrante `suave` (M2.5, §6.7), así que la tabla que manda es *Veredicto por cuadrante*, con su columna `peso_%`.

> **Solo se comparan las celdas donde los contendientes tienen la misma cobertura.** Una serie no predicha puntúa WAPE 0,0 —perfecto— y solo `cobertura` lo delata.

## Corrida

| id | fecha_ejecucion | n_cortes | horizonte_max | columnas_id | columna_objetivo | densificado | primer_corte | ultimo_corte | datos_filas | datos_series | datos_primer_mes | datos_ultimo_mes | datos_suma_objetivo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a79a9b23676b | 2026-08-07 | 18 | 12 | ('id_producto',) | unidades | True | 2024-11-01 | 2026-04-01 | 157431 | 2128 | 2018-07-01 | 2026-05-01 | 31122141.0000 |

## Cabeza a cabeza por nivel y horizonte (M2.5) — **solo se comparan WAPE con la misma `cobertura`**

| contendiente | nivel | horizonte | wape | n | cobertura | sesgo |
|---|---|---|---|---|---|---|
| piso | producto | 1 | 0.3305 | 36003 | 0.9927 | 0.0099 |
| global | producto | 1 | 0.2953 | 36003 | 0.9927 | -0.0040 |
| champion | producto | 1 | 0.3230 | 36003 | 0.9927 | -0.0009 |
| champion_cuadrante | producto | 1 | 0.3182 | 36003 | 0.9927 | -0.0038 |
| piso | producto | 3 | 0.3767 | 32235 | 0.9786 | 0.0266 |
| global | producto | 3 | 0.3435 | 32235 | 0.9786 | 0.0074 |
| champion | producto | 3 | 0.3667 | 32235 | 0.9786 | 0.0139 |
| champion_cuadrante | producto | 3 | 0.3940 | 32235 | 0.9786 | 0.0141 |
| piso | producto | 6 | 0.4001 | 26513 | 0.9546 | 0.0061 |
| global | producto | 6 | 0.3834 | 26513 | 0.9546 | 0.0097 |
| champion | producto | 6 | 0.3928 | 26513 | 0.9546 | 0.0013 |
| champion_cuadrante | producto | 6 | 0.4164 | 26513 | 0.9546 | -0.0439 |
| piso | producto | 12 | 0.3699 | 14606 | 0.9104 | 0.0351 |
| global | producto | 12 | 0.3746 | 14606 | 0.9104 | 0.0258 |
| champion | producto | 12 | 0.3644 | 14606 | 0.9104 | 0.0359 |
| champion_cuadrante | producto | 12 | 0.3795 | 14606 | 0.9104 | 0.0482 |
| piso | categoria | 1 | 0.1509 | 216 | 1.0000 | 0.0077 |
| global | categoria | 1 | 0.1208 | 216 | 1.0000 | -0.0062 |
| champion | categoria | 1 | 0.1428 | 216 | 1.0000 | -0.0031 |
| champion_cuadrante | categoria | 1 | 0.1631 | 216 | 1.0000 | -0.0060 |
| piso | categoria | 3 | 0.1701 | 192 | 1.0000 | 0.0203 |
| global | categoria | 3 | 0.1428 | 192 | 1.0000 | 0.0011 |
| champion | categoria | 3 | 0.1648 | 192 | 1.0000 | 0.0077 |
| champion_cuadrante | categoria | 3 | 0.2481 | 192 | 1.0000 | 0.0079 |
| piso | categoria | 6 | 0.2063 | 156 | 1.0000 | -0.0100 |
| global | categoria | 6 | 0.1831 | 156 | 1.0000 | -0.0065 |
| champion | categoria | 6 | 0.2010 | 156 | 1.0000 | -0.0149 |
| champion_cuadrante | categoria | 6 | 0.2632 | 156 | 1.0000 | -0.0600 |
| piso | categoria | 12 | 0.1787 | 84 | 1.0000 | -0.0090 |
| global | categoria | 12 | 0.1503 | 84 | 1.0000 | -0.0183 |
| champion | categoria | 12 | 0.1754 | 84 | 1.0000 | -0.0082 |
| champion_cuadrante | categoria | 12 | 0.1919 | 84 | 1.0000 | 0.0041 |
| piso | total | 1 | 0.1205 | 18 | 1.0000 | 0.0077 |
| global | total | 1 | 0.0934 | 18 | 1.0000 | -0.0062 |
| champion | total | 1 | 0.1088 | 18 | 1.0000 | -0.0031 |
| champion_cuadrante | total | 1 | 0.1311 | 18 | 1.0000 | -0.0060 |
| piso | total | 3 | 0.1390 | 16 | 1.0000 | 0.0203 |
| global | total | 3 | 0.0906 | 16 | 1.0000 | 0.0011 |
| champion | total | 3 | 0.1294 | 16 | 1.0000 | 0.0077 |
| champion_cuadrante | total | 3 | 0.2158 | 16 | 1.0000 | 0.0079 |
| piso | total | 6 | 0.1575 | 13 | 1.0000 | -0.0100 |
| global | total | 6 | 0.1164 | 13 | 1.0000 | -0.0065 |
| champion | total | 6 | 0.1458 | 13 | 1.0000 | -0.0149 |
| champion_cuadrante | total | 6 | 0.2204 | 13 | 1.0000 | -0.0600 |
| piso | total | 12 | 0.0867 | 7 | 1.0000 | -0.0090 |
| global | total | 12 | 0.0811 | 7 | 1.0000 | -0.0183 |
| champion | total | 12 | 0.0881 | 7 | 1.0000 | -0.0082 |
| champion_cuadrante | total | 12 | 0.1022 | 7 | 1.0000 | 0.0041 |

## Cabeza a cabeza **por cuadrante** (grano producto) — leer con la columna `peso_%`: es cuánto pesa cada cuadrante en el WAPE agregado de arriba

| contendiente | cuadrante | horizonte | wape | n | cobertura | sesgo | peso_% |
|---|---|---|---|---|---|---|---|
| piso | erratica | 1 | 0.4748 | 4221 | 0.9955 | 0.0390 | 13.3324 |
| global | erratica | 1 | 0.4426 | 4221 | 0.9955 | 0.0220 | 13.3324 |
| champion | erratica | 1 | 0.4585 | 4221 | 0.9955 | 0.0264 | 13.3324 |
| champion_cuadrante | erratica | 1 | 0.4701 | 4221 | 0.9955 | -0.0500 | 13.3324 |
| piso | erratica | 3 | 0.5764 | 3772 | 0.9873 | 0.0571 | 13.0671 |
| global | erratica | 3 | 0.5247 | 3772 | 0.9873 | 0.0240 | 13.0671 |
| champion | erratica | 3 | 0.5573 | 3772 | 0.9873 | 0.0350 | 13.0671 |
| champion_cuadrante | erratica | 3 | 0.6008 | 3772 | 0.9873 | -0.0437 | 13.0671 |
| piso | erratica | 6 | 0.6400 | 3087 | 0.9741 | -0.0411 | 13.3105 |
| global | erratica | 6 | 0.6174 | 3087 | 0.9741 | 0.0167 | 13.3105 |
| champion | erratica | 6 | 0.6341 | 3087 | 0.9741 | -0.0398 | 13.3105 |
| champion_cuadrante | erratica | 6 | 0.6392 | 3087 | 0.9741 | -0.1218 | 13.3105 |
| piso | erratica | 12 | 0.5535 | 1673 | 0.9474 | -0.0322 | 13.8407 |
| global | erratica | 12 | 0.5789 | 1673 | 0.9474 | 0.0496 | 13.8407 |
| champion | erratica | 12 | 0.5575 | 1673 | 0.9474 | -0.0084 | 13.8407 |
| champion_cuadrante | erratica | 12 | 0.5740 | 1673 | 0.9474 | -0.0483 | 13.8407 |
| piso | intermitente | 1 | 0.9616 | 7867 | 0.9865 | 0.2107 | 0.4634 |
| global | intermitente | 1 | 0.9603 | 7867 | 0.9865 | 0.4574 | 0.4634 |
| champion | intermitente | 1 | 0.9149 | 7867 | 0.9865 | 0.1779 | 0.4634 |
| champion_cuadrante | intermitente | 1 | 1.1153 | 7867 | 0.9865 | -0.0954 | 0.4634 |
| piso | intermitente | 3 | 0.9381 | 7093 | 0.9578 | 0.1838 | 0.4604 |
| global | intermitente | 3 | 1.8750 | 7093 | 0.9578 | 1.3699 | 0.4604 |
| champion | intermitente | 3 | 0.9007 | 7093 | 0.9578 | 0.1554 | 0.4604 |
| champion_cuadrante | intermitente | 3 | 1.1541 | 7093 | 0.9578 | -0.1750 | 0.4604 |
| piso | intermitente | 6 | 1.1460 | 5901 | 0.9110 | 0.3370 | 0.4332 |
| global | intermitente | 6 | 2.7000 | 5901 | 0.9110 | 2.2977 | 0.4332 |
| champion | intermitente | 6 | 1.2150 | 5901 | 0.9110 | 0.4284 | 0.4332 |
| champion_cuadrante | intermitente | 6 | 1.3829 | 5901 | 0.9110 | -0.0748 | 0.4332 |
| piso | intermitente | 12 | 1.2254 | 3333 | 0.8266 | 0.3646 | 0.4002 |
| global | intermitente | 12 | 3.4260 | 3333 | 0.8266 | 3.0806 | 0.4002 |
| champion | intermitente | 12 | 1.3426 | 3333 | 0.8266 | 0.6131 | 0.4002 |
| champion_cuadrante | intermitente | 12 | 1.8569 | 3333 | 0.8266 | -0.0994 | 0.4002 |
| piso | lumpy | 1 | 1.2052 | 3142 | 0.9981 | 0.3596 | 0.3269 |
| global | lumpy | 1 | 1.1783 | 3142 | 0.9981 | 0.5914 | 0.3269 |
| champion | lumpy | 1 | 1.2073 | 3142 | 0.9981 | 0.3744 | 0.3269 |
| champion_cuadrante | lumpy | 1 | 1.0714 | 3142 | 0.9981 | 0.2506 | 0.3269 |
| piso | lumpy | 3 | 1.5863 | 2798 | 0.9943 | 0.6532 | 0.2905 |
| global | lumpy | 3 | 2.0442 | 2798 | 0.9943 | 1.4522 | 0.2905 |
| champion | lumpy | 3 | 1.5816 | 2798 | 0.9943 | 0.6730 | 0.2905 |
| champion_cuadrante | lumpy | 3 | 1.3387 | 2798 | 0.9943 | 0.3826 | 0.2905 |
| piso | lumpy | 6 | 1.9245 | 2281 | 0.9868 | 0.7809 | 0.2519 |
| global | lumpy | 6 | 3.0773 | 2281 | 0.9868 | 2.4415 | 0.2519 |
| champion | lumpy | 6 | 2.0069 | 2281 | 0.9868 | 0.8989 | 0.2519 |
| champion_cuadrante | lumpy | 6 | 1.8318 | 2281 | 0.9868 | 0.6669 | 0.2519 |
| piso | lumpy | 12 | 2.5491 | 1237 | 0.9741 | 1.3620 | 0.2008 |
| global | lumpy | 12 | 5.6294 | 1237 | 0.9741 | 5.1088 | 0.2008 |
| champion | lumpy | 12 | 2.7709 | 1237 | 0.9741 | 1.6158 | 0.2008 |
| champion_cuadrante | lumpy | 12 | 2.8486 | 1237 | 0.9741 | 1.6715 | 0.2008 |
| piso | suave | 1 | 0.3013 | 20773 | 0.9937 | 0.0030 | 85.8774 |
| global | suave | 1 | 0.2654 | 20773 | 0.9937 | -0.0128 | 85.8774 |
| champion | suave | 1 | 0.2954 | 20773 | 0.9937 | -0.0075 | 85.8774 |
| champion_cuadrante | suave | 1 | 0.2875 | 20773 | 0.9937 | 0.0029 | 85.8774 |
| piso | suave | 3 | 0.3393 | 18572 | 0.9823 | 0.0190 | 86.1820 |
| global | suave | 3 | 0.3022 | 18572 | 0.9823 | -0.0073 | 86.1820 |
| champion | suave | 3 | 0.3309 | 18572 | 0.9823 | 0.0077 | 86.1820 |
| champion_cuadrante | suave | 3 | 0.3554 | 18572 | 0.9823 | 0.0227 | 86.1820 |
| piso | suave | 6 | 0.3547 | 15244 | 0.9626 | 0.0095 | 86.0043 |
| global | suave | 6 | 0.3276 | 15244 | 0.9626 | -0.0101 | 86.0043 |
| champion | suave | 6 | 0.3466 | 15244 | 0.9626 | 0.0029 | 86.0043 |
| champion_cuadrante | suave | 6 | 0.3729 | 15244 | 0.9626 | -0.0337 | 86.0043 |
| piso | suave | 12 | 0.3310 | 8363 | 0.9269 | 0.0413 | 85.5582 |
| global | suave | 12 | 0.3149 | 8363 | 0.9269 | -0.0043 | 85.5582 |
| champion | suave | 12 | 0.3229 | 8363 | 0.9269 | 0.0367 | 85.5582 |
| champion_cuadrante | suave | 12 | 0.3353 | 8363 | 0.9269 | 0.0607 | 85.5582 |

## Por nivel de agregación y horizonte

| nivel | horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|---|
| producto | 1 | 0.3182 | -0.0038 | 36003 | 0.9927 |
| producto | 3 | 0.3940 | 0.0141 | 32235 | 0.9786 |
| producto | 6 | 0.4164 | -0.0439 | 26513 | 0.9546 |
| producto | 12 | 0.3795 | 0.0482 | 14606 | 0.9104 |
| categoria | 1 | 0.1631 | -0.0060 | 216 | 1.0000 |
| categoria | 3 | 0.2481 | 0.0079 | 192 | 1.0000 |
| categoria | 6 | 0.2632 | -0.0600 | 156 | 1.0000 |
| categoria | 12 | 0.1919 | 0.0041 | 84 | 1.0000 |
| total | 1 | 0.1311 | -0.0060 | 18 | 1.0000 |
| total | 3 | 0.2158 | 0.0079 | 16 | 1.0000 |
| total | 6 | 0.2204 | -0.0600 | 13 | 1.0000 |
| total | 12 | 0.1022 | 0.0041 | 7 | 1.0000 |

## Por horizonte (grano producto)

| horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|
| 1 | 0.3182 | -0.0038 | 36003 | 0.9927 |
| 3 | 0.3940 | 0.0141 | 32235 | 0.9786 |
| 6 | 0.4164 | -0.0439 | 26513 | 0.9546 |
| 12 | 0.3795 | 0.0482 | 14606 | 0.9104 |

## Por categoría y horizonte

| categoria | horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|---|
| ACCESORIO | 1 | 1.0724 | -0.0817 | 342 | 1.0000 |
| ACCESORIO | 3 | 1.0653 | -0.3073 | 304 | 1.0000 |
| ACCESORIO | 6 | 1.0299 | -0.5618 | 247 | 1.0000 |
| ACCESORIO | 12 | 0.9956 | -0.6969 | 133 | 1.0000 |
| ALIMENTO | 1 | 0.2941 | 0.0579 | 828 | 1.0000 |
| ALIMENTO | 3 | 0.2560 | -0.0259 | 736 | 1.0000 |
| ALIMENTO | 6 | 0.2870 | -0.0611 | 598 | 1.0000 |
| ALIMENTO | 12 | 0.2956 | -0.0659 | 322 | 1.0000 |
| ANTIARTROSICO | 1 | 0.2295 | -0.0376 | 774 | 1.0000 |
| ANTIARTROSICO | 3 | 0.2549 | -0.0875 | 688 | 1.0000 |
| ANTIARTROSICO | 6 | 0.2712 | -0.1575 | 559 | 1.0000 |
| ANTIARTROSICO | 12 | 0.3050 | -0.1985 | 301 | 1.0000 |
| ANTIPARASITARIO EXTERNO | 1 | 0.3562 | 0.0171 | 6284 | 0.9946 |
| ANTIPARASITARIO EXTERNO | 3 | 0.4720 | 0.0697 | 5617 | 0.9849 |
| ANTIPARASITARIO EXTERNO | 6 | 0.4816 | 0.0156 | 4606 | 0.9674 |
| ANTIPARASITARIO EXTERNO | 12 | 0.4110 | 0.2366 | 2508 | 0.9358 |
| ANTIPARASITARIO INTERNO | 1 | 0.2491 | 0.0324 | 2448 | 1.0000 |
| ANTIPARASITARIO INTERNO | 3 | 0.2510 | 0.0505 | 2176 | 1.0000 |
| ANTIPARASITARIO INTERNO | 6 | 0.2767 | 0.0314 | 1768 | 1.0000 |
| ANTIPARASITARIO INTERNO | 12 | 0.2791 | 0.0593 | 952 | 1.0000 |
| BIOLOGICO | 1 | 0.3567 | -0.0056 | 778 | 0.9987 |
| BIOLOGICO | 3 | 0.4290 | 0.0045 | 692 | 0.9957 |
| BIOLOGICO | 6 | 0.4913 | -0.0567 | 563 | 0.9929 |
| BIOLOGICO | 12 | 0.5280 | -0.0873 | 305 | 0.9869 |
| CARDIOLOGICO | 1 | 0.1778 | 0.0035 | 1134 | 1.0000 |
| CARDIOLOGICO | 3 | 0.1782 | -0.0170 | 1008 | 1.0000 |
| CARDIOLOGICO | 6 | 0.1989 | -0.0572 | 819 | 1.0000 |
| CARDIOLOGICO | 12 | 0.2181 | -0.1017 | 441 | 1.0000 |
| CLINICO | 1 | 0.2313 | -0.0318 | 13070 | 0.9995 |
| CLINICO | 3 | 0.2595 | -0.0532 | 11626 | 0.9985 |
| CLINICO | 6 | 0.2882 | -0.1058 | 9452 | 0.9970 |
| CLINICO | 12 | 0.2778 | -0.1132 | 5096 | 0.9939 |
| DESCARTABLES | 1 | 0.3987 | 0.0606 | 936 | 1.0000 |
| DESCARTABLES | 3 | 0.3614 | 0.0446 | 832 | 1.0000 |
| DESCARTABLES | 6 | 0.3981 | 0.0284 | 676 | 1.0000 |
| DESCARTABLES | 12 | 0.5034 | 0.0593 | 364 | 1.0000 |
| HIGIENE Y BELLEZA | 1 | 0.2530 | -0.0083 | 3888 | 1.0000 |
| HIGIENE Y BELLEZA | 3 | 0.3132 | 0.0004 | 3456 | 1.0000 |
| HIGIENE Y BELLEZA | 6 | 0.3343 | -0.0656 | 2808 | 1.0000 |
| HIGIENE Y BELLEZA | 12 | 0.2691 | -0.0796 | 1512 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 1 | 0.2524 | -0.0804 | 18 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 3 | 0.2620 | -0.1330 | 16 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 6 | 0.3342 | -0.2442 | 13 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 12 | 0.3746 | -0.2624 | 7 | 1.0000 |
| SIN CATEGORIA | 1 | 0.4624 | -0.1832 | 5503 | 0.9598 |
| SIN CATEGORIA | 3 | 0.5701 | -0.2423 | 5084 | 0.8849 |
| SIN CATEGORIA | 6 | 0.5539 | -0.3913 | 4404 | 0.7677 |
| SIN CATEGORIA | 12 | 0.4289 | -0.2873 | 2665 | 0.5824 |

## Por cuadrante de intermitencia y horizonte

| cuadrante | horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|---|
| erratica | 1 | 0.4701 | -0.0500 | 4221 | 0.9955 |
| erratica | 3 | 0.6008 | -0.0437 | 3772 | 0.9873 |
| erratica | 6 | 0.6392 | -0.1218 | 3087 | 0.9741 |
| erratica | 12 | 0.5740 | -0.0483 | 1673 | 0.9474 |
| intermitente | 1 | 1.1153 | -0.0954 | 7867 | 0.9865 |
| intermitente | 3 | 1.1541 | -0.1750 | 7093 | 0.9578 |
| intermitente | 6 | 1.3829 | -0.0748 | 5901 | 0.9110 |
| intermitente | 12 | 1.8569 | -0.0994 | 3333 | 0.8266 |
| lumpy | 1 | 1.0714 | 0.2506 | 3142 | 0.9981 |
| lumpy | 3 | 1.3387 | 0.3826 | 2798 | 0.9943 |
| lumpy | 6 | 1.8318 | 0.6669 | 2281 | 0.9868 |
| lumpy | 12 | 2.8486 | 1.6715 | 1237 | 0.9741 |
| suave | 1 | 0.2875 | 0.0029 | 20773 | 0.9937 |
| suave | 3 | 0.3554 | 0.0227 | 18572 | 0.9823 |
| suave | 6 | 0.3729 | -0.0337 | 15244 | 0.9626 |
| suave | 12 | 0.3353 | 0.0607 | 8363 | 0.9269 |

## mejora_cuadrante_vs_champion

| cuadrante | horizonte | series | no_comparable | gana_retador | %_gana_retador | mejora_mediana | mejora_p25 | mejora_p75 |
|---|---|---|---|---|---|---|---|---|
| erratica | 1 | 239 | 0 | 139 | 58.2000 | 0.0164 | -0.0547 | 0.0836 |
| erratica | 2 | 239 | 0 | 132 | 55.2000 | 0.0216 | -0.0599 | 0.0803 |
| erratica | 3 | 239 | 0 | 127 | 53.1000 | 0.0067 | -0.0737 | 0.0906 |
| erratica | 4 | 239 | 0 | 115 | 48.1000 | -0.0081 | -0.0997 | 0.0930 |
| erratica | 5 | 239 | 0 | 122 | 51.0000 | 0.0061 | -0.1010 | 0.1134 |
| erratica | 6 | 239 | 0 | 137 | 57.3000 | 0.0211 | -0.0742 | 0.1440 |
| erratica | 7 | 239 | 0 | 139 | 58.2000 | 0.0279 | -0.0663 | 0.1505 |
| erratica | 8 | 237 | 2 | 136 | 57.4000 | 0.0165 | -0.0652 | 0.1382 |
| erratica | 9 | 236 | 3 | 131 | 55.5000 | 0.0142 | -0.0652 | 0.1261 |
| erratica | 10 | 236 | 3 | 118 | 50.0000 | 0.0006 | -0.0874 | 0.0893 |
| erratica | 11 | 235 | 4 | 115 | 48.9000 | -0.0039 | -0.0965 | 0.0822 |
| erratica | 12 | 231 | 8 | 116 | 50.2000 | 0.0024 | -0.1260 | 0.0719 |
| intermitente | 1 | 488 | 0 | 206 | 42.2000 | 0.1582 | -0.0585 | 1.2831 |
| intermitente | 2 | 479 | 9 | 161 | 33.6000 | 0.0279 | -0.0567 | 0.3818 |
| intermitente | 3 | 476 | 12 | 158 | 33.2000 | 0.0523 | -0.0377 | 0.3967 |
| intermitente | 4 | 476 | 12 | 185 | 38.9000 | 0.1731 | 0.0000 | 0.6250 |
| intermitente | 5 | 466 | 22 | 158 | 33.9000 | 0.1635 | -0.0050 | 0.6004 |
| intermitente | 6 | 460 | 28 | 156 | 33.9000 | 0.1667 | 0.0000 | 0.7127 |
| intermitente | 7 | 445 | 43 | 135 | 30.3000 | 0.2132 | -0.0026 | 0.6586 |
| intermitente | 8 | 437 | 51 | 113 | 25.9000 | 0.1129 | -0.0351 | 0.5147 |
| intermitente | 9 | 433 | 55 | 93 | 21.5000 | 0.0613 | -0.0402 | 0.3443 |
| intermitente | 10 | 427 | 61 | 79 | 18.5000 | 0.0055 | -0.0383 | 0.3333 |
| intermitente | 11 | 419 | 69 | 72 | 17.2000 | 0.0008 | -0.0619 | 0.3154 |
| intermitente | 12 | 407 | 81 | 52 | 12.8000 | 0.0000 | -0.1064 | 0.2338 |
| lumpy | 1 | 177 | 0 | 85 | 48.0000 | 0.0508 | -0.1203 | 0.3347 |
| lumpy | 2 | 177 | 0 | 87 | 49.2000 | 0.0910 | -0.0886 | 0.3422 |
| lumpy | 3 | 177 | 0 | 84 | 47.5000 | 0.0801 | -0.1026 | 0.3648 |
| lumpy | 4 | 177 | 0 | 82 | 46.3000 | 0.0751 | -0.1150 | 0.4075 |
| lumpy | 5 | 177 | 0 | 76 | 42.9000 | 0.0923 | -0.1462 | 0.5037 |
| lumpy | 6 | 175 | 2 | 70 | 40.0000 | 0.0261 | -0.2124 | 0.3857 |
| lumpy | 7 | 175 | 2 | 74 | 42.3000 | 0.0635 | -0.1321 | 0.5603 |
| lumpy | 8 | 174 | 3 | 76 | 43.7000 | 0.0987 | -0.0933 | 0.6703 |
| lumpy | 9 | 174 | 3 | 67 | 38.5000 | 0.0549 | -0.1237 | 0.3622 |
| lumpy | 10 | 174 | 3 | 63 | 36.2000 | 0.0819 | -0.1196 | 0.5123 |
| lumpy | 11 | 174 | 3 | 62 | 35.6000 | 0.0377 | -0.1194 | 0.4934 |
| lumpy | 12 | 173 | 4 | 56 | 32.4000 | 0.0587 | -0.1200 | 0.3335 |
| suave | 1 | 1202 | 22 | 769 | 64.0000 | 0.0122 | -0.0106 | 0.0422 |
| suave | 2 | 1196 | 28 | 688 | 57.5000 | 0.0072 | -0.0221 | 0.0336 |
| suave | 3 | 1193 | 31 | 630 | 52.8000 | 0.0035 | -0.0258 | 0.0355 |
| suave | 4 | 1192 | 32 | 654 | 54.9000 | 0.0054 | -0.0262 | 0.0391 |
| suave | 5 | 1185 | 39 | 638 | 53.8000 | 0.0049 | -0.0320 | 0.0403 |
| suave | 6 | 1171 | 53 | 607 | 51.8000 | 0.0023 | -0.0342 | 0.0400 |
| suave | 7 | 1164 | 60 | 671 | 57.6000 | 0.0095 | -0.0310 | 0.0502 |
| suave | 8 | 1156 | 68 | 609 | 52.7000 | 0.0040 | -0.0331 | 0.0458 |
| suave | 9 | 1147 | 77 | 616 | 53.7000 | 0.0055 | -0.0317 | 0.0529 |
| suave | 10 | 1144 | 80 | 623 | 54.5000 | 0.0062 | -0.0335 | 0.0482 |
| suave | 11 | 1140 | 84 | 608 | 53.3000 | 0.0070 | -0.0318 | 0.0570 |
| suave | 12 | 1130 | 94 | 619 | 54.8000 | 0.0104 | -0.0348 | 0.0581 |

## mejora_cuadrante_vs_global

| cuadrante | horizonte | series | no_comparable | gana_retador | %_gana_retador | mejora_mediana | mejora_p25 | mejora_p75 |
|---|---|---|---|---|---|---|---|---|
| erratica | 1 | 239 | 0 | 132 | 55.2000 | 0.0210 | -0.0646 | 0.1485 |
| erratica | 2 | 239 | 0 | 117 | 49.0000 | -0.0057 | -0.1000 | 0.0886 |
| erratica | 3 | 239 | 0 | 120 | 50.2000 | 0.0026 | -0.0953 | 0.1183 |
| erratica | 4 | 239 | 0 | 124 | 51.9000 | 0.0083 | -0.0838 | 0.1781 |
| erratica | 5 | 239 | 0 | 136 | 56.9000 | 0.0267 | -0.0723 | 0.2047 |
| erratica | 6 | 239 | 0 | 147 | 61.5000 | 0.0494 | -0.0553 | 0.2229 |
| erratica | 7 | 239 | 0 | 154 | 64.4000 | 0.0575 | -0.0334 | 0.2823 |
| erratica | 8 | 237 | 2 | 154 | 65.0000 | 0.0837 | -0.0406 | 0.4186 |
| erratica | 9 | 236 | 3 | 155 | 65.7000 | 0.0779 | -0.0389 | 0.3025 |
| erratica | 10 | 236 | 3 | 135 | 57.2000 | 0.0365 | -0.0613 | 0.3165 |
| erratica | 11 | 235 | 4 | 131 | 55.7000 | 0.0380 | -0.0800 | 0.2719 |
| erratica | 12 | 231 | 8 | 130 | 56.3000 | 0.0204 | -0.0928 | 0.2620 |
| intermitente | 1 | 488 | 0 | 274 | 56.1000 | 2.6386 | 0.5585 | 7.6261 |
| intermitente | 2 | 479 | 9 | 277 | 57.8000 | 4.8191 | 0.8401 | 16.3545 |
| intermitente | 3 | 476 | 12 | 258 | 54.2000 | 4.8893 | 0.8294 | 17.8593 |
| intermitente | 4 | 476 | 12 | 255 | 53.6000 | 5.1685 | 0.9365 | 19.9969 |
| intermitente | 5 | 466 | 22 | 243 | 52.1000 | 5.4151 | 1.1130 | 19.9511 |
| intermitente | 6 | 460 | 28 | 227 | 49.3000 | 6.3036 | 1.0473 | 21.7253 |
| intermitente | 7 | 445 | 43 | 198 | 44.5000 | 6.5875 | 1.3461 | 27.8441 |
| intermitente | 8 | 437 | 51 | 173 | 39.6000 | 6.2257 | 1.0545 | 23.5371 |
| intermitente | 9 | 433 | 55 | 146 | 33.7000 | 4.3628 | 0.8319 | 21.0865 |
| intermitente | 10 | 427 | 61 | 130 | 30.4000 | 4.0705 | 0.9629 | 18.3135 |
| intermitente | 11 | 419 | 69 | 122 | 29.1000 | 4.0491 | 0.7500 | 16.4678 |
| intermitente | 12 | 407 | 81 | 113 | 27.8000 | 3.5779 | 0.7390 | 12.9203 |
| lumpy | 1 | 177 | 0 | 121 | 68.4000 | 1.1286 | 0.1577 | 2.5070 |
| lumpy | 2 | 177 | 0 | 114 | 64.4000 | 1.1765 | 0.1650 | 3.4292 |
| lumpy | 3 | 177 | 0 | 113 | 63.8000 | 1.3135 | 0.1223 | 4.0621 |
| lumpy | 4 | 177 | 0 | 111 | 62.7000 | 1.7234 | 0.2156 | 5.3748 |
| lumpy | 5 | 177 | 0 | 110 | 62.1000 | 1.5065 | 0.2317 | 6.1900 |
| lumpy | 6 | 175 | 2 | 112 | 64.0000 | 2.0993 | 0.4467 | 8.8099 |
| lumpy | 7 | 175 | 2 | 108 | 61.7000 | 2.3289 | 0.5185 | 7.9154 |
| lumpy | 8 | 174 | 3 | 101 | 58.0000 | 3.0533 | 0.3360 | 8.7946 |
| lumpy | 9 | 174 | 3 | 98 | 56.3000 | 2.7935 | 0.5218 | 9.8634 |
| lumpy | 10 | 174 | 3 | 92 | 52.9000 | 2.8984 | 0.2157 | 10.1282 |
| lumpy | 11 | 174 | 3 | 82 | 47.1000 | 2.1924 | 0.1864 | 11.4757 |
| lumpy | 12 | 173 | 4 | 83 | 48.0000 | 2.2530 | 0.2744 | 10.8029 |
| suave | 1 | 1202 | 22 | 650 | 54.1000 | 0.0047 | -0.0290 | 0.0439 |
| suave | 2 | 1196 | 28 | 520 | 43.5000 | -0.0072 | -0.0405 | 0.0282 |
| suave | 3 | 1193 | 31 | 545 | 45.7000 | -0.0047 | -0.0380 | 0.0391 |
| suave | 4 | 1192 | 32 | 553 | 46.4000 | -0.0054 | -0.0439 | 0.0497 |
| suave | 5 | 1185 | 39 | 532 | 44.9000 | -0.0074 | -0.0456 | 0.0467 |
| suave | 6 | 1171 | 53 | 498 | 42.5000 | -0.0094 | -0.0490 | 0.0433 |
| suave | 7 | 1164 | 60 | 571 | 49.1000 | -0.0017 | -0.0402 | 0.0624 |
| suave | 8 | 1156 | 68 | 537 | 46.5000 | -0.0046 | -0.0440 | 0.0642 |
| suave | 9 | 1147 | 77 | 538 | 46.9000 | -0.0054 | -0.0430 | 0.0600 |
| suave | 10 | 1144 | 80 | 555 | 48.5000 | -0.0020 | -0.0451 | 0.0636 |
| suave | 11 | 1140 | 84 | 610 | 53.5000 | 0.0062 | -0.0402 | 0.0676 |
| suave | 12 | 1130 | 94 | 585 | 51.8000 | 0.0061 | -0.0468 | 0.0717 |

## ganador_por_cuadrante_y_corte

| corte | erratica | intermitente | lumpy | sin_actividad | suave |
|---|---|---|---|---|---|
| 2024-11-01 00:00:00 | SeasonalNaive | SeasonalNaive | SeasonalNaive | SeasonalNaive | SeasonalNaive |
| 2024-12-01 00:00:00 | AutoARIMA | AutoARIMA | GlobalLGBM_P50 | SeasonalNaive | AutoTheta |
| 2025-01-01 00:00:00 | AutoETS | AutoARIMA | GlobalLGBM_P50 | SeasonalNaive | AutoTheta |
| 2025-02-01 00:00:00 | GlobalLGBM_P50 | AutoARIMA | GlobalLGBM_P50 | SeasonalNaive | AutoTheta |
| 2025-03-01 00:00:00 | GlobalLGBM_P50 | AutoARIMA | GlobalLGBM_P50 | SeasonalNaive | GlobalLGBM_P50 |
| 2025-04-01 00:00:00 | GlobalLGBM_P50 | AutoARIMA | GlobalLGBM_P50 | SeasonalNaive | TSB |
| 2025-05-01 00:00:00 | GlobalLGBM_P50 | AutoARIMA | GlobalLGBM_P50 | SeasonalNaive | GlobalLGBM_P50 |
| 2025-06-01 00:00:00 | GlobalLGBM_P50 | AutoARIMA | GlobalLGBM_P50 | SeasonalNaive | GlobalLGBM_P50 |
| 2025-07-01 00:00:00 | GlobalLGBM_P50 | AutoARIMA | AutoARIMA | SeasonalNaive | GlobalLGBM_P50 |
| 2025-08-01 00:00:00 | GlobalLGBM_P50 | AutoARIMA | GlobalLGBM_P50 | SeasonalNaive | GlobalLGBM_P50 |
| 2025-09-01 00:00:00 | GlobalLGBM_P50 | AutoARIMA | AutoARIMA | SeasonalNaive | GlobalLGBM_P50 |
| 2025-10-01 00:00:00 | GlobalLGBM_P50 | AutoARIMA | AutoARIMA | SeasonalNaive | GlobalLGBM_P50 |
| 2025-11-01 00:00:00 | GlobalLGBM_P50 | AutoARIMA | AutoARIMA | SeasonalNaive | TSB |
| 2025-12-01 00:00:00 | AutoARIMA | AutoARIMA | AutoARIMA | SeasonalNaive | AutoTheta |
| 2026-01-01 00:00:00 | AutoARIMA | AutoARIMA | AutoARIMA | SeasonalNaive | AutoTheta |
| 2026-02-01 00:00:00 | GlobalLGBM_P50 | AutoARIMA | AutoARIMA | SeasonalNaive | AutoTheta |
| 2026-03-01 00:00:00 | GlobalLGBM_P50 | AutoARIMA | AutoARIMA | SeasonalNaive | AutoTheta |
| 2026-04-01 00:00:00 | GlobalLGBM_P50 | AutoARIMA | AutoARIMA | SeasonalNaive | GlobalLGBM_P50 |

## reparto_champion_cuadrante

| modelo_ganador | erratica | intermitente | lumpy | suave | total |
|---|---|---|---|---|---|
| GlobalLGBM_P50 | 2815 | 784 | 1070 | 9297 | 13966 |
| AutoARIMA | 588 | 6024 | 1799 | 338 | 8749 |
| AutoTheta | 316 | 256 | 42 | 7622 | 8236 |
| SeasonalNaive | 324 | 1540 | 232 | 2347 | 4443 |
| TSB | 111 | 87 | 13 | 2149 | 2360 |
| AutoETS | 148 | 10 | 28 | 74 | 260 |

## reparto_champion_serie

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

## estabilidad_champion_cuadrante

| cambios | n_series | % |
|---|---|---|
| 0 | 23 | 1.1000 |
| 1 | 257 | 12.1000 |
| 2 | 164 | 7.7000 |
| 3 | 66 | 3.1000 |
| 4 | 177 | 8.3000 |
| 5 | 228 | 10.7000 |
| 6 | 117 | 5.5000 |
| 7 | 1034 | 48.6000 |
| 8 | 41 | 1.9000 |
| 9 | 19 | 0.9000 |
| 10 | 1 | 0.0000 |
| 11 | 1 | 0.0000 |

## origen_champion_cuadrante

| origen | filas | % |
|---|---|---|
| ganador del corte | 291561 | 95.5000 |
| sin predicción (ningún candidato) | 12700 | 4.1600 |
| cascada | 1048 | 0.3400 |
