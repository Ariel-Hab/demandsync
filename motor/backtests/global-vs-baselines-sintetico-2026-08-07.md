# Champion/challenger: global contra el piso de baselines — sintetico (2026-08-07)

Champion/challenger de M2.5. **Ningún modelo se reajustó**: la tabla sale de cruzar los checkpoints de dos corridas que comparten `id` — el hash de corrida es de configuración + datos y no incluye el predictor.

- **Productos:** 400 de 2295 · **cortes:** 18 · **horizonte:** 12 · **filas cruzadas:** 57579 · **8.9 s**
- **Candidatos del champion:** 7 baselines + `GlobalLGBM` + `GlobalLGBM_P50`, elegidos con **selección prospectiva + cascada** (ADR-016) — por (serie, corte), y en cada corte solo con el error de las filas cuyo mes ya ocurrió.
- **El piso usa exactamente la misma regla**, y eso es el punto: si el champion eligiera con hindsight y el piso no, la comparación estaría inclinada a favor del global, que es ADR-016 punto 4 al revés.
- **`global` y `global_P50` no seleccionan nada**: son la columna del modelo aplicada a todas las series. Sirven para separar cuánto del resultado es el modelo y cuánto es elegir por serie.
- **Las tablas estándar de abajo (por nivel, categoría, cuadrante, MASE) son del `champion`**, que es el candidato a promover. La comparación entre los cuatro está en *Cabeza a cabeza*.
- **Muestreo:** estratificado, hasta 100 por cuadrante, semilla 42 → erratica: 100 · intermitente: 100 · lumpy: 100 · suave: 100

> **`mejora` es `wape(campeon) - wape(retador)`: positivo favorece al retador.** Se reporta la mediana y los cuartiles, no la media: la distribución tiene colas largas y una serie con WAPE de 40 corre el promedio entero.

> **Solo se comparan las celdas donde los dos contendientes tienen la misma cobertura.** En `metricas.wape` una predicción nula aporta 0 al numerador, así que una serie **no predicha** puntúa WAPE 0,0 —perfecto— y solo la columna `cobertura` lo delata. La columna `no_comparable` cuenta lo que queda afuera.

> **Por qué la `cobertura` no es 1,0:** son las **altas de catálogo** de `roadmap-motor.md` §5.6.1 — productos cuya primera venta es posterior al corte. §6.5 verificó fila a fila que son **las mismas** en las dos corridas, así que la comparación es a igual cobertura por construcción, no por suerte.

> ⚠️ **El sintético no decide el gate de M2.** El generador no tiene la irregularidad del mundo real y haría ver al modelo mejor de lo que es (`roadmap-motor.md` §6, *Riesgo específico*). Vale para verificar que el pipeline corre; el número que manda es el de la corrida real. Y **no se compara contra `baselines-sintetico-2026-07-30.md`**: esa tabla se congeló antes de que T0.4 reescribiera el generador (§6.4).

## Corrida

| id | fecha_ejecucion | n_cortes | horizonte_max | columnas_id | columna_objetivo | densificado | primer_corte | ultimo_corte | datos_filas | datos_series | datos_primer_mes | datos_ultimo_mes | datos_suma_objetivo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| be8823f67f16 | 2026-08-07 | 18 | 12 | ('id_producto',) | unidades | True | 2024-12-01 | 2026-05-01 | 27683 | 400 | 2018-07-01 | 2026-06-01 | 517206.8400 |

## Cabeza a cabeza por nivel y horizonte (M2.5) — **solo se comparan WAPE con la misma `cobertura`**

