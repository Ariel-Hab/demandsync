# `datasets/sintetico/` — Generador de dataset sintético (T0.1)

Determinístico por semilla, calibrado contra `motor/eda/eda-2026-07-15.md` §8. Ver
parámetros completos en `parametros.py` y el resultado de la última corrida en
`manifiesto.json` (commiteado — la carpeta `salida/` no, se regenera).

## Correr

Desde la raíz del repo, con el venv de `motor/` (ya tiene `pandas`/`pyarrow`/`numpy`):

```bash
motor/.venv/Scripts/python -m datasets.sintetico.generar_sintetico --semilla 42
```

Iteración rápida en desarrollo (menos productos/clientes, sin exportar el contrato):

```bash
motor/.venv/Scripts/python -m datasets.sintetico.generar_sintetico \
    --semilla 42 --n-productos 200 --n-clientes 150 --sin-contrato
```

## Salida (`salida/`, no se commitea)

- `salida/hechos/*.parquet` — las 4 tablas de lectura del diccionario (`motor.datos.diccionario`):
  `hecho_venta_mensual_producto`, `hecho_venta_mensual_cliente_producto`, `catalogo_producto`,
  `cliente_feature`. Se leen con `motor.datos.archivos.RepositorioArchivos("salida/hechos")`.
- `salida/contrato/ventas_<AAAAMM>.json` — esquema §1 de `docs/contrato-ingesta.md` v0.9 (una
  venta por cliente×mes, con notas de crédito inyectadas en ~9,5% de los comprobantes).

## Diseño (por qué está calibrado así)

Es **top-down por producto, con rechazo/resorteo**: a cada producto se le asigna un arquetipo
Syntetos-Boylan (suave/intermitente/errática/lumpy) según las proporciones del EDA; se simula
su serie de 96 meses y se reclasifica con el mismo criterio ADI/CV² del EDA —usando
**`motor.clasificacion`, el clasificador del motor** (`clasificacion.py` acá es solo el
adaptador); que el generador calibre con el mismo código que después mide el motor es lo
que hace que este gate signifique algo—
— si no cae en su cuadrante, se resortean los parámetros (hasta `MAX_INTENTOS_CALIBRACION_PRODUCTO`
veces). Recién con la serie de producto ya calibrada se reparte entre un pool de clientes
elegibles (tamaño de pool correlacionado con el arquetipo) para producir la intermitencia
cliente×producto — ese reparto es *best-effort* contra el objetivo del EDA §5, no forma parte
del gate.

## Gate de S0

`manifiesto.json` → `cuadrantes_intermitencia.gate_ok`: la distribución de cuadrantes lograda
cae dentro de `TOLERANCIA_CALIBRACION_PUNTOS` (±3 puntos) de los reales. Es lo único que bloquea
— el resto de las métricas del manifiesto (intermitencia cliente×producto, % sin ancla propia,
% de notas de crédito) se reportan para transparencia pero no gatean.
