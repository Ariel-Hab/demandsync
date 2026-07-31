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

### Ciclo de vida del producto (T0.4)

Cada producto tiene un `mes_alta` y un `mes_baja`, y solo vende entre los dos. **Los ceros de
antes del alta y los de después de la baja no son la misma cosa**: los primeros son meses en
que el producto no existía y ADR-010 los excluye de la ventana de clasificación; los segundos
son demanda cero de verdad.

Eso obliga a que el bucle de rechazo clasifique sobre la vida efectiva del producto y no sobre
`serie[-36:]` — ver `_ventana_de_calibracion` en `demanda.py`, que documenta por qué compartir
el clasificador con el motor no alcanza si se lo llama con la ventana equivocada.

Las bajas se correlacionan con el arquetipo (`lumpy` muere 4,9× más que `suave`, medido sobre
datos reales) y **no se suman a `sin_ancla_propia`**: un producto muerto ya no tiene venta
reciente, así que contarlo dos veces rompería la calibración de EDA §4.

## Gate de S0 y de T0.4

`manifiesto.json` → cinco banderas `gate_ok`:

| bloque | qué exige |
|---|---|
| `cuadrantes_intermitencia` | distribución de cuadrantes dentro de ±3 puntos de la real (**gate de S0**) |
| `cliente_feature_versionada` | más de una `fecha_calculo` — sin esto M2.2 no puede consumirla sin leakage |
| `meses_degenerados` | existen meses con neto negativo y con neto cero |
| `altas_y_bajas` | % de altas en la ventana y tasa de baja dentro de ±3 puntos de los objetivos |
| `categorias` | las 12 reales, con desvío de distribución dentro de ±3 puntos |

El resto de las métricas (intermitencia cliente×producto, % sin ancla propia, % de notas de
crédito) se reportan para transparencia pero no gatean.

**Los tests viven en `motor/tests/test_generador_sintetico.py`** y verifican las cuatro
condiciones de T0.4 sobre la salida, no sobre los parámetros. Corren con un dataset chico, así
que sus tolerancias son más anchas que las del gate: el ±3 a tamaño real lo certifica el
manifiesto.
