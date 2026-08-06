# Ablaciones del modelo global — real (2026-08-06)

Modelo global LightGBM (`GlobalLGBM`), multi-horizonte directo con `max_horizon=12`.

- **Productos:** 2128 de 2128 · **cortes:** 18 · **horizonte:** 12
- **Cobertura esperada por longitud de serie:** 0.8393 — fracción de series con historia suficiente para que `mlforecast` genere los lags. Es la **cota superior** de la cobertura del global, así que una cobertura baja en la tabla no necesariamente es del modelo.

> **Esto NO es el piso ni un champion/challenger.** El gate de M2.3 es que el modelo corra dentro del arnés y sea comparable; elegir dónde reemplaza al baseline es M2.5, y ahí rige la selección prospectiva de ADR-016. Esta tabla solo decide **con qué configuración** el global llega a esa comparación.

> **El sintético no valida calidad predictiva** — reproduce propiedades estadísticas, no la señal del negocio. Sirve para comparar variantes entre sí (mismo dataset, misma muestra), no para anticipar el número real.

## Corrida

| id | fecha_ejecucion | n_cortes | horizonte_max | columnas_id | columna_objetivo | densificado | primer_corte | ultimo_corte | datos_filas | datos_series | datos_primer_mes | datos_ultimo_mes | datos_suma_objetivo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a79a9b23676b | 2026-08-06 | 18 | 12 | ('id_producto',) | unidades | True | 2024-11-01 | 2026-04-01 | 157431 | 2128 | 2018-07-01 | 2026-05-01 | 31122141.0000 |

## Por cuadrante de intermitencia y horizonte