| contendiente | nivel | horizonte | wape | n | cobertura | sesgo |
|---|---|---|---|---|---|---|
| piso | producto | 1 | 0.9819 | 6805 | 0.9941 | 0.0677 |
| global | producto | 1 | 0.9360 | 6805 | 0.9941 | -0.0017 |
| global_P50 | producto | 1 | 0.7996 | 6805 | 0.9941 | -0.2966 |
| champion | producto | 1 | 0.9657 | 6805 | 0.9941 | 0.0027 |
| piso | producto | 3 | 0.9366 | 6084 | 0.9809 | 0.0057 |
| global | producto | 3 | 0.8736 | 6084 | 0.9809 | 0.0031 |
| global_P50 | producto | 3 | 0.7518 | 6084 | 0.9809 | -0.3915 |
| champion | producto | 3 | 0.9000 | 6084 | 0.9809 | -0.0799 |
| piso | producto | 6 | 0.9380 | 4992 | 0.9599 | 0.0386 |
| global | producto | 6 | 0.9122 | 4992 | 0.9599 | 0.0447 |
| global_P50 | producto | 6 | 0.7470 | 4992 | 0.9599 | -0.3615 |
| champion | producto | 6 | 0.8817 | 4992 | 0.9599 | -0.0532 |
| piso | producto | 12 | 0.9465 | 2756 | 0.9216 | 0.1025 |
| global | producto | 12 | 0.8883 | 2756 | 0.9216 | 0.1195 |
| global_P50 | producto | 12 | 0.7296 | 2756 | 0.9216 | -0.2802 |
| champion | producto | 12 | 0.9340 | 2756 | 0.9216 | 0.0838 |
| piso | categoria | 1 | 0.3066 | 198 | 1.0000 | 0.0581 |
| global | categoria | 1 | 0.2652 | 198 | 1.0000 | -0.0113 |
| global_P50 | categoria | 1 | 0.3592 | 198 | 1.0000 | -0.3064 |
| champion | categoria | 1 | 0.2957 | 198 | 1.0000 | -0.0069 |
| piso | categoria | 3 | 0.2894 | 176 | 1.0000 | -0.0154 |
| global | categoria | 3 | 0.2679 | 176 | 1.0000 | -0.0181 |
| global_P50 | categoria | 3 | 0.4422 | 176 | 1.0000 | -0.4128 |
| champion | categoria | 3 | 0.2947 | 176 | 1.0000 | -0.1011 |
| piso | categoria | 6 | 0.2776 | 143 | 1.0000 | 0.0011 |
| global | categoria | 6 | 0.2675 | 143 | 1.0000 | 0.0072 |
| global_P50 | categoria | 6 | 0.4263 | 143 | 1.0000 | -0.3992 |
| champion | categoria | 6 | 0.2874 | 143 | 1.0000 | -0.0908 |
| piso | categoria | 12 | 0.2854 | 77 | 1.0000 | 0.0290 |
| global | categoria | 12 | 0.2466 | 77 | 1.0000 | 0.0461 |
| global_P50 | categoria | 12 | 0.3965 | 77 | 1.0000 | -0.3537 |
| champion | categoria | 12 | 0.2880 | 77 | 1.0000 | 0.0103 |
| piso | total | 1 | 0.1717 | 18 | 1.0000 | 0.0581 |
| global | total | 1 | 0.1183 | 18 | 1.0000 | -0.0113 |
| global_P50 | total | 1 | 0.3064 | 18 | 1.0000 | -0.3064 |
| champion | total | 1 | 0.1663 | 18 | 1.0000 | -0.0069 |
| piso | total | 3 | 0.1763 | 16 | 1.0000 | -0.0154 |
| global | total | 3 | 0.1391 | 16 | 1.0000 | -0.0181 |
| global_P50 | total | 3 | 0.4156 | 16 | 1.0000 | -0.4128 |
| champion | total | 3 | 0.2048 | 16 | 1.0000 | -0.1011 |
| piso | total | 6 | 0.1432 | 13 | 1.0000 | 0.0011 |
| global | total | 6 | 0.1365 | 13 | 1.0000 | 0.0072 |
| global_P50 | total | 6 | 0.3992 | 13 | 1.0000 | -0.3992 |
| champion | total | 6 | 0.1774 | 13 | 1.0000 | -0.0908 |
| piso | total | 12 | 0.2025 | 7 | 1.0000 | 0.0290 |
| global | total | 12 | 0.1743 | 7 | 1.0000 | 0.0461 |
| global_P50 | total | 12 | 0.3537 | 7 | 1.0000 | -0.3537 |
| champion | total | 12 | 0.1884 | 7 | 1.0000 | 0.0103 |

## Cabeza a cabeza **por cuadrante** (grano producto) — leer con la columna `peso_%`: es cuánto pesa cada cuadrante en el WAPE agregado de arriba

