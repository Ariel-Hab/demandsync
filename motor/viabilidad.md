# Informe de Viabilidad del Motor de Predicción

**Fecha:** 2026-07-15
**Autor:** ML Specialist
**Pregunta:** ¿es viable implementar el predictor de DemandSync con los datos que realmente tiene el cliente 1 (DFV/defeve), y cómo hay que adecuarse? Validación de lo documentado (docs UTN + correcciones DFV) contra el estado del arte en predicción de demanda.

---

## Veredicto

**Viable, con adecuaciones concretas.** El problema "predecir unidades mensuales por producto para una distribuidora, con 8 años de historia y ~2.600 SKUs" es un problema estándar y bien resuelto en la industria; existen librerías open source maduras que cubren el 90% del modelado. Los riesgos reales del proyecto **no están en el algoritmo**: están en (1) la calidad/preparación de los datos (deduplicación, inflación), (2) la granularidad prometida (cliente×producto es intermitente), y (3) las expectativas sobre horizontes largos (12 meses) y sobre métricas (MAPE). Las cuatro subsecciones de adecuaciones abordan exactamente eso.

---

## 1. Lo que tenemos, en términos del estado del arte

| Dimensión | Dataset cliente 1 | Lectura |
|---|---|---|
| Historia | ~96 meses (2018-09→) | Excelente para frecuencia mensual: 8 ciclos estacionales completos. La mayoría de los casos publicados de farma/distribución trabajan con 21–24 meses |
| Series | ~2.600 productos; ~1.500 clientes | Escala media: suficiente para un modelo global ML (cross-learning), lejos de necesitar infra distribuida |
| Grano | Renglón de comprobante → mensualizable | Correcto. El diseño (hechos mensuales inmutables) es exactamente la práctica recomendada |
| Exógenas | Clima/macro (mock), inflación implícita en precios | Ver §3.4 |
| Stock | Solo foto actual | No afecta el motor de demanda; afecta las capas de negocio (ya resuelto por ADR-004) |

**Clasificación esperada de las series** (a confirmar con el EDA de R0, taxonomía Syntetos-Boylan por ADI/CV²):
- **Nivel producto-mes:** mezcla de series suaves (alta rotación) e intermitentes (cola larga del vademécum).
- **Nivel cliente×producto-mes:** mayormente intermitente/lumpy — la mayoría de los pares tendrá muchos meses en cero. Esto NO es un defecto de los datos; es la naturaleza del negocio mayorista, y define la estrategia de modelado (§3.2).

## 2. Qué dice el estado del arte (evidencia)

1. **Modelos globales de gradient boosting dominan el retail forecasting.** En la competencia M5 (Walmart, 42k series jerárquicas), todas las top-50 soluciones usaron ensambles de árboles; LightGBM con lags y features de calendario/precio fue el enfoque ganador, con ~22% de mejora sobre el benchmark naive estacional. El "cross-learning" (un modelo entrenado sobre todas las series) superó a los modelos por serie individual — exactamente lo que planea DemandSync con su modelo global. Matiz: los modelos globales pierden robustez al agregar hacia arriba de la jerarquía, lo que motiva la reconciliación (§3.3).
2. **Los baselines estadísticos siguen siendo competitivos y obligatorios.** ETS/ARIMA/Theta automáticos son rápidos, fuertes en series mensuales largas, y son el piso contra el que se mide todo. Cualquier modelo sofisticado que no le gane a `SeasonalNaive` y `AutoETS` no se despliega.
3. **Demanda intermitente tiene su propia familia de métodos.** Croston y sus variantes (SBA con corrección de sesgo; TSB para obsolescencia con probabilidad de ocurrencia) son el estándar para SKUs de baja rotación, y la evidencia favorece seleccionar método **por serie** según su perfil, no una política única global.
4. **Métricas: la industria abandonó MAPE para operar.** MAPE es indefinida con demanda cero e incentiva el under-forecast; WAPE/WMAPE (ponderada por volumen) es hoy la métrica primaria dominante en planificación de demanda, complementada con sesgo; M5 usó WRMSSE (escalada). Base del ADR-008.
5. **Reconciliación jerárquica suma precisión gratis.** Forecasts coherentes total→categoría→producto con MinT/bottom-up mejoran 2–25% según nivel y horizonte, con más ganancia en niveles agregados — relevante porque compras decide por producto pero planifica por categoría/laboratorio.
6. **Exógenas climáticas: valor real modesto y de corto plazo.** El caso mejor documentado (productos fuertemente estacionales) logró reducciones de error grandes en porcentaje pero equivalentes a ~2% de las ventas, y el beneficio se concentra en horizontes cortos (≤7 días con pronóstico meteorológico). Para horizonte mensual 6–12m, el clima futuro no se conoce; la estacionalidad de calendario captura la mayor parte de la señal.
7. **Deflactar por índice específico del producto es la práctica correcta.** La literatura de forecasting con inflación recomienda deflactar valores nominales por un índice — y uno específico del producto es preferible al índice general cuando se busca volumen real. El "índice implícito" (`revenue/unidades`) es el *unit value index* de la estadística económica; su debilidad conocida es el efecto mix, que el diseño ya mitiga (promedio ponderado mensual + media geométrica ponderada para índices de nivel + clamp de outliers). La fórmula elegida (deflactar el monto del cliente por el ratio del promedio del producto) además preserva el descuento individual — propiedad que un IPC macro destruiría.
8. **Tooling maduro y gratuito.** El ecosistema Nixtla (`statsforecast`: AutoARIMA/AutoETS/Theta/CES + Croston/SBA/TSB + baselines; `mlforecast`: LightGBM global con feature engineering de lags/ventanas; `hierarchicalforecast`: reconciliación; `utilsforecast`: métricas y evaluación) cubre el pipeline completo del motor en Python/pandas, compatible con el stack FastAPI del proyecto. Esto des-riesga el Release 2: no hay que implementar modelos a mano, solo orquestarlos y evaluarlos bien.