| variante | cuadrante | horizonte | wape | n | cobertura | sesgo |
|---|---|---|---|---|---|---|
| precio+crudo | erratica | 1 | 0.4426 | 4221 | 0.9955 | 0.0220 |
| precio+crudo | erratica | 3 | 0.5247 | 3772 | 0.9873 | 0.0240 |
| precio+crudo | erratica | 6 | 0.6174 | 3087 | 0.9741 | 0.0167 |
| precio+crudo | erratica | 12 | 0.5789 | 1673 | 0.9474 | 0.0496 |
| precio+crudo | intermitente | 1 | 0.9603 | 7867 | 0.9865 | 0.4574 |
| precio+crudo | intermitente | 3 | 1.8750 | 7093 | 0.9578 | 1.3699 |
| precio+crudo | intermitente | 6 | 2.7000 | 5901 | 0.9110 | 2.2977 |
| precio+crudo | intermitente | 12 | 3.4260 | 3333 | 0.8266 | 3.0806 |
| precio+crudo | lumpy | 1 | 1.1783 | 3142 | 0.9981 | 0.5914 |
| precio+crudo | lumpy | 3 | 2.0442 | 2798 | 0.9943 | 1.4522 |
| precio+crudo | lumpy | 6 | 3.0773 | 2281 | 0.9868 | 2.4415 |
| precio+crudo | lumpy | 12 | 5.6294 | 1237 | 0.9741 | 5.1088 |
| precio+crudo | suave | 1 | 0.2654 | 20773 | 0.9937 | -0.0128 |
| precio+crudo | suave | 3 | 0.3022 | 18572 | 0.9823 | -0.0073 |
| precio+crudo | suave | 6 | 0.3276 | 15244 | 0.9626 | -0.0101 |
| precio+crudo | suave | 12 | 0.3149 | 8363 | 0.9269 | -0.0043 |
| precio+escalado | erratica | 1 | 0.4781 | 4221 | 0.9955 | 0.0350 |
| precio+escalado | erratica | 3 | 0.6151 | 3772 | 0.9873 | 0.0811 |
| precio+escalado | erratica | 6 | 0.7233 | 3087 | 0.9741 | 0.0909 |
| precio+escalado | erratica | 12 | 0.7815 | 1673 | 0.9474 | 0.1682 |
| precio+escalado | intermitente | 1 | 0.6751 | 7867 | 0.9865 | 0.1971 |
| precio+escalado | intermitente | 3 | 2.5415 | 7093 | 0.9578 | 1.9305 |
| precio+escalado | intermitente | 6 | 4.5524 | 5901 | 0.9110 | 3.9324 |
| precio+escalado | intermitente | 12 | 10.2251 | 3333 | 0.8266 | 9.4434 |
| precio+escalado | lumpy | 1 | 1.2639 | 3142 | 0.9981 | 0.7029 |
| precio+escalado | lumpy | 3 | 2.2985 | 2798 | 0.9943 | 1.6809 |
| precio+escalado | lumpy | 6 | 3.5875 | 2281 | 0.9868 | 2.8807 |
| precio+escalado | lumpy | 12 | 6.3471 | 1237 | 0.9741 | 5.7535 |
| precio+escalado | suave | 1 | 0.2646 | 20773 | 0.9937 | 0.0051 |
| precio+escalado | suave | 3 | 0.3203 | 18572 | 0.9823 | -0.0100 |
| precio+escalado | suave | 6 | 0.3651 | 15244 | 0.9626 | -0.0340 |
| precio+escalado | suave | 12 | 0.3893 | 8363 | 0.9269 | -0.0159 |
| sin_precio+crudo | erratica | 1 | 0.4407 | 4221 | 0.9955 | 0.0232 |
| sin_precio+crudo | erratica | 3 | 0.5132 | 3772 | 0.9873 | 0.0206 |
| sin_precio+crudo | erratica | 6 | 0.6007 | 3087 | 0.9741 | 0.0197 |
| sin_precio+crudo | erratica | 12 | 0.6073 | 1673 | 0.9474 | 0.0832 |
| sin_precio+crudo | intermitente | 1 | 1.6164 | 7867 | 0.9865 | 1.1365 |
| sin_precio+crudo | intermitente | 3 | 2.2662 | 7093 | 0.9578 | 1.8119 |
| sin_precio+crudo | intermitente | 6 | 2.9706 | 5901 | 0.9110 | 2.5724 |
| sin_precio+crudo | intermitente | 12 | 3.8786 | 3333 | 0.8266 | 3.6284 |
| sin_precio+crudo | lumpy | 1 | 1.4643 | 3142 | 0.9981 | 0.9410 |
| sin_precio+crudo | lumpy | 3 | 2.2351 | 2798 | 0.9943 | 1.7021 |
| sin_precio+crudo | lumpy | 6 | 3.1904 | 2281 | 0.9868 | 2.5738 |
| sin_precio+crudo | lumpy | 12 | 6.0109 | 1237 | 0.9741 | 5.4729 |
| sin_precio+crudo | suave | 1 | 0.2630 | 20773 | 0.9937 | 0.0012 |
| sin_precio+crudo | suave | 3 | 0.3023 | 18572 | 0.9823 | -0.0013 |
| sin_precio+crudo | suave | 6 | 0.3338 | 15244 | 0.9626 | 0.0080 |
| sin_precio+crudo | suave | 12 | 0.3345 | 8363 | 0.9269 | 0.0332 |
| sin_precio+escalado | erratica | 1 | 0.4808 | 4221 | 0.9955 | 0.0376 |
| sin_precio+escalado | erratica | 3 | 0.6139 | 3772 | 0.9873 | 0.0716 |
| sin_precio+escalado | erratica | 6 | 0.7166 | 3087 | 0.9741 | 0.0801 |
| sin_precio+escalado | erratica | 12 | 0.7731 | 1673 | 0.9474 | 0.1603 |
| sin_precio+escalado | intermitente | 1 | 1.8259 | 7867 | 0.9865 | 1.2886 |
| sin_precio+escalado | intermitente | 3 | 3.3556 | 7093 | 0.9578 | 2.7496 |
| sin_precio+escalado | intermitente | 6 | 5.6207 | 5901 | 0.9110 | 4.9909 |
| sin_precio+escalado | intermitente | 12 | 11.0726 | 3333 | 0.8266 | 10.2753 |
| sin_precio+escalado | lumpy | 1 | 1.5270 | 3142 | 0.9981 | 0.9851 |
| sin_precio+escalado | lumpy | 3 | 2.5519 | 2798 | 0.9943 | 1.9343 |
| sin_precio+escalado | lumpy | 6 | 3.7244 | 2281 | 0.9868 | 3.0515 |
| sin_precio+escalado | lumpy | 12 | 6.6129 | 1237 | 0.9741 | 5.9967 |
| sin_precio+escalado | suave | 1 | 0.2600 | 20773 | 0.9937 | -0.0113 |
| sin_precio+escalado | suave | 3 | 0.3199 | 18572 | 0.9823 | -0.0230 |
| sin_precio+escalado | suave | 6 | 0.3681 | 15244 | 0.9626 | -0.0410 |
| sin_precio+escalado | suave | 12 | 0.3907 | 8363 | 0.9269 | -0.0170 |

## por_variante