| contendiente | cuadrante | horizonte | wape | n | cobertura | sesgo | peso_% |
|---|---|---|---|---|---|---|---|
| piso | erratica | 1 | 1.0994 | 1647 | 0.9903 | 0.0169 | 38.6689 |
| global | erratica | 1 | 1.0059 | 1647 | 0.9903 | 0.0006 | 38.6689 |
| global_P50 | erratica | 1 | 0.8316 | 1647 | 0.9903 | -0.4048 | 38.6689 |
| champion | erratica | 1 | 1.0849 | 1647 | 0.9903 | -0.0521 | 38.6689 |
| piso | erratica | 3 | 1.0441 | 1478 | 0.9682 | 0.0048 | 38.8303 |
| global | erratica | 3 | 0.9312 | 1478 | 0.9682 | -0.0791 | 38.8303 |
| global_P50 | erratica | 3 | 0.7992 | 1478 | 0.9682 | -0.4667 | 38.8303 |
| champion | erratica | 3 | 1.0126 | 1478 | 0.9682 | -0.0945 | 38.8303 |
| piso | erratica | 6 | 1.0362 | 1220 | 0.9361 | 0.0601 | 38.2038 |
| global | erratica | 6 | 0.9383 | 1220 | 0.9361 | -0.0330 | 38.2038 |
| global_P50 | erratica | 6 | 0.7761 | 1220 | 0.9361 | -0.4288 | 38.2038 |
| champion | erratica | 6 | 0.9585 | 1220 | 0.9361 | -0.0601 | 38.2038 |
| piso | erratica | 12 | 1.0991 | 682 | 0.8768 | 0.1223 | 36.6793 |
| global | erratica | 12 | 0.8992 | 682 | 0.8768 | 0.0800 | 36.6793 |
| global_P50 | erratica | 12 | 0.7420 | 682 | 0.8768 | -0.3138 | 36.6793 |
| champion | erratica | 12 | 1.0883 | 682 | 0.8768 | 0.1174 | 36.6793 |
| piso | intermitente | 1 | 1.1646 | 1690 | 0.9923 | 0.2323 | 14.6858 |
| global | intermitente | 1 | 1.1826 | 1690 | 0.9923 | -0.0845 | 14.6858 |
| global_P50 | intermitente | 1 | 1.0808 | 1690 | 0.9923 | -0.2894 | 14.6858 |
| champion | intermitente | 1 | 1.1392 | 1690 | 0.9923 | 0.1083 | 14.6858 |
| piso | intermitente | 3 | 1.2683 | 1516 | 0.9743 | 0.1896 | 14.6463 |
| global | intermitente | 3 | 1.1778 | 1516 | 0.9743 | 0.1284 | 14.6463 |
| global_P50 | intermitente | 3 | 0.9789 | 1516 | 0.9743 | -0.4848 | 14.6463 |
| champion | intermitente | 3 | 1.1860 | 1516 | 0.9743 | 0.0502 | 14.6463 |
| piso | intermitente | 6 | 1.2195 | 1249 | 0.9464 | 0.2745 | 14.2107 |
| global | intermitente | 6 | 1.2560 | 1249 | 0.9464 | 0.2932 | 14.2107 |
| global_P50 | intermitente | 6 | 0.9717 | 1249 | 0.9464 | -0.4278 | 14.2107 |
| champion | intermitente | 6 | 1.1454 | 1249 | 0.9464 | 0.1400 | 14.2107 |
| piso | intermitente | 12 | 1.1668 | 691 | 0.8958 | 0.3463 | 14.3587 |
| global | intermitente | 12 | 1.1796 | 691 | 0.8958 | 0.3680 | 14.3587 |
| global_P50 | intermitente | 12 | 0.9154 | 691 | 0.8958 | -0.2530 | 14.3587 |
| champion | intermitente | 12 | 1.1512 | 691 | 0.8958 | 0.3398 | 14.3587 |
| piso | lumpy | 1 | 1.6301 | 1766 | 0.9983 | 0.1605 | 14.6155 |
| global | lumpy | 1 | 1.3900 | 1766 | 0.9983 | -0.0804 | 14.6155 |
| global_P50 | lumpy | 1 | 1.1501 | 1766 | 0.9983 | -0.4499 | 14.6155 |
| champion | lumpy | 1 | 1.5662 | 1766 | 0.9983 | 0.0420 | 14.6155 |
| piso | lumpy | 3 | 1.3853 | 1572 | 0.9943 | -0.1606 | 14.2237 |
| global | lumpy | 3 | 1.3964 | 1572 | 0.9943 | 0.0696 | 14.2237 |
| global_P50 | lumpy | 3 | 1.0615 | 1572 | 0.9943 | -0.6132 | 14.2237 |
| champion | lumpy | 3 | 1.2991 | 1572 | 0.9943 | -0.2938 | 14.2237 |
| piso | lumpy | 6 | 1.3849 | 1281 | 0.9867 | -0.1247 | 15.1107 |
| global | lumpy | 6 | 1.4583 | 1281 | 0.9867 | 0.1153 | 15.1107 |
| global_P50 | lumpy | 6 | 1.0566 | 1281 | 0.9867 | -0.6132 | 15.1107 |
| champion | lumpy | 6 | 1.3067 | 1281 | 0.9867 | -0.2484 | 15.1107 |
| piso | lumpy | 12 | 1.3683 | 697 | 0.9742 | -0.0425 | 14.3373 |
| global | lumpy | 12 | 1.4553 | 697 | 0.9742 | 0.2011 | 14.3373 |
| global_P50 | lumpy | 12 | 1.0527 | 697 | 0.9742 | -0.5540 | 14.3373 |
| champion | lumpy | 12 | 1.3384 | 697 | 0.9742 | -0.0956 | 14.3373 |
| piso | suave | 1 | 0.4606 | 1702 | 0.9953 | 0.0112 | 32.0299 |
| global | suave | 1 | 0.5314 | 1702 | 0.9953 | 0.0693 | 32.0299 |
| global_P50 | suave | 1 | 0.4722 | 1702 | 0.9953 | -0.0995 | 32.0299 |
| champion | suave | 1 | 0.4683 | 1702 | 0.9953 | 0.0024 | 32.0299 |
| piso | suave | 3 | 0.4593 | 1518 | 0.9862 | -0.0033 | 32.2997 |
| global | suave | 3 | 0.4361 | 1518 | 0.9862 | 0.0158 | 32.2997 |
| global_P50 | suave | 3 | 0.4556 | 1518 | 0.9862 | -0.1611 | 32.2997 |
| champion | suave | 3 | 0.4591 | 1518 | 0.9862 | -0.0272 | 32.2997 |
| piso | suave | 6 | 0.4913 | 1242 | 0.9694 | -0.0139 | 32.4748 |
| global | suave | 6 | 0.4769 | 1242 | 0.9694 | -0.0055 | 32.4748 |
| global_P50 | suave | 6 | 0.4704 | 1242 | 0.9694 | -0.1362 | 32.4748 |
| champion | suave | 6 | 0.4782 | 1242 | 0.9694 | -0.0388 | 32.4748 |
| piso | suave | 12 | 0.5189 | 686 | 0.9388 | 0.0403 | 34.6247 |
| global | suave | 12 | 0.5211 | 686 | 0.9388 | 0.0246 | 34.6247 |
| global_P50 | suave | 12 | 0.5057 | 686 | 0.9388 | -0.1425 | 34.6247 |
| champion | suave | 12 | 0.5130 | 686 | 0.9388 | 0.0162 | 34.6247 |

