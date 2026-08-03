# Piso de baselines — real (2026-07-31)

> 🛑 **SUPERADA — y su nota de cobertura tiene un error.** El piso vigente es
> `baselines-real-2026-08-03.md` (corrida `a79a9b23676b`): esta tabla midió sobre un universo
> con obsequios y con 2026-06 al 32% de carga (ADR-012, M1.8b). **Errata, agregada el
> 2026-08-03:** donde la nota de abajo dice "el 100,00% de las 13.889 filas sin predicción",
> el total real de filas sin predicción del modelo seleccionado —lo que mide la columna
> `cobertura`— es **20.174 (6,41%)**, no 13.889 (4,41%). Las 13.889 son solo las filas donde
> **ningún** candidato predijo. Las **6.285 restantes (31,15%)** son series jóvenes cuyo
> ganador retrospectivo no llegaba al horizonte pedido, y ahí otros candidatos sí predijeron;
> el "cero filas sin explicar" es falso. **No se corrigió ningún número de las tablas** —
> siguen siendo el registro auditable de la corrida `f7af767ca7e6`. Diagnóstico completo en
> `roadmap-motor.md` §5.6.1 y en la nota del piso vigente.

Selección por serie (M1.7) entre 7 candidatos: `SeasonalNaive`, `WindowAverage`, `AutoETS`, `AutoTheta`, `AutoARIMA`, `CrostonSBA`, `TSB`.

- **Productos:** 2189 · **cortes:** 18 · **horizonte:** 12 · **n_jobs:** 4
- **Tiempo de backtest:** 214.1 min
- **Series con ganador asignado:** 2186

> ⚠️ **La cobertura NO es 1,0 a grano producto: baja de 0,9918 (h=1) a 0,8794 (h=12).**
> Son filas con valor real y **sin predicción de ningún candidato**, así que el WAPE de
> esta tabla está mejorado por omitir series, no por acertar más. Condición 4 de
> `backtests/README.md`; la causa se diagnosticó antes de congelar y es la de abajo.
>
> **Causa: altas de catálogo.** El **100,00%** de las 13.889 filas sin predicción (4,41%
> del reporte crudo) son productos cuya **primera venta es posterior al corte** — 277
> series, de 301 productos que entraron al catálogo desde 2024-12. Cero filas sin
> explicar, cero bajas. Un baseline univariado no puede predecir una serie que todavía no
> existía en el corte: el arnés registra el real (densificado, ADR-010) y ninguna
> predicción, y la cobertura lo hace visible en vez de taparlo. **No es un defecto de la
> corrida.**
>
> Por eso `SIN CATEGORIA` cae a **0,5203** a h=12: 252 de esos 301 productos nuevos no
> tienen categoría asignada todavía. Leer esa fila como "la categoría se predice mal"
> sería un error — casi la mitad de sus filas no se predijo en absoluto.
>
> **Consecuencia para M2:** los productos nuevos son el caso de mayor incertidumbre y
> **ningún baseline los cubre**. Es un hueco que el modelo global sí podría llenar con
> features de categoría/laboratorio (arranque en frío). Comparar M2 contra este piso a
> igual cobertura, o la comparación no es justa en ninguna de las dos direcciones.
>
> Esta nota se agregó a mano tras el diagnóstico. El script ya emite la advertencia
> genérica de cobertura por su cuenta (`_nota_de_cobertura`), pero la causa concreta no
> la puede deducir solo.

> **La selección por serie es retrospectiva, así que este piso es optimista.** El ganador de cada serie se eligió con el MASE de todos los cortes y se aplicó también a los más viejos, es decir con información posterior a las filas donde se mide. Es lo que especifica `plan-diseno.md` §M1 y la convención para fijar una referencia fuerte, pero **no es un procedimiento prospectivo** y por lo tanto este piso está más alto que el de un pipeline que eligiera el método en cada corte con datos ≤ corte. Antes del champion/challenger de M2.5 hay que nivelar la comparación — ver `roadmap-motor.md` §12.5.

> Las predicciones individuales **sí** son limpias: el arnés garantiza historia ≤ corte en cada una (M1.3). Lo retrospectivo es la elección de *qué modelo* mirar, no lo que cada modelo vio.

## Corrida

| id | fecha_ejecucion | n_cortes | horizonte_max | columnas_id | columna_objetivo | densificado | primer_corte | ultimo_corte | datos_filas | datos_series | datos_primer_mes | datos_ultimo_mes | datos_suma_objetivo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| f7af767ca7e6 | 2026-07-31 | 18 | 12 | ('id_producto',) | unidades | True | 2024-12-01 | 2026-05-01 | 161878 | 2189 | 2018-07-01 | 2026-06-01 | 31244972.0000 |

