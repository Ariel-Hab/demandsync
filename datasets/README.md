# datasets/

**Regla de oro: los datos reales del cliente NUNCA entran a este repositorio.** Ni exports JSON, ni dumps, ni CSVs, ni notebooks con outputs que muestren clientes, precios o volúmenes reales. El `.gitignore` bloquea todo el contenido de esta carpeta salvo este README y `sintetico/`.

## Qué va acá

- `sintetico/` — dataset generado artificialmente que replica el **esquema** del contrato de ingesta (`docs/datos-defeve.md`) y las **propiedades estadísticas** del dataset real: intermitencia por producto, estacionalidad mensual, inflación acumulada, distribución de tamaños de cliente, precios con descuento por cliente. Es el dataset con el que desarrolla y testea todo el equipo.

## Dónde viven los datos reales

En la máquina autorizada (acceso al snap del cliente), fuera del repo. El ML Specialist corre ahí los experimentos de validación y publica al repo solo métricas agregadas y conclusiones (ej. tablas WAPE por nivel), nunca registros.

## Generador sintético — `datasets/sintetico/` (T0.1, ✅ 2026-07-27)

`datasets/sintetico/generar_sintetico.py`, parametrizado por las estadísticas del EDA real (**sin copiar registros**). Ver [`datasets/sintetico/README.md`](sintetico/README.md) para cómo correrlo y el diseño; [`motor/roadmap-motor.md`](../motor/roadmap-motor.md) §4 para el contexto de S0.

**Dos salidas, no una:**

1. **Renglones de venta** en el esquema del contrato de ingesta (`docs/contrato-ingesta.md`) — es lo que necesita el backend para probar el ETL y la validación de garantías, y el frontend para mockear.
2. **Hechos mensuales agregados** desde la propia verdad de base del generador — es lo que consume el motor sin depender del ETL (ADR-009).

Como (2) se deriva de (1) por una agregación conocida y sin ambigüedad, **el ETL del Release 1 debe reproducir (2) a partir de (1)**: eso queda como test de integración de la ingesta.

**Parámetros calibrados** (EDA §8): cuadrantes de intermitencia 48/31/10/11%, 53,5% de pares cliente×producto con ≤2 compras en 36m, 25% de productos sin ancla propia, ~9,5% de comprobantes con cantidad negativa (notas de crédito), inflación acumulada en precios nominales, estacionalidad mensual, descuento por cliente.

**Determinismo:** el generador corre por semilla fija. Se commitean el **script, la semilla y el manifiesto**, no los archivos generados — cualquiera reproduce el mismo dataset. La carpeta de salida va al `.gitignore`.

**Criterio de aceptación (cumplido):** el perfil de intermitencia del dataset generado, recalculado con el mismo código del EDA, cae dentro de ±3 puntos de los cuadrantes reales — ver `sintetico/manifiesto.json` (desvíos máximos: 1,25 pts).