## ¿En cuántas series le gana el global al piso? `mejora = wape(piso) − wape(global)`, positivo favorece al global

| cuadrante | horizonte | series | no_comparable | gana_retador | %_gana_retador | mejora_mediana | mejora_p25 | mejora_p75 |
|---|---|---|---|---|---|---|---|---|
| erratica | 1 | 100 | 0 | 36 | 36.0000 | -0.0732 | -0.2091 | 0.0894 |
| erratica | 2 | 100 | 0 | 56 | 56.0000 | 0.0182 | -0.1107 | 0.1596 |
| erratica | 3 | 99 | 1 | 58 | 58.6000 | 0.0533 | -0.1139 | 0.2406 |
| erratica | 4 | 96 | 4 | 56 | 58.3000 | 0.0355 | -0.0909 | 0.2254 |
| erratica | 5 | 94 | 6 | 60 | 63.8000 | 0.0565 | -0.0928 | 0.2541 |
| erratica | 6 | 93 | 7 | 55 | 59.1000 | 0.0345 | -0.0736 | 0.2351 |
| erratica | 7 | 92 | 8 | 58 | 63.0000 | 0.0800 | -0.0881 | 0.2560 |
| erratica | 8 | 91 | 9 | 50 | 54.9000 | 0.0370 | -0.1428 | 0.2092 |
| erratica | 9 | 91 | 9 | 54 | 59.3000 | 0.0710 | -0.0828 | 0.2773 |
| erratica | 10 | 89 | 11 | 59 | 66.3000 | 0.0870 | -0.0441 | 0.2270 |
| erratica | 11 | 88 | 12 | 50 | 56.8000 | 0.0523 | -0.1438 | 0.3242 |
| erratica | 12 | 87 | 13 | 45 | 51.7000 | 0.0035 | -0.1781 | 0.2536 |
| intermitente | 1 | 100 | 0 | 42 | 42.0000 | -0.1107 | -0.3299 | 0.2073 |
| intermitente | 2 | 100 | 0 | 46 | 46.0000 | -0.0268 | -0.3100 | 0.1398 |
| intermitente | 3 | 100 | 0 | 46 | 46.0000 | -0.0148 | -0.3002 | 0.1657 |
| intermitente | 4 | 98 | 2 | 52 | 53.1000 | 0.0205 | -0.3132 | 0.1616 |
| intermitente | 5 | 97 | 3 | 42 | 43.3000 | -0.0338 | -0.2701 | 0.1662 |
| intermitente | 6 | 96 | 4 | 34 | 35.4000 | -0.0677 | -0.3786 | 0.0981 |
| intermitente | 7 | 95 | 5 | 43 | 45.3000 | -0.0158 | -0.3215 | 0.1453 |
| intermitente | 8 | 95 | 5 | 39 | 41.1000 | -0.0549 | -0.3592 | 0.0903 |
| intermitente | 9 | 93 | 7 | 38 | 40.9000 | -0.0320 | -0.4366 | 0.1718 |
| intermitente | 10 | 93 | 7 | 33 | 35.5000 | -0.1409 | -0.5329 | 0.1128 |
| intermitente | 11 | 91 | 9 | 37 | 40.7000 | -0.0416 | -0.4963 | 0.1642 |
| intermitente | 12 | 91 | 9 | 29 | 31.9000 | -0.0990 | -0.5445 | 0.1412 |
| lumpy | 1 | 100 | 0 | 46 | 46.0000 | -0.0312 | -0.3666 | 0.4632 |
| lumpy | 2 | 100 | 0 | 44 | 44.0000 | -0.0354 | -0.5376 | 0.1850 |
| lumpy | 3 | 100 | 0 | 43 | 43.0000 | -0.0373 | -0.5698 | 0.2234 |
| lumpy | 4 | 100 | 0 | 39 | 39.0000 | -0.1058 | -0.5911 | 0.2350 |
| lumpy | 5 | 99 | 1 | 37 | 37.4000 | -0.1397 | -0.6100 | 0.1154 |
| lumpy | 6 | 98 | 2 | 32 | 32.7000 | -0.1222 | -0.8652 | 0.0914 |
| lumpy | 7 | 98 | 2 | 31 | 31.6000 | -0.1328 | -0.5962 | 0.1039 |
| lumpy | 8 | 98 | 2 | 38 | 38.8000 | -0.0506 | -0.5655 | 0.1334 |
| lumpy | 9 | 97 | 3 | 31 | 32.0000 | -0.1370 | -0.9309 | 0.0605 |
| lumpy | 10 | 97 | 3 | 29 | 29.9000 | -0.1877 | -0.8051 | 0.0703 |
| lumpy | 11 | 97 | 3 | 38 | 39.2000 | -0.0580 | -0.7451 | 0.1587 |
| lumpy | 12 | 97 | 3 | 31 | 32.0000 | -0.1234 | -0.9560 | 0.0890 |
| suave | 1 | 99 | 1 | 21 | 21.2000 | -0.0888 | -0.1817 | -0.0208 |
| suave | 2 | 98 | 2 | 58 | 59.2000 | 0.0110 | -0.0454 | 0.0798 |
| suave | 3 | 98 | 2 | 62 | 63.3000 | 0.0346 | -0.0473 | 0.0739 |
| suave | 4 | 98 | 2 | 63 | 64.3000 | 0.0345 | -0.0421 | 0.1188 |
| suave | 5 | 97 | 3 | 61 | 62.9000 | 0.0398 | -0.0281 | 0.1015 |
| suave | 6 | 96 | 4 | 62 | 64.6000 | 0.0324 | -0.0290 | 0.0908 |
| suave | 7 | 95 | 5 | 57 | 60.0000 | 0.0303 | -0.0446 | 0.0894 |
| suave | 8 | 93 | 7 | 53 | 57.0000 | 0.0164 | -0.0749 | 0.0860 |
| suave | 9 | 92 | 8 | 51 | 55.4000 | 0.0139 | -0.0951 | 0.1161 |
| suave | 10 | 92 | 8 | 51 | 55.4000 | 0.0213 | -0.0562 | 0.1063 |
| suave | 11 | 92 | 8 | 55 | 59.8000 | 0.0275 | -0.0796 | 0.1183 |
| suave | 12 | 92 | 8 | 50 | 54.3000 | 0.0120 | -0.0730 | 0.0987 |

