# Piso de baselines — sintetico (2026-07-30)

Selección por serie (M1.7) entre 7 candidatos: `SeasonalNaive`, `WindowAverage`, `AutoETS`, `AutoTheta`, `AutoARIMA`, `CrostonSBA`, `TSB`.

- **Productos:** 400 · **cortes:** 18 · **horizonte:** 12 · **n_jobs:** 4
- **Tiempo de backtest:** 91.2 min
- **Series con ganador asignado:** 400
- **Muestreo:** estratificado, hasta 100 productos por cuadrante, semilla 42 → erratica: 100 · intermitente: 100 · lumpy: 100 · suave: 100

> **Muestra estratificada de 400 de 2300 productos, no el catálogo completo** — decisión registrada en `roadmap-motor.md` §5.2. El sintético no valida calidad predictiva (reproduce propiedades, no la señal), así que esta tabla acredita que el pipeline de selección corre reproducible de punta a punta; **no es el piso a batir**. El piso es el de M1.8, sobre datos reales. Estratificar además da mejores estadísticas por cuadrante que la distribución natural, donde `lumpy` es ~11%.

> **La selección por serie es retrospectiva, así que este piso es optimista.** El ganador de cada serie se eligió con el MASE de todos los cortes y se aplicó también a los más viejos, es decir con información posterior a las filas donde se mide. Es lo que especifica `plan-diseno.md` §M1 y la convención para fijar una referencia fuerte, pero **no es un procedimiento prospectivo** y por lo tanto este piso está más alto que el de un pipeline que eligiera el método en cada corte con datos ≤ corte. Antes del champion/challenger de M2.5 hay que nivelar la comparación — ver `roadmap-motor.md` §12.5.

> Las predicciones individuales **sí** son limpias: el arnés garantiza historia ≤ corte en cada una (M1.3). Lo retrospectivo es la elección de *qué modelo* mirar, no lo que cada modelo vio.

## Corrida

| id | fecha_ejecucion | n_cortes | horizonte_max | columnas_id | columna_objetivo | densificado | primer_corte | ultimo_corte | datos_filas | datos_series | datos_primer_mes | datos_ultimo_mes | datos_suma_objetivo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| f993bc6ae12e | 2026-07-30 | 18 | 12 | ('id_producto',) | unidades | True | 2024-12-01 | 2026-05-01 | 38095 | 400 | 2018-07-01 | 2026-06-01 | 564266.7800 |

## Modelo ganador por cuadrante (selección por serie, M1.7)

| modelo_ganador | erratica | intermitente | lumpy | suave | total |
|---|---|---|---|---|---|
| AutoARIMA | 26 | 35 | 50 | 16 | 127 |
| AutoETS | 31 | 17 | 8 | 45 | 101 |
| SeasonalNaive | 14 | 21 | 19 | 3 | 57 |
| CrostonSBA | 15 | 6 | 5 | 24 | 50 |
| AutoTheta | 6 | 8 | 6 | 6 | 26 |
| WindowAverage | 4 | 10 | 10 | 2 | 26 |
| TSB | 4 | 3 | 2 | 4 | 13 |

## Por nivel de agregación y horizonte

| nivel | horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|---|
| producto | 1 | 0.8102 | -0.1049 | 7200 | 1.0000 |
| producto | 3 | 0.8070 | -0.1075 | 6400 | 1.0000 |
| producto | 6 | 0.8046 | -0.1308 | 5200 | 1.0000 |
| producto | 12 | 0.8361 | -0.0667 | 2800 | 1.0000 |
| categoria | 1 | 0.2422 | -0.1049 | 144 | 1.0000 |
| categoria | 3 | 0.2591 | -0.1075 | 128 | 1.0000 |
| categoria | 6 | 0.2673 | -0.1308 | 104 | 1.0000 |
| categoria | 12 | 0.2419 | -0.0667 | 56 | 1.0000 |
| total | 1 | 0.1552 | -0.1049 | 18 | 1.0000 |
| total | 3 | 0.1651 | -0.1075 | 16 | 1.0000 |
| total | 6 | 0.1750 | -0.1308 | 13 | 1.0000 |
| total | 12 | 0.1279 | -0.0667 | 7 | 1.0000 |

## Por horizonte (grano producto)

| horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|
| 1 | 0.8102 | -0.1049 | 7200 | 1.0000 |
| 3 | 0.8070 | -0.1075 | 6400 | 1.0000 |
| 6 | 0.8046 | -0.1308 | 5200 | 1.0000 |
| 12 | 0.8361 | -0.0667 | 2800 | 1.0000 |

## Por categoría y horizonte

