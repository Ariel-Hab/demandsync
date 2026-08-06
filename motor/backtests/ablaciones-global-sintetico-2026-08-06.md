# Ablaciones del modelo global — sintetico (2026-08-06)

Modelo global LightGBM (`GlobalLGBM`), multi-horizonte directo con `max_horizon=12`.

- **Productos:** 400 de 2295 · **cortes:** 18 · **horizonte:** 12
- **Cobertura esperada por longitud de serie:** 0.8475 — fracción de series con historia suficiente para que `mlforecast` genere los lags. Es la **cota superior** de la cobertura del global, así que una cobertura baja en la tabla no necesariamente es del modelo.
- **Muestreo:** estratificado, hasta 100 por cuadrante, semilla 42 → erratica: 100 · intermitente: 100 · lumpy: 100 · suave: 100

> **Esto NO es el piso ni un champion/challenger.** El gate de M2.3 es que el modelo corra dentro del arnés y sea comparable; elegir dónde reemplaza al baseline es M2.5, y ahí rige la selección prospectiva de ADR-016. Esta tabla solo decide **con qué configuración** el global llega a esa comparación.

> **El sintético no valida calidad predictiva** — reproduce propiedades estadísticas, no la señal del negocio. Sirve para comparar variantes entre sí (mismo dataset, misma muestra), no para anticipar el número real.

## Corrida

| id | fecha_ejecucion | n_cortes | horizonte_max | columnas_id | columna_objetivo | densificado | primer_corte | ultimo_corte | datos_filas | datos_series | datos_primer_mes | datos_ultimo_mes | datos_suma_objetivo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| be8823f67f16 | 2026-08-06 | 18 | 12 | ('id_producto',) | unidades | True | 2024-12-01 | 2026-05-01 | 27683 | 400 | 2018-07-01 | 2026-06-01 | 517206.8400 |

## Por cuadrante de intermitencia y horizonte