## ¿Paga elegir por serie? `mejora = wape(global) − wape(champion)`, positivo favorece a la selección

| cuadrante | horizonte | series | no_comparable | gana_retador | %_gana_retador | mejora_mediana | mejora_p25 | mejora_p75 |
|---|---|---|---|---|---|---|---|---|
| erratica | 1 | 100 | 0 | 70 | 70.0000 | 0.0979 | -0.0243 | 0.2262 |
| erratica | 2 | 100 | 0 | 54 | 54.0000 | 0.0203 | -0.1213 | 0.1428 |
| erratica | 3 | 99 | 1 | 46 | 46.5000 | -0.0210 | -0.1822 | 0.1299 |
| erratica | 4 | 96 | 4 | 48 | 50.0000 | -0.0027 | -0.1794 | 0.1151 |
| erratica | 5 | 94 | 6 | 41 | 43.6000 | -0.0220 | -0.2070 | 0.0925 |
| erratica | 6 | 93 | 7 | 46 | 49.5000 | -0.0017 | -0.1481 | 0.1755 |
| erratica | 7 | 92 | 8 | 34 | 37.0000 | -0.0515 | -0.2104 | 0.1123 |
| erratica | 8 | 91 | 9 | 41 | 45.1000 | -0.0326 | -0.1408 | 0.1735 |
| erratica | 9 | 91 | 9 | 37 | 40.7000 | -0.0340 | -0.1998 | 0.0828 |
| erratica | 10 | 89 | 11 | 34 | 38.2000 | -0.0870 | -0.1977 | 0.0767 |
| erratica | 11 | 88 | 12 | 40 | 45.5000 | -0.0289 | -0.2617 | 0.1378 |
| erratica | 12 | 87 | 13 | 43 | 49.4000 | -0.0035 | -0.2335 | 0.1785 |
| intermitente | 1 | 100 | 0 | 56 | 56.0000 | 0.0757 | -0.1708 | 0.3299 |
| intermitente | 2 | 100 | 0 | 56 | 56.0000 | 0.0605 | -0.1147 | 0.3610 |
| intermitente | 3 | 100 | 0 | 51 | 51.0000 | 0.0251 | -0.1187 | 0.3854 |
| intermitente | 4 | 98 | 2 | 52 | 53.1000 | 0.0245 | -0.1299 | 0.3777 |
| intermitente | 5 | 97 | 3 | 56 | 57.7000 | 0.0848 | -0.1531 | 0.4071 |
| intermitente | 6 | 96 | 4 | 60 | 62.5000 | 0.0684 | -0.1009 | 0.4171 |
| intermitente | 7 | 95 | 5 | 54 | 56.8000 | 0.0561 | -0.1361 | 0.3369 |
| intermitente | 8 | 95 | 5 | 55 | 57.9000 | 0.0564 | -0.0820 | 0.3929 |
| intermitente | 9 | 93 | 7 | 48 | 51.6000 | 0.0384 | -0.1632 | 0.4958 |
| intermitente | 10 | 93 | 7 | 53 | 57.0000 | 0.1409 | -0.1380 | 0.5459 |
| intermitente | 11 | 91 | 9 | 47 | 51.6000 | 0.0882 | -0.1108 | 0.5455 |
| intermitente | 12 | 91 | 9 | 48 | 52.7000 | 0.0990 | -0.1412 | 0.6382 |
| lumpy | 1 | 100 | 0 | 56 | 56.0000 | 0.1052 | -0.2588 | 0.3715 |
| lumpy | 2 | 100 | 0 | 60 | 60.0000 | 0.1439 | -0.1027 | 0.7205 |
| lumpy | 3 | 100 | 0 | 63 | 63.0000 | 0.1472 | -0.0685 | 0.7004 |
| lumpy | 4 | 100 | 0 | 67 | 67.0000 | 0.1623 | -0.0899 | 0.7779 |
| lumpy | 5 | 99 | 1 | 67 | 67.7000 | 0.1721 | -0.0182 | 0.6639 |
| lumpy | 6 | 98 | 2 | 66 | 67.3000 | 0.2224 | -0.0574 | 0.8732 |
| lumpy | 7 | 98 | 2 | 65 | 66.3000 | 0.1698 | -0.0938 | 0.7522 |
| lumpy | 8 | 98 | 2 | 60 | 61.2000 | 0.0537 | -0.0630 | 0.6896 |
| lumpy | 9 | 97 | 3 | 61 | 62.9000 | 0.2560 | -0.0468 | 0.9309 |
| lumpy | 10 | 97 | 3 | 61 | 62.9000 | 0.2434 | -0.0240 | 1.0690 |
| lumpy | 11 | 97 | 3 | 56 | 57.7000 | 0.1172 | -0.0945 | 0.7173 |
| lumpy | 12 | 97 | 3 | 58 | 59.8000 | 0.1676 | -0.0636 | 0.9860 |
| suave | 1 | 99 | 1 | 77 | 77.8000 | 0.0704 | 0.0154 | 0.1712 |
| suave | 2 | 98 | 2 | 38 | 38.8000 | -0.0219 | -0.0791 | 0.0382 |
| suave | 3 | 98 | 2 | 33 | 33.7000 | -0.0375 | -0.0824 | 0.0361 |
| suave | 4 | 98 | 2 | 34 | 34.7000 | -0.0356 | -0.1052 | 0.0356 |
| suave | 5 | 97 | 3 | 35 | 36.1000 | -0.0398 | -0.0947 | 0.0232 |
| suave | 6 | 96 | 4 | 38 | 39.6000 | -0.0230 | -0.0960 | 0.0366 |
| suave | 7 | 95 | 5 | 35 | 36.8000 | -0.0222 | -0.1039 | 0.0468 |
| suave | 8 | 93 | 7 | 43 | 46.2000 | -0.0164 | -0.0875 | 0.0877 |
| suave | 9 | 92 | 8 | 40 | 43.5000 | -0.0123 | -0.1142 | 0.0972 |
| suave | 10 | 92 | 8 | 41 | 44.6000 | -0.0141 | -0.0987 | 0.0609 |
| suave | 11 | 92 | 8 | 34 | 37.0000 | -0.0392 | -0.1219 | 0.0614 |
| suave | 12 | 92 | 8 | 43 | 46.7000 | -0.0097 | -0.1064 | 0.0766 |