## Modelo ganador por cuadrante (selección por serie, M1.7)

| modelo_ganador | erratica | intermitente | lumpy | suave | total |
|---|---|---|---|---|---|
| SeasonalNaive | 72 | 257 | 31 | 318 | 678 |
| CrostonSBA | 44 | 21 | 16 | 322 | 403 |
| AutoARIMA | 47 | 82 | 63 | 132 | 324 |
| WindowAverage | 31 | 140 | 60 | 55 | 286 |
| AutoETS | 28 | 13 | 8 | 151 | 200 |
| AutoTheta | 30 | 18 | 14 | 134 | 196 |
| TSB | 14 | 10 | 7 | 68 | 99 |

## Por nivel de agregación y horizonte

| nivel | horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|---|
| producto | 1 | 0.3241 | -0.0120 | 37097 | 0.9918 |
| producto | 3 | 0.3380 | 0.0022 | 33228 | 0.9636 |
| producto | 6 | 0.3538 | 0.0150 | 27350 | 0.9249 |
| producto | 12 | 0.3470 | 0.0521 | 15085 | 0.8794 |
| categoria | 1 | 0.1506 | -0.0136 | 216 | 1.0000 |
| categoria | 3 | 0.1667 | -0.0100 | 192 | 1.0000 |
| categoria | 6 | 0.2096 | -0.0213 | 156 | 1.0000 |
| categoria | 12 | 0.2229 | -0.0197 | 84 | 1.0000 |
| total | 1 | 0.1223 | -0.0136 | 18 | 1.0000 |
| total | 3 | 0.1271 | -0.0100 | 16 | 1.0000 |
| total | 6 | 0.1574 | -0.0213 | 13 | 1.0000 |
| total | 12 | 0.1544 | -0.0197 | 7 | 1.0000 |

## Por horizonte (grano producto)

| horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|
| 1 | 0.3241 | -0.0120 | 37097 | 0.9918 |
| 3 | 0.3380 | 0.0022 | 33228 | 0.9636 |
| 6 | 0.3538 | 0.0150 | 27350 | 0.9249 |
| 12 | 0.3470 | 0.0521 | 15085 | 0.8794 |

## Por categoría y horizonte