| variante | cuadrante | horizonte | wape | n | cobertura | sesgo |
|---|---|---|---|---|---|---|
| precio+crudo | erratica | 1 | 1.0059 | 1647 | 0.9903 | 0.0006 |
| precio+crudo | erratica | 3 | 0.9312 | 1478 | 0.9682 | -0.0791 |
| precio+crudo | erratica | 6 | 0.9383 | 1220 | 0.9361 | -0.0330 |
| precio+crudo | erratica | 12 | 0.8992 | 682 | 0.8768 | 0.0800 |
| precio+crudo | intermitente | 1 | 1.1826 | 1690 | 0.9923 | -0.0845 |
| precio+crudo | intermitente | 3 | 1.1778 | 1516 | 0.9743 | 0.1284 |
| precio+crudo | intermitente | 6 | 1.2560 | 1249 | 0.9464 | 0.2932 |
| precio+crudo | intermitente | 12 | 1.1796 | 691 | 0.8958 | 0.3680 |
| precio+crudo | lumpy | 1 | 1.3900 | 1766 | 0.9983 | -0.0804 |
| precio+crudo | lumpy | 3 | 1.3964 | 1572 | 0.9943 | 0.0696 |
| precio+crudo | lumpy | 6 | 1.4583 | 1281 | 0.9867 | 0.1153 |
| precio+crudo | lumpy | 12 | 1.4553 | 697 | 0.9742 | 0.2011 |
| precio+crudo | suave | 1 | 0.5314 | 1702 | 0.9953 | 0.0693 |
| precio+crudo | suave | 3 | 0.4361 | 1518 | 0.9862 | 0.0158 |
| precio+crudo | suave | 6 | 0.4769 | 1242 | 0.9694 | -0.0055 |
| precio+crudo | suave | 12 | 0.5211 | 686 | 0.9388 | 0.0246 |
| precio+escalado | erratica | 1 | 1.1416 | 1647 | 0.9903 | 0.3062 |
| precio+escalado | erratica | 3 | 0.9155 | 1478 | 0.9682 | 0.0679 |
| precio+escalado | erratica | 6 | 0.9200 | 1220 | 0.9361 | 0.1338 |
| precio+escalado | erratica | 12 | 0.8882 | 682 | 0.8768 | 0.2079 |
| precio+escalado | intermitente | 1 | 1.1367 | 1690 | 0.9923 | -0.0652 |
| precio+escalado | intermitente | 3 | 1.1376 | 1516 | 0.9743 | 0.2535 |
| precio+escalado | intermitente | 6 | 1.1844 | 1249 | 0.9464 | 0.3307 |
| precio+escalado | intermitente | 12 | 1.1353 | 691 | 0.8958 | 0.4227 |
| precio+escalado | lumpy | 1 | 1.3891 | 1766 | 0.9983 | -0.0260 |
| precio+escalado | lumpy | 3 | 1.4557 | 1572 | 0.9943 | 0.1789 |
| precio+escalado | lumpy | 6 | 1.4438 | 1281 | 0.9867 | 0.1595 |
| precio+escalado | lumpy | 12 | 1.4667 | 697 | 0.9742 | 0.2461 |
| precio+escalado | suave | 1 | 0.4659 | 1702 | 0.9953 | 0.0405 |
| precio+escalado | suave | 3 | 0.3964 | 1518 | 0.9862 | -0.0034 |
| precio+escalado | suave | 6 | 0.4153 | 1242 | 0.9694 | 0.0059 |
| precio+escalado | suave | 12 | 0.4397 | 686 | 0.9388 | 0.0252 |
| sin_precio+crudo | erratica | 1 | 0.9437 | 1647 | 0.9903 | -0.0532 |
| sin_precio+crudo | erratica | 3 | 0.9425 | 1478 | 0.9682 | -0.0683 |
| sin_precio+crudo | erratica | 6 | 0.9063 | 1220 | 0.9361 | -0.0431 |
| sin_precio+crudo | erratica | 12 | 0.9404 | 682 | 0.8768 | 0.0815 |
| sin_precio+crudo | intermitente | 1 | 1.1601 | 1690 | 0.9923 | 0.1090 |
| sin_precio+crudo | intermitente | 3 | 1.1629 | 1516 | 0.9743 | 0.1018 |
| sin_precio+crudo | intermitente | 6 | 1.2506 | 1249 | 0.9464 | 0.2804 |
| sin_precio+crudo | intermitente | 12 | 1.2047 | 691 | 0.8958 | 0.4212 |
| sin_precio+crudo | lumpy | 1 | 1.3904 | 1766 | 0.9983 | 0.0779 |
| sin_precio+crudo | lumpy | 3 | 1.4055 | 1572 | 0.9943 | 0.0803 |
| sin_precio+crudo | lumpy | 6 | 1.4853 | 1281 | 0.9867 | 0.1462 |
| sin_precio+crudo | lumpy | 12 | 1.4724 | 697 | 0.9742 | 0.2512 |
| sin_precio+crudo | suave | 1 | 0.4600 | 1702 | 0.9953 | -0.0104 |
| sin_precio+crudo | suave | 3 | 0.4450 | 1518 | 0.9862 | 0.0095 |
| sin_precio+crudo | suave | 6 | 0.4696 | 1242 | 0.9694 | -0.0080 |
| sin_precio+crudo | suave | 12 | 0.5098 | 686 | 0.9388 | 0.0337 |
| sin_precio+escalado | erratica | 1 | 0.9266 | 1647 | 0.9903 | 0.0662 |
| sin_precio+escalado | erratica | 3 | 0.9351 | 1478 | 0.9682 | 0.1001 |
| sin_precio+escalado | erratica | 6 | 0.9125 | 1220 | 0.9361 | 0.1394 |
| sin_precio+escalado | erratica | 12 | 0.8861 | 682 | 0.8768 | 0.1989 |
| sin_precio+escalado | intermitente | 1 | 1.1597 | 1690 | 0.9923 | 0.2165 |
| sin_precio+escalado | intermitente | 3 | 1.1352 | 1516 | 0.9743 | 0.2412 |
| sin_precio+escalado | intermitente | 6 | 1.1816 | 1249 | 0.9464 | 0.3322 |
| sin_precio+escalado | intermitente | 12 | 1.1178 | 691 | 0.8958 | 0.3942 |
| sin_precio+escalado | lumpy | 1 | 1.4022 | 1766 | 0.9983 | 0.1245 |
| sin_precio+escalado | lumpy | 3 | 1.4371 | 1572 | 0.9943 | 0.1635 |
| sin_precio+escalado | lumpy | 6 | 1.4399 | 1281 | 0.9867 | 0.1593 |
| sin_precio+escalado | lumpy | 12 | 1.4320 | 697 | 0.9742 | 0.1968 |
| sin_precio+escalado | suave | 1 | 0.4153 | 1702 | 0.9953 | 0.0107 |
| sin_precio+escalado | suave | 3 | 0.4017 | 1518 | 0.9862 | -0.0041 |
| sin_precio+escalado | suave | 6 | 0.4162 | 1242 | 0.9694 | 0.0096 |
| sin_precio+escalado | suave | 12 | 0.4456 | 686 | 0.9388 | 0.0210 |