| variante | nivel | horizonte | wape | n | cobertura | sesgo |
|---|---|---|---|---|---|---|
| precio+crudo | producto | 1 | 0.2953 | 36003 | 0.9927 | -0.0040 |
| precio+crudo | producto | 3 | 0.3435 | 32235 | 0.9786 | 0.0074 |
| precio+crudo | producto | 6 | 0.3834 | 26513 | 0.9546 | 0.0097 |
| precio+crudo | producto | 12 | 0.3746 | 14606 | 0.9104 | 0.0258 |
| precio+crudo | categoria | 1 | 0.1208 | 216 | 1.0000 | -0.0062 |
| precio+crudo | categoria | 3 | 0.1428 | 192 | 1.0000 | 0.0011 |
| precio+crudo | categoria | 6 | 0.1831 | 156 | 1.0000 | -0.0065 |
| precio+crudo | categoria | 12 | 0.1503 | 84 | 1.0000 | -0.0183 |
| precio+crudo | total | 1 | 0.0934 | 18 | 1.0000 | -0.0062 |
| precio+crudo | total | 3 | 0.0906 | 16 | 1.0000 | 0.0011 |
| precio+crudo | total | 6 | 0.1164 | 13 | 1.0000 | -0.0065 |
| precio+crudo | total | 12 | 0.0811 | 7 | 1.0000 | -0.0183 |
| precio+escalado | producto | 1 | 0.2982 | 36003 | 0.9927 | 0.0123 |
| precio+escalado | producto | 3 | 0.3748 | 32235 | 0.9786 | 0.0158 |
| precio+escalado | producto | 6 | 0.4390 | 26513 | 0.9546 | 0.0072 |
| precio+escalado | producto | 12 | 0.4949 | 14606 | 0.9104 | 0.0590 |
| precio+escalado | categoria | 1 | 0.1357 | 216 | 1.0000 | 0.0100 |
| precio+escalado | categoria | 3 | 0.1747 | 192 | 1.0000 | 0.0095 |
| precio+escalado | categoria | 6 | 0.1958 | 156 | 1.0000 | -0.0090 |
| precio+escalado | categoria | 12 | 0.1864 | 84 | 1.0000 | 0.0149 |
| precio+escalado | total | 1 | 0.1112 | 18 | 1.0000 | 0.0100 |
| precio+escalado | total | 3 | 0.1264 | 16 | 1.0000 | 0.0095 |
| precio+escalado | total | 6 | 0.1258 | 13 | 1.0000 | -0.0090 |
| precio+escalado | total | 12 | 0.0917 | 7 | 1.0000 | 0.0149 |
| sin_precio+crudo | producto | 1 | 0.2969 | 36003 | 0.9927 | 0.0125 |
| sin_precio+crudo | producto | 3 | 0.3445 | 32235 | 0.9786 | 0.0148 |
| sin_precio+crudo | producto | 6 | 0.3879 | 26513 | 0.9546 | 0.0271 |
| sin_precio+crudo | producto | 12 | 0.3979 | 14606 | 0.9104 | 0.0654 |
| sin_precio+crudo | categoria | 1 | 0.1255 | 216 | 1.0000 | 0.0103 |
| sin_precio+crudo | categoria | 3 | 0.1399 | 192 | 1.0000 | 0.0086 |
| sin_precio+crudo | categoria | 6 | 0.1746 | 156 | 1.0000 | 0.0110 |
| sin_precio+crudo | categoria | 12 | 0.1665 | 84 | 1.0000 | 0.0213 |
| sin_precio+crudo | total | 1 | 0.0961 | 18 | 1.0000 | 0.0103 |
| sin_precio+crudo | total | 3 | 0.0916 | 16 | 1.0000 | 0.0086 |
| sin_precio+crudo | total | 6 | 0.1069 | 13 | 1.0000 | 0.0110 |
| sin_precio+crudo | total | 12 | 0.0856 | 7 | 1.0000 | 0.0213 |
| sin_precio+escalado | producto | 1 | 0.3009 | 36003 | 0.9927 | 0.0045 |
| sin_precio+escalado | producto | 3 | 0.3788 | 32235 | 0.9786 | 0.0078 |
| sin_precio+escalado | producto | 6 | 0.4457 | 26513 | 0.9546 | 0.0047 |
| sin_precio+escalado | producto | 12 | 0.4988 | 14606 | 0.9104 | 0.0608 |
| sin_precio+escalado | categoria | 1 | 0.1327 | 216 | 1.0000 | 0.0023 |
| sin_precio+escalado | categoria | 3 | 0.1699 | 192 | 1.0000 | 0.0015 |
| sin_precio+escalado | categoria | 6 | 0.1988 | 156 | 1.0000 | -0.0115 |
| sin_precio+escalado | categoria | 12 | 0.1854 | 84 | 1.0000 | 0.0168 |
| sin_precio+escalado | total | 1 | 0.1040 | 18 | 1.0000 | 0.0023 |
| sin_precio+escalado | total | 3 | 0.1201 | 16 | 1.0000 | 0.0015 |
| sin_precio+escalado | total | 6 | 0.1260 | 13 | 1.0000 | -0.0115 |
| sin_precio+escalado | total | 12 | 0.0921 | 7 | 1.0000 | 0.0168 |

## costo

| variante | minutos |
|---|---|
| precio+crudo | 0.0000 |
| precio+escalado | 0.0000 |
| sin_precio+crudo | 0.0000 |
| sin_precio+escalado | 0.0000 |