## Modelo ganador del champion por cuadrante (pares serie×corte)

| modelo_ganador | erratica | intermitente | lumpy | suave | total |
|---|---|---|---|---|---|
| SeasonalNaive | 590 | 704 | 527 | 466 | 2287 |
| GlobalLGBM_P50 | 461 | 311 | 419 | 146 | 1337 |
| AutoETS | 201 | 151 | 122 | 501 | 975 |
| AutoARIMA | 187 | 246 | 360 | 126 | 919 |
| CrostonSBA | 112 | 131 | 78 | 229 | 550 |
| WindowAverage | 102 | 121 | 170 | 58 | 451 |
| GlobalLGBM | 43 | 60 | 39 | 114 | 256 |
| AutoTheta | 55 | 33 | 50 | 88 | 226 |
| TSB | 31 | 34 | 32 | 58 | 155 |

## Modelo ganador del piso por cuadrante, para contrastar

| modelo_ganador | erratica | intermitente | lumpy | suave | total |
|---|---|---|---|---|---|
| SeasonalNaive | 642 | 759 | 572 | 494 | 2467 |
| AutoARIMA | 294 | 372 | 480 | 156 | 1302 |
| AutoETS | 298 | 191 | 162 | 589 | 1240 |
| CrostonSBA | 216 | 167 | 121 | 271 | 775 |
| WindowAverage | 173 | 173 | 294 | 82 | 722 |
| AutoTheta | 97 | 54 | 98 | 112 | 361 |
| TSB | 62 | 75 | 70 | 82 | 289 |