## por_variante

| variante | nivel | horizonte | wape | n | cobertura | sesgo |
|---|---|---|---|---|---|---|
| precio+crudo | producto | 1 | 0.9360 | 6805 | 0.9941 | -0.0017 |
| precio+crudo | producto | 3 | 0.8736 | 6084 | 0.9809 | 0.0031 |
| precio+crudo | producto | 6 | 0.9122 | 4992 | 0.9599 | 0.0447 |
| precio+crudo | producto | 12 | 0.8883 | 2756 | 0.9216 | 0.1195 |
| precio+crudo | total | 1 | 0.1183 | 18 | 1.0000 | -0.0113 |
| precio+crudo | total | 3 | 0.1391 | 16 | 1.0000 | -0.0181 |
| precio+crudo | total | 6 | 0.1365 | 13 | 1.0000 | 0.0072 |
| precio+crudo | total | 12 | 0.1743 | 7 | 1.0000 | 0.0461 |
| precio+escalado | producto | 1 | 0.9606 | 6805 | 0.9941 | 0.1180 |
| precio+escalado | producto | 3 | 0.8572 | 6084 | 0.9809 | 0.0878 |
| precio+escalado | producto | 6 | 0.8728 | 4992 | 0.9599 | 0.1241 |
| precio+escalado | producto | 12 | 0.8514 | 2756 | 0.9216 | 0.1810 |
| precio+escalado | total | 1 | 0.1199 | 18 | 1.0000 | 0.1084 |
| precio+escalado | total | 3 | 0.1380 | 16 | 1.0000 | 0.0667 |
| precio+escalado | total | 6 | 0.1175 | 13 | 1.0000 | 0.0867 |
| precio+escalado | total | 12 | 0.1708 | 7 | 1.0000 | 0.1075 |
| sin_precio+crudo | producto | 1 | 0.8858 | 6805 | 0.9941 | 0.0035 |
| sin_precio+crudo | producto | 3 | 0.8800 | 6084 | 0.9809 | 0.0029 |
| sin_precio+crudo | producto | 6 | 0.9009 | 4992 | 0.9599 | 0.0429 |
| sin_precio+crudo | producto | 12 | 0.9055 | 2756 | 0.9216 | 0.1381 |
| sin_precio+crudo | total | 1 | 0.1279 | 18 | 1.0000 | -0.0061 |
| sin_precio+crudo | total | 3 | 0.1378 | 16 | 1.0000 | -0.0183 |
| sin_precio+crudo | total | 6 | 0.1252 | 13 | 1.0000 | 0.0054 |
| sin_precio+crudo | total | 12 | 0.1655 | 7 | 1.0000 | 0.0646 |
| sin_precio+escalado | producto | 1 | 0.8666 | 6805 | 0.9941 | 0.0790 |
| sin_precio+escalado | producto | 3 | 0.8635 | 6084 | 0.9809 | 0.0961 |
| sin_precio+escalado | producto | 6 | 0.8693 | 4992 | 0.9599 | 0.1276 |
| sin_precio+escalado | producto | 12 | 0.8451 | 2756 | 0.9216 | 0.1650 |
| sin_precio+escalado | total | 1 | 0.1143 | 18 | 1.0000 | 0.0695 |
| sin_precio+escalado | total | 3 | 0.1384 | 16 | 1.0000 | 0.0750 |
| sin_precio+escalado | total | 6 | 0.1247 | 13 | 1.0000 | 0.0901 |
| sin_precio+escalado | total | 12 | 0.1578 | 7 | 1.0000 | 0.0916 |

## costo

| variante | minutos |
|---|---|
| precio+crudo | 0.0000 |
| precio+escalado | 0.0000 |
| sin_precio+crudo | 0.0000 |
| sin_precio+escalado | 0.0000 |