## 3. Adecuaciones necesarias (dónde ajustar lo documentado)

### 3.1 Datos primero: dedup e inflación son bloqueantes del modelado
Nada de lo anterior funciona sobre una serie inflada por doble conteo factura/remito ni sobre montos nominales de 2018 mezclados con 2026. Las correcciones ya entregadas (ADR-002/003, casos CP-INF-*, CP-DEDUP-01) son **prerrequisito del motor**, no mejoras opcionales. Además el EDA debe mapear eventos 2018–2026 (COVID 2020, saltos devaluatorios/inflacionarios) para tratarlos como dummies o exclusiones.

### 3.2 Granularidad: prometer por producto/segmento; cliente×producto como probabilidad
Los CU prometen predicción por producto y por segmento — eso es alcanzable con calidad. Lo que **no** es realista es un pronóstico puntual mensual confiable por cliente×producto (series ~todas ceros): ahí el output honesto es **P(compra en el mes) × tamaño esperado** (enfoque tipo TSB / dos etapas), que es además lo que necesitan venta cruzada y redistribución (ranking de propensión, no cantidades exactas). El brainstorming interno ya lo anticipaba como variable objetivo alternativa; formalizarlo.

### 3.3 Target en unidades, jerarquía y horizontes
- **Unidades como target primario** (ADR-007): elimina la inflación del target; el valor en pesos se deriva con el precio ancla. Los montos deflactados quedan como features (RFM, valor real del cliente).
- **Jerarquía y reconciliación:** producir forecasts coherentes en total → categoría → laboratorio → producto (cliente/segmento como scoping aparte). Ganancia esperada de precisión en los niveles que usa compras.
- **Horizontes 1/6/12:** t+1 tendrá el mejor error; t+12 sirve para planificación con intervalos anchos. Comunicar SIEMPRE con intervalos (quantile regression en LightGBM / intervalos de los modelos estadísticos), no puntos secos — el propio plan de riesgos UTN (riesgo 5) ya prevé darle peso operativo al mes 1.

### 3.4 Exógenas: estacionalidad primero, clima después, macro solo vía deflación
Orden de valor esperado: (1) calendario/estacionalidad mensual — barato y captura lo grueso de la señal climática indirecta; (2) precio real deflactado como feature — la señal comercial más rica del dataset; (3) clima observado como feature explicativa/mock para cumplir el alcance académico, sin depender de él para precisión (a 6–12 meses se necesitaría *pronóstico* climático, que no existe con esa precisión); (4) macro (IPC INDEC) solo como fallback del ancla de deflación, no como regresor del modelo en el MVP.

### 3.5 Limitación estructural a documentar: demanda censurada
Sin histórico de stock no se distinguen los meses de venta cero por "no hubo demanda" de los de "hubo quiebre". Estándar en la industria; se documenta como supuesto (ventas ≈ demanda) y se revisa si el cliente algún día expone quiebres.

## 4. Qué NO es viable prometer (anti-alcance del motor)