| categoria | horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|---|
| ACCESORIO | 1 | 0.8975 | -0.3066 | 342 | 1.0000 |
| ACCESORIO | 3 | 0.9016 | -0.3575 | 304 | 1.0000 |
| ACCESORIO | 6 | 0.8530 | -0.4241 | 247 | 1.0000 |
| ACCESORIO | 12 | 0.8444 | -0.4560 | 133 | 1.0000 |
| ALIMENTO | 1 | 0.2670 | -0.0202 | 828 | 1.0000 |
| ALIMENTO | 3 | 0.2658 | -0.0241 | 736 | 1.0000 |
| ALIMENTO | 6 | 0.2776 | -0.0223 | 598 | 1.0000 |
| ALIMENTO | 12 | 0.3308 | 0.0574 | 322 | 1.0000 |
| ANTIARTROSICO | 1 | 0.2541 | -0.0588 | 774 | 1.0000 |
| ANTIARTROSICO | 3 | 0.2663 | -0.0875 | 688 | 1.0000 |
| ANTIARTROSICO | 6 | 0.2926 | -0.1236 | 559 | 1.0000 |
| ANTIARTROSICO | 12 | 0.3347 | -0.1363 | 301 | 1.0000 |
| ANTIPARASITARIO EXTERNO | 1 | 0.3581 | -0.0039 | 6313 | 0.9948 |
| ANTIPARASITARIO EXTERNO | 3 | 0.3688 | 0.0162 | 5639 | 0.9759 |
| ANTIPARASITARIO EXTERNO | 6 | 0.3957 | 0.0557 | 4621 | 0.9433 |
| ANTIPARASITARIO EXTERNO | 12 | 0.3649 | 0.1677 | 2512 | 0.9057 |
| ANTIPARASITARIO INTERNO | 1 | 0.2336 | 0.0334 | 2448 | 1.0000 |
| ANTIPARASITARIO INTERNO | 3 | 0.2438 | 0.0513 | 2176 | 1.0000 |
| ANTIPARASITARIO INTERNO | 6 | 0.2726 | 0.0747 | 1768 | 1.0000 |
| ANTIPARASITARIO INTERNO | 12 | 0.3180 | 0.1040 | 952 | 1.0000 |
| BIOLOGICO | 1 | 0.3642 | 0.0272 | 779 | 0.9987 |
| BIOLOGICO | 3 | 0.4256 | 0.0605 | 693 | 0.9913 |
| BIOLOGICO | 6 | 0.4396 | 0.0369 | 564 | 0.9840 |
| BIOLOGICO | 12 | 0.4644 | -0.0224 | 306 | 0.9608 |
| CARDIOLOGICO | 1 | 0.1878 | -0.0122 | 1134 | 1.0000 |
| CARDIOLOGICO | 3 | 0.1958 | -0.0189 | 1008 | 1.0000 |
| CARDIOLOGICO | 6 | 0.2048 | -0.0351 | 819 | 1.0000 |
| CARDIOLOGICO | 12 | 0.2509 | -0.0277 | 441 | 1.0000 |
| CLINICO | 1 | 0.2459 | -0.0322 | 12986 | 0.9995 |
| CLINICO | 3 | 0.2508 | -0.0393 | 11550 | 0.9981 |
| CLINICO | 6 | 0.2650 | -0.0463 | 9390 | 0.9958 |
| CLINICO | 12 | 0.2948 | -0.0640 | 5061 | 0.9931 |
| DESCARTABLES | 1 | 0.3539 | 0.0028 | 918 | 1.0000 |
| DESCARTABLES | 3 | 0.3709 | 0.0183 | 816 | 1.0000 |
| DESCARTABLES | 6 | 0.3988 | 0.0250 | 663 | 1.0000 |
| DESCARTABLES | 12 | 0.5037 | 0.0947 | 357 | 1.0000 |
| HIGIENE Y BELLEZA | 1 | 0.2411 | -0.0023 | 3834 | 1.0000 |
| HIGIENE Y BELLEZA | 3 | 0.2528 | 0.0019 | 3408 | 1.0000 |
| HIGIENE Y BELLEZA | 6 | 0.2759 | 0.0002 | 2769 | 1.0000 |
| HIGIENE Y BELLEZA | 12 | 0.2838 | -0.0261 | 1491 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 1 | 0.3036 | 0.0049 | 18 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 3 | 0.3121 | -0.0156 | 16 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 6 | 0.3265 | -0.0436 | 13 | 1.0000 |
| HIGIENE Y BELLEZA (odontologico) | 12 | 0.4498 | 0.0345 | 7 | 1.0000 |
| SIN CATEGORIA | 1 | 0.5405 | -0.2114 | 6723 | 0.9604 |
| SIN CATEGORIA | 3 | 0.4874 | -0.1674 | 6194 | 0.8311 |
| SIN CATEGORIA | 6 | 0.3536 | -0.1768 | 5339 | 0.6733 |
| SIN CATEGORIA | 12 | 0.2072 | -0.0979 | 3202 | 0.5203 |

## Por cuadrante de intermitencia y horizonte

| cuadrante | horizonte | wape | sesgo | n | cobertura |
|---|---|---|---|---|---|
| erratica | 1 | 0.4806 | -0.0294 | 4627 | 0.9922 |
| erratica | 3 | 0.5221 | -0.0451 | 4136 | 0.9715 |
| erratica | 6 | 0.5275 | -0.0794 | 3392 | 0.9360 |
| erratica | 12 | 0.4390 | -0.0606 | 1844 | 0.8894 |
| intermitente | 1 | 1.0547 | 0.2469 | 8576 | 0.9832 |
| intermitente | 3 | 0.9887 | 0.3037 | 7751 | 0.9192 |
| intermitente | 6 | 1.1371 | 0.4887 | 6480 | 0.8344 |
| intermitente | 12 | 2.0728 | 1.2922 | 3689 | 0.7414 |
| lumpy | 1 | 0.8987 | -0.0178 | 3516 | 0.9963 |
| lumpy | 3 | 0.9968 | -0.0438 | 3132 | 0.9872 |
| lumpy | 6 | 1.2451 | 0.0787 | 2554 | 0.9757 |
| lumpy | 12 | 1.4570 | 0.2361 | 1388 | 0.9481 |
| suave | 1 | 0.2910 | -0.0098 | 20378 | 0.9945 |
| suave | 3 | 0.3006 | 0.0097 | 18209 | 0.9766 |
| suave | 6 | 0.3167 | 0.0308 | 14924 | 0.9530 |
| suave | 12 | 0.3232 | 0.0703 | 8164 | 0.9277 |

## MASE por horizonte

| horizonte | mase_medio | mase_mediana | n |
|---|---|---|---|
| 1 | 0.7249 | 0.5282 | 36820 |
| 3 | 0.7231 | 0.5315 | 32470 |
| 6 | 0.7320 | 0.5398 | 26042 |
| 12 | 0.7526 | 0.5378 | 13666 |
