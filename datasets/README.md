# datasets/

**Regla de oro: los datos reales del cliente NUNCA entran a este repositorio.** Ni exports JSON, ni dumps, ni CSVs, ni notebooks con outputs que muestren clientes, precios o volúmenes reales. El `.gitignore` bloquea todo el contenido de esta carpeta salvo este README y `sintetico/`.

## Qué va acá

- `sintetico/` — dataset generado artificialmente que replica el **esquema** del contrato de ingesta (`docs/datos-defeve.md`) y las **propiedades estadísticas** del dataset real: intermitencia por producto, estacionalidad mensual, inflación acumulada, distribución de tamaños de cliente, precios con descuento por cliente. Es el dataset con el que desarrolla y testea todo el equipo.

## Dónde viven los datos reales

En la máquina autorizada (acceso al snap del cliente), fuera del repo. El ML Specialist corre ahí los experimentos de validación y publica al repo solo métricas agregadas y conclusiones (ej. tablas WAPE por nivel), nunca registros.

## Pendiente (R0)

Generador del dataset sintético parametrizado por las estadísticas del EDA real (sin copiar registros): script `generar_sintetico.py` a crear cuando cierre el EDA.