- Pronóstico puntual preciso por cliente×producto×mes (ver §3.2).
- Precisión alta "garantizada" a 12 meses en el contexto macro argentino: se promete el intervalo y el proceso de mejora continua, no un MAPE bajo.
- Modelar rotación histórica de stock o quiebres pasados (no hay datos; ADR-004).
- Recalculo de modelos en tiempo real (restricción batch del acta — y correcta).

## 5. Riesgos residuales del motor

| Riesgo | Prob. | Mitigación |
|---|---|---|
| El índice implícito queda ruidoso en productos de baja venta | Alta (cola larga) | Fallback categoría/lab ya diseñado + clamp; EDA mide cuántos productos caen al fallback |
| Leakage temporal en el backtesting vía el ancla de deflación (usar `precio_prom_hoy` calculado con datos posteriores al corte) | Media, sutil | El protocolo de backtesting congela el ancla al corte de cada ventana (ver `plan-diseno.md` §Backtesting) |
| Modelo global degradado por heterogeneidad extrema de series | Media | Baselines por serie como challenger + selección por serie; clustering interno (Ward) como pooling opcional |
| Sobre-ingeniería temprana (deep learning, features exóticas) | Media | Disciplina baselines-first: nada entra si no le gana a AutoETS/SeasonalNaive en WAPE |

## 6. Conclusión operativa

El diseño documentado (hechos mensuales inmutables + deflación por índice implícito + dedup + stock actual) está **alineado con la práctica correcta** y no hay que rehacerlo: hay que ejecutarlo en orden. El camino de menor riesgo para el Release 2 es: EDA → baselines estadísticos/intermitentes (statsforecast) → modelo global LightGBM (mlforecast) → reconciliación → intervalos. Plan detallado en [`plan-diseno.md`](plan-diseno.md).

---

## Fuentes

- [M5 accuracy competition: Results, findings, and conclusions (Makridakis et al., IJF)](https://www.sciencedirect.com/science/article/pii/S0169207021001874)
- [Sales forecasting in retail: what we learned from the M5 competition (Artefact)](https://medium.com/artefact-engineering-and-data-science/sales-forecasting-in-retail-what-we-learned-from-the-m5-competition-445c5911e2f6)
- [The performance of the global bottom-up approach in the M5 (robustness check)](https://www.sciencedirect.com/science/article/abs/pii/S0169207021001400)
- [A Review of Croston's method for intermittent demand forecasting](https://www.researchgate.net/publication/254044245_A_Review_of_Croston's_method_for_intermittent_demand_forecasting)
- [Intermittent demand / spare parts SKU-level optimization (MDPI 2025)](https://www.mdpi.com/2076-3417/15/22/12030)
- [MAPE, WMAPE & Forecast Bias in Demand Planning](https://demandplanning.net/mape-wmape-and-forecast-bias/)
- [Measuring forecast accuracy: The complete guide (RELEX)](https://www.relexsolutions.com/resources/measuring-forecast-accuracy/)
- [Understanding Forecast Accuracy: MAPE, WAPE, WMAPE (Baeldung)](https://www.baeldung.com/cs/mape-vs-wape-vs-wmape)
- [Assessing the Performance of Hierarchical Forecasting Methods on the Retail Sector (Entropy)](https://www.mdpi.com/1099-4300/21/4/436)
- [Improving Forecast Accuracy with Hierarchical Time-Series Models](https://www.singdata.com/trending/forecast-accuracy-hierarchical-models/)
- [Inflation adjustment of data for regression and forecasting (Nau, Duke)](https://people.duke.edu/~rnau/411infla.htm)
- [Deflating nominal values to real values (Dallas Fed)](https://www.dallasfed.org/research/basics/nominal)
- [Using weather data to improve demand forecasting for seasonal products (IJSOM)](https://www.researchgate.net/publication/327198243_Using_weather_data_to_improve_demand_forecasting_for_seasonal_products)
- [Demand forecasting accuracy in the pharmaceutical supply chain: a ML approach (Emerald)](https://www.emerald.com/insight/content/doi/10.1108/ijphm-05-2021-0056/full/html)
- [Cross-Series Demand Forecasting using ML: Evidence in the Pharmaceutical Industry](https://www.researchgate.net/publication/350475349_Cross-Series_Demand_Forecasting_using_Machine_Learning_Evidence_in_the_Pharmaceutical_Industry)
- [Nixtla statsforecast](https://github.com/Nixtla/statsforecast) · [mlforecast](https://github.com/Nixtla/mlforecast) · [Automated Model Selection with StatsForecast](https://www.nixtla.io/blog/statsforecast-automatic-model-selection)
