# `motor/ejemplos/` — casos para explorar lo ya construido

No es parte del paquete `motor` ni una unidad del roadmap: es documentación
ejecutable de lo que ya está cerrado (S0, M1.0–M1.7), pensada para correr y tocar.
Para el diseño formal de cada pieza ver [`../roadmap-motor.md`](../roadmap-motor.md),
[`../src/motor/backtesting/README.md`](../src/motor/backtesting/README.md) y
[`../src/motor/modelado/README.md`](../src/motor/modelado/README.md).

## Prerequisito

Entorno instalado y dataset sintético generado — ver
[`../README.md`](../README.md) §Arranque desde cero. Si `datasets/sintetico/salida/hechos/`
no existe, cada caso corta con un error explicando cómo regenerarlo.

## Cómo correr

```bash
# un caso suelto
motor/.venv/Scripts/python motor/ejemplos/caso_01_datos.py

# los 7 en orden
motor/.venv/Scripts/python motor/ejemplos/recorrido_completo.py
```

## Los casos

| # | Script | Qué muestra | Pieza |
|---|---|---|---|
| 1 | `caso_01_datos.py` | Forma de `hecho_venta_mensual_producto`: dispersa, dtypes, una serie de ejemplo | T0.3 (capa de datos) |
| 2 | `caso_02_clasificacion.py` | Distribución de cuadrantes vs el EDA real, series de ejemplo suave/lumpy | M1.4 (clasificador) |
| 3 | `caso_03_arnes.py` | El arnés rolling-origin corriendo con un predictor de juguete | M1.1 (arnés) |
| 4 | `caso_04_metricas.py` | WAPE/sesgo/MASE al mismo reporte, en distintos niveles — el factor 3-4x | M1.2 (métricas) |
| 5 | `caso_05_reporte.py` | El juego de tablas completo + el markdown que se congela en `motor/backtests/` | M1.0(g)/M1.2 (reporte) |
| 6 | `caso_06_antileakage.py` | La red atrapando una implementación contaminada en vivo | M1.3 (anti-leakage) |
| 7 | `caso_07_seleccion.py` | Los 7 candidatos reales corriendo y el ganador por producto vía MASE, en una muestra chica | M1.7 (selección por serie) |

Cada script tiene un `main()` y corre solo — pará donde te sirva, cambiá un
parámetro (`N_PRODUCTOS_MUESTRA` en `_comun.py`, los umbrales de `clasificacion.py`,
lo que sea) y volvé a correrlo. Es exploración, no un test: no hay asserts, solo
salida impresa para leer.

## Qué NO es esto

- No es una tabla de referencia (eso es M1.7/M1.8) ni va a `motor/backtests/` —
  incluido el caso 7, que corre sobre una muestra chica, no el catálogo completo.
- Los casos 1-6 no corren ningún baseline real — el predictor es "repetí el
  último valor conocido", el mismo truco que usan los tests del arnés. El caso 7
  es el primero con los baselines de verdad (M1.5/M1.6) y su selección (M1.7).
- La salida que escriben a disco (`caso_05_reporte.py`) va a `salida/`, gitignorada:
  son artefactos de exploración, no resultados a versionar.