## Cambios de ganador del champion a lo largo de los cortes

| cambios | n_series | % |
|---|---|---|
| 0 | 39 | 9.8000 |
| 1 | 12 | 3.0000 |
| 2 | 13 | 3.2000 |
| 3 | 16 | 4.0000 |
| 4 | 22 | 5.5000 |
| 5 | 22 | 5.5000 |
| 6 | 27 | 6.8000 |
| 7 | 43 | 10.8000 |
| 8 | 44 | 11.0000 |
| 9 | 36 | 9.0000 |
| 10 | 39 | 9.8000 |
| 11 | 33 | 8.2000 |
| 12 | 22 | 5.5000 |
| 13 | 13 | 3.2000 |
| 14 | 13 | 3.2000 |
| 15 | 5 | 1.2000 |
| 16 | 1 | 0.2000 |

## Origen de cada predicción del champion (ganador / cascada / nadie)

| origen | filas | % |
|---|---|---|
| ganador del corte | 54216 | 94.1600 |
| sin predicción (ningún candidato) | 2121 | 3.6800 |
| cascada | 1242 | 2.1600 |

## Por nivel de agregación y horizonte

| nivel | horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|---|
| producto | 1 | 0.9657 | 0.0027 | 6805 | 0.9941 |
| producto | 3 | 0.9000 | -0.0799 | 6084 | 0.9809 |
| producto | 6 | 0.8817 | -0.0532 | 4992 | 0.9599 |
| producto | 12 | 0.9340 | 0.0838 | 2756 | 0.9216 |
| categoria | 1 | 0.2957 | -0.0069 | 198 | 1.0000 |
| categoria | 3 | 0.2947 | -0.1011 | 176 | 1.0000 |
| categoria | 6 | 0.2874 | -0.0908 | 143 | 1.0000 |
| categoria | 12 | 0.2880 | 0.0103 | 77 | 1.0000 |
| total | 1 | 0.1663 | -0.0069 | 18 | 1.0000 |
| total | 3 | 0.2048 | -0.1011 | 16 | 1.0000 |
| total | 6 | 0.1774 | -0.0908 | 13 | 1.0000 |
| total | 12 | 0.1884 | 0.0103 | 7 | 1.0000 |

## Por horizonte (grano producto)

| horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|
| 1 | 0.9657 | 0.0027 | 6805 | 0.9941 |
| 3 | 0.9000 | -0.0799 | 6084 | 0.9809 |
| 6 | 0.8817 | -0.0532 | 4992 | 0.9599 |
| 12 | 0.9340 | 0.0838 | 2756 | 0.9216 |

## Por categoría y horizonte