| categoria | horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|---|
| alimentos_balanceados | 1 | 0.9417 | -0.0961 | 648 | 1.0000 |
| alimentos_balanceados | 3 | 0.9344 | -0.1354 | 576 | 1.0000 |
| alimentos_balanceados | 6 | 0.9395 | -0.1553 | 468 | 1.0000 |
| alimentos_balanceados | 12 | 0.9423 | -0.1317 | 252 | 1.0000 |
| analgesicos | 1 | 0.8065 | -0.0733 | 1044 | 1.0000 |
| analgesicos | 3 | 0.8659 | -0.0686 | 928 | 1.0000 |
| analgesicos | 6 | 0.8708 | -0.0462 | 754 | 1.0000 |
| analgesicos | 12 | 1.0387 | 0.1567 | 406 | 1.0000 |
| antibioticos | 1 | 0.7693 | -0.1252 | 1044 | 1.0000 |
| antibioticos | 3 | 0.7891 | -0.1091 | 928 | 1.0000 |
| antibioticos | 6 | 0.7712 | -0.1004 | 754 | 1.0000 |
| antibioticos | 12 | 0.8227 | -0.0796 | 406 | 1.0000 |
| antiparasitarios | 1 | 0.6512 | -0.0646 | 972 | 1.0000 |
| antiparasitarios | 3 | 0.6512 | -0.0725 | 864 | 1.0000 |
| antiparasitarios | 6 | 0.6466 | -0.1034 | 702 | 1.0000 |
| antiparasitarios | 12 | 0.6345 | -0.0801 | 378 | 1.0000 |
| dermatologicos | 1 | 0.9633 | -0.3232 | 810 | 1.0000 |
| dermatologicos | 3 | 0.9135 | -0.3676 | 720 | 1.0000 |
| dermatologicos | 6 | 0.9453 | -0.4171 | 585 | 1.0000 |
| dermatologicos | 12 | 0.9504 | -0.3425 | 315 | 1.0000 |
| reproductivos | 1 | 0.8257 | -0.1100 | 990 | 1.0000 |
| reproductivos | 3 | 0.8261 | -0.1495 | 880 | 1.0000 |
| reproductivos | 6 | 0.8117 | -0.1872 | 715 | 1.0000 |
| reproductivos | 12 | 0.8098 | -0.1041 | 385 | 1.0000 |
| suplementos | 1 | 0.8385 | -0.0399 | 774 | 1.0000 |
| suplementos | 3 | 0.8005 | -0.0618 | 688 | 1.0000 |
| suplementos | 6 | 0.7826 | -0.1112 | 559 | 1.0000 |
| suplementos | 12 | 0.8774 | -0.0190 | 301 | 1.0000 |
| vacunas | 1 | 0.7883 | -0.0451 | 918 | 1.0000 |
| vacunas | 3 | 0.7519 | 0.0392 | 816 | 1.0000 |
| vacunas | 6 | 0.7588 | -0.0090 | 663 | 1.0000 |
| vacunas | 12 | 0.7336 | 0.0247 | 357 | 1.0000 |

## Por cuadrante de intermitencia y horizonte

| cuadrante | horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|---|
| erratica | 1 | 0.8534 | -0.1219 | 1800 | 1.0000 |
| erratica | 3 | 0.8375 | -0.1046 | 1600 | 1.0000 |
| erratica | 6 | 0.8312 | -0.1595 | 1300 | 1.0000 |
| erratica | 12 | 0.8505 | -0.1762 | 700 | 1.0000 |
| intermitente | 1 | 1.0599 | -0.0593 | 1800 | 1.0000 |
| intermitente | 3 | 1.0968 | -0.0650 | 1600 | 1.0000 |
| intermitente | 6 | 1.1241 | -0.0192 | 1300 | 1.0000 |
| intermitente | 12 | 1.2570 | 0.1464 | 700 | 1.0000 |
| lumpy | 1 | 1.2109 | -0.3273 | 1800 | 1.0000 |
| lumpy | 3 | 1.1612 | -0.3758 | 1600 | 1.0000 |
| lumpy | 6 | 1.1727 | -0.3898 | 1300 | 1.0000 |
| lumpy | 12 | 1.2671 | -0.3016 | 700 | 1.0000 |
| suave | 1 | 0.3946 | 0.0084 | 1800 | 1.0000 |
| suave | 3 | 0.4050 | 0.0187 | 1600 | 1.0000 |
| suave | 6 | 0.3989 | -0.0215 | 1300 | 1.0000 |
| suave | 12 | 0.3986 | 0.0497 | 700 | 1.0000 |

## MASE por horizonte

| horizonte | mase_medio | mase_mediana | n |
|---|---|---|---|
| 1 | 0.7081 | 0.6402 | 7200 |
| 3 | 0.7213 | 0.6571 | 6400 |
| 6 | 0.7433 | 0.6871 | 5200 |
| 12 | 0.7727 | 0.7246 | 2800 |
