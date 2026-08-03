# motor/ — Motor de Predicción de Demanda

**Responsable:** ML Specialist. **Estado:** M1 cerrado (piso real congelado en `backtests/`), T0.4 y M2.1 cerradas; en curso M2.2 (features). Ver [`roadmap-motor.md`](roadmap-motor.md) §9 para el estado vigente.

> **Regla de trabajo en este módulo (CLAUDE.md §6):** todo desarrollo se controla contra [`roadmap-motor.md`](roadmap-motor.md). Antes de codear, ubicá la tarea en una unidad de trabajo (`T0.x`/`M1.x`/…); si no existe, se agrega al roadmap primero. No se empieza un hito con el gate del anterior sin cumplir. Al terminar, se actualiza el estado de la unidad en el roadmap en la misma unidad de trabajo.

## Alcance

Todo lo que ocurre entre los hechos mensuales materializados y la tabla `PREDICCION_DEMANDA`:

1. **Deflación read-time** (ADR-002): ancla por producto + índices de nivel + fallback, aplicada al armar features.
2. **Feature engineering**: lags, ventanas móviles, estacionalidad, features de cliente, precio real.
3. **Modelos**: baselines estadísticos → intermitentes → modelo global ML; clustering RFM propio.
4. **Backtesting**: protocolo de evaluación rolling-origin con métricas por nivel y horizonte.
5. **Empaquetado batch**: corridas versionadas (`EJECUCION_MODELO`), escritura de predicciones e intervalos.

## Interfaces

- **Entrada:** `HECHO_VENTA_MENSUAL_PRODUCTO`, `HECHO_VENTA_MENSUAL_CLIENTE_PRODUCTO`, `CLIENTE_FEATURE`, catálogo, `VARIABLE_EXTERNA`, `PARAMETRO_SISTEMA`.
- **Único insumo externo:** la serie del IPC nacional del INDEC, empaquetada en `motor.datos.ipc` (dato público, CC-BY; es el último peldaño del fallback de ADR-002). Se vence: un corte posterior al último mes del CSV levanta `IpcDesactualizado` en vez de subestimar la inflación en silencio.
- **Salida:** `ANCLA_PRECIO_PRODUCTO`, `INDICE_PRECIO_NIVEL`, `SEGMENTO`/`CLIENTE_SEGMENTO`, `PREDICCION_DEMANDA` (con intervalos), `RECOMENDACION`, todo colgado de una `EJECUCION_MODELO`.
- El acceso a esas tablas es **a través de una interfaz de repositorio** con dos implementaciones —archivos locales y PostgreSQL— para que el motor se desarrolle y se evalúe sin depender del Release 1 (ADR-009, *Propuesta*: a ratificar con el Backend Dev).
- El motor **no** expone HTTP ni lee JSON crudo del ERP: es una librería Python invocada por el job batch nocturno.

## Arranque desde cero

Un clon nuevo **no tiene el dataset sintético**: `datasets/sintetico/salida/` está en
`.gitignore` (se commitean el script, la semilla y el manifiesto, no los archivos). Sin
regenerarlo se pueden correr los tests, pero no las validaciones a escala.

```bash
# 1. entorno — el venv vive en motor/.venv y todos los comandos del repo lo asumen
cd motor
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"     # Linux/macOS: .venv/bin/python

# 2. tests
.venv/Scripts/python -m pytest                       # toda la suite
.venv/Scripts/python -m pytest -m innegociable       # solo la red anti-leakage (M1.3)

# 3. dataset sintético — desde la RAÍZ del repo, ~1 min sin el export del contrato
cd ..
motor/.venv/Scripts/python -m datasets.sintetico.generar_sintetico --semilla 42 --sin-contrato
```

Con `--semilla 42` el dataset es idéntico al que produjo
`datasets/sintetico/manifiesto.json`, así que se puede verificar el gate de calibración
comparando contra ese archivo. Quitá `--sin-contrato` solo si necesitás los
`ventas_<AAAAMM>.json` del contrato de ingesta (tarda bastante más y pesa ~240 MB).

Layout `src/`: el paquete importable es `motor` (`motor/src/motor/`). Ya existen `datos/`
(T0.3, más el IPC del INDEC empaquetado en M2.1), `backtesting/` (M1.0–M1.3, ver su propio
[README](src/motor/backtesting/README.md)), `clasificacion.py` (M1.4: cuadrantes
Syntetos-Boylan por serie), `modelado/` (M1.5–M1.7: baselines `statsforecast`, rama
intermitente y selección por serie, ver su propio
[README](src/motor/modelado/README.md)) y `deflacion/` (M2.1: ADR-002 de punta a punta, ver
su propio [README](src/motor/deflacion/README.md)). El resto de los subpaquetes se agregan
en sus propias unidades de trabajo del roadmap.

Fuera del paquete hay dos carpetas de scripts, ninguna importable por el job batch:

- [`ejemplos/`](ejemplos/) — documentación ejecutable de cada pieza, para explorar y tocar.
- [`scripts/`](scripts/) — operación del track. Hoy:
  `congelar_baselines_sintetico.py`, que genera la tabla de referencia de M1.7/M1.8 en
  `backtests/`.

```bash
pytest                     # toda la suite
pytest -m innegociable     # solo la red anti-leakage (M1.3)
```

**`datasets/` importa del motor, nunca al revés.** El motor es código de producción y no
puede depender de una herramienta de desarrollo; el generador sintético usa
`motor.clasificacion` para que su gate de calibración se mida con el mismo criterio que
después usa el motor.

## Documentos

| Doc | Contenido |
|---|---|
| [`viabilidad.md`](viabilidad.md) | Informe de viabilidad: qué dice el estado del arte, qué permiten los datos del cliente 1, veredicto y adecuaciones |
| [`plan-diseno.md`](plan-diseno.md) | Plan de diseño e implementación del motor por fases (M0–M4), protocolo de backtesting, decisiones resueltas |
| [`roadmap-motor.md`](roadmap-motor.md) | **Track del ML Specialist:** los hitos M0–M4 desglosados en unidades de trabajo con entregable y gate de salida, cronograma en semanas relativas, dependencias externas y riesgos |
| [`eda/`](eda/) | Reportes de EDA sobre datos reales — solo métricas agregadas (ADR-006) |
| `backtests/` | Tablas de error congeladas por corrida (piso de baselines, champion/challenger) — solo métricas agregadas. Se crea en M1 |