| categoria | horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|---|
| ACCESORIO | 1 | 2.1627 | 0.8781 | 36 | 1.0000 |
| ACCESORIO | 3 | 1.8112 | 0.6030 | 32 | 1.0000 |
| ACCESORIO | 6 | 2.1145 | 0.4300 | 26 | 1.0000 |
| ACCESORIO | 12 | 2.9104 | 1.0547 | 14 | 1.0000 |
| ALIMENTO | 1 | 0.9204 | 0.1469 | 126 | 1.0000 |
| ALIMENTO | 3 | 0.6511 | -0.1136 | 112 | 1.0000 |
| ALIMENTO | 6 | 0.7985 | 0.0119 | 91 | 1.0000 |
| ALIMENTO | 12 | 0.9102 | 0.0116 | 49 | 1.0000 |
| ANTIARTROSICO | 1 | 1.1018 | 0.6289 | 36 | 1.0000 |
| ANTIARTROSICO | 3 | 0.5121 | -0.0743 | 32 | 1.0000 |
| ANTIARTROSICO | 6 | 0.7339 | -0.1279 | 26 | 1.0000 |
| ANTIARTROSICO | 12 | 0.4119 | -0.0660 | 14 | 1.0000 |
| ANTIPARASITARIO EXTERNO | 1 | 1.2172 | 0.1910 | 1071 | 0.9897 |
| ANTIPARASITARIO EXTERNO | 3 | 0.9735 | 0.0188 | 962 | 0.9667 |
| ANTIPARASITARIO EXTERNO | 6 | 0.9041 | -0.1040 | 796 | 0.9296 |
| ANTIPARASITARIO EXTERNO | 12 | 0.8843 | 0.1112 | 446 | 0.8632 |
| ANTIPARASITARIO INTERNO | 1 | 0.8519 | -0.0085 | 394 | 0.9949 |
| ANTIPARASITARIO INTERNO | 3 | 0.7133 | -0.2080 | 352 | 0.9830 |
| ANTIPARASITARIO INTERNO | 6 | 0.7177 | -0.1798 | 289 | 0.9619 |
| ANTIPARASITARIO INTERNO | 12 | 0.6082 | 0.0084 | 159 | 0.9245 |
| BIOLOGICO | 1 | 1.0811 | -0.3025 | 216 | 1.0000 |
| BIOLOGICO | 3 | 1.1244 | -0.3156 | 192 | 1.0000 |
| BIOLOGICO | 6 | 1.2229 | -0.2019 | 156 | 1.0000 |
| BIOLOGICO | 12 | 1.0332 | -0.3621 | 84 | 1.0000 |
| CARDIOLOGICO | 1 | 1.0698 | 0.0495 | 126 | 1.0000 |
| CARDIOLOGICO | 3 | 0.9625 | -0.1084 | 112 | 1.0000 |
| CARDIOLOGICO | 6 | 0.9638 | -0.1736 | 91 | 1.0000 |
| CARDIOLOGICO | 12 | 1.0442 | -0.2127 | 49 | 1.0000 |
| CLINICO | 1 | 0.8724 | -0.0724 | 2194 | 0.9941 |
| CLINICO | 3 | 0.8878 | -0.0941 | 1960 | 0.9816 |
| CLINICO | 6 | 0.8769 | -0.0396 | 1607 | 0.9627 |
| CLINICO | 12 | 1.0140 | 0.1679 | 888 | 0.9268 |
| DESCARTABLES | 1 | 1.1419 | 0.3580 | 229 | 0.9825 |
| DESCARTABLES | 3 | 0.9871 | 0.3078 | 207 | 0.9420 |
| DESCARTABLES | 6 | 0.7864 | 0.0948 | 174 | 0.8621 |
| DESCARTABLES | 12 | 0.4897 | 0.0386 | 104 | 0.7404 |
| HIGIENE Y BELLEZA | 1 | 1.0170 | 0.0184 | 823 | 0.9939 |
| HIGIENE Y BELLEZA | 3 | 0.8585 | -0.0877 | 737 | 0.9796 |
| HIGIENE Y BELLEZA | 6 | 0.8122 | -0.1820 | 605 | 0.9603 |
| HIGIENE Y BELLEZA | 12 | 0.9132 | -0.0430 | 331 | 0.9245 |
| SIN CATEGORIA | 1 | 1.0466 | 0.0573 | 1554 | 0.9968 |
| SIN CATEGORIA | 3 | 1.0063 | -0.0220 | 1386 | 0.9892 |
| SIN CATEGORIA | 6 | 0.9666 | 0.0827 | 1131 | 0.9779 |
| SIN CATEGORIA | 12 | 0.9785 | 0.1106 | 618 | 0.9579 |

## Por cuadrante de intermitencia y horizonte

| cuadrante | horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|---|
| erratica | 1 | 1.0849 | -0.0521 | 1647 | 0.9903 |
| erratica | 3 | 1.0126 | -0.0945 | 1478 | 0.9682 |
| erratica | 6 | 0.9585 | -0.0601 | 1220 | 0.9361 |
| erratica | 12 | 1.0883 | 0.1174 | 682 | 0.8768 |
| intermitente | 1 | 1.1392 | 0.1083 | 1690 | 0.9923 |
| intermitente | 3 | 1.1860 | 0.0502 | 1516 | 0.9743 |
| intermitente | 6 | 1.1454 | 0.1400 | 1249 | 0.9464 |
| intermitente | 12 | 1.1512 | 0.3398 | 691 | 0.8958 |
| lumpy | 1 | 1.5662 | 0.0420 | 1766 | 0.9983 |
| lumpy | 3 | 1.2991 | -0.2938 | 1572 | 0.9943 |
| lumpy | 6 | 1.3067 | -0.2484 | 1281 | 0.9867 |
| lumpy | 12 | 1.3384 | -0.0956 | 697 | 0.9742 |
| suave | 1 | 0.4683 | 0.0024 | 1702 | 0.9953 |
| suave | 3 | 0.4591 | -0.0272 | 1518 | 0.9862 |
| suave | 6 | 0.4782 | -0.0388 | 1242 | 0.9694 |
| suave | 12 | 0.5130 | 0.0162 | 686 | 0.9388 |
