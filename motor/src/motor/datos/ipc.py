"""IPC nacional del INDEC — último peldaño del fallback de deflación (ADR-002).

La cascada de ADR-002 es `producto → categoría → laboratorio → IPC`. Los tres primeros
peldaños salen de las ventas del propio cliente; **este es el único insumo externo del
motor**, y existe para que la cascada tenga fondo: un producto cuya categoría y
laboratorio no tengan muestra en un mes igual necesita un deflactor, y sin esto la
respuesta sería un `NaN` que se propaga.

En la práctica se espera que se use poquísimo (con 12 categorías reales, que se quede sin
muestra el nivel categoría *y* el nivel laboratorio es raro). No por eso es opcional: un
camino de código que no existe no se puede testear, y CP-INF-03 lo exige.

**Es dato público, no dato del cliente.** Por eso puede vivir en el repo sin violar
ADR-006/CLAUDE.md §4: no dice nada de DFV, sale de una API abierta del Estado.

## Procedencia de `ipc_indec.csv`

| | |
|---|---|
| Serie | `148.3_INIVELNAL_DICI_M_26` — "IPC. Nivel General Nacional. Base dic 2016. Mensual." |
| Fuente | API de Series de Tiempo de la Administración Pública Nacional (`apis.datos.gob.ar`) |
| Publica | Subsecretaría de Programación Macroeconómica, sobre el IPC del INDEC |
| Licencia | Creative Commons Attribution 4.0 |
| Bajada | 2026-07-31 — 115 meses, 2016-12 a 2026-06, sin huecos ni nulos |

Reproducir la bajada:

```bash
curl "https://apis.datos.gob.ar/series/api/series/?ids=148.3_INIVELNAL_DICI_M_26&format=csv&limit=5000"
```

**La base (dic-2016 = 100) es irrelevante para el motor**: la deflación solo usa
*cocientes* entre dos meses, y la base se cancela. Se conserva el índice tal cual lo
publica la fuente para que el número sea verificable contra el original, en vez de
renormalizarlo a algo más cómodo y perder la trazabilidad.

## Este archivo se vence

Es una foto de una serie que sigue creciendo. Un corte posterior al último mes del CSV no
tiene deflactor, y responder con el último dato disponible sería **subestimar la inflación
en silencio** — la peor forma de fallar acá. `cargar_ipc()` levanta `IpcDesactualizado`
antes que eso pase. Actualizarlo es volver a correr el `curl` de arriba y mover la fecha
de la tabla de procedencia.
"""

from importlib import resources

import pandas as pd

ARCHIVO = "ipc_indec.csv"

COLUMNAS = {"anio_mes": "datetime64[ns]", "indice": "float64"}
"""Mismos nombres y tipos que `indice_precio_nivel` en el diccionario: quien lo consuma
lo apila con los otros niveles sin renombrar nada."""


class IpcDesactualizado(RuntimeError):
    """Se pidió un mes posterior al último que tiene el CSV. Ver §"Este archivo se vence"."""


def cargar_ipc(hasta: pd.Timestamp | None = None) -> pd.DataFrame:
    """Devuelve la serie del IPC nacional, opcionalmente recortada en `hasta`.

    Args:
        hasta: último mes a devolver, inclusive. **Pasalo siempre que estés dentro de un
            backtest**: es el corte, y sin él la deflación de un corte de 2022 usaría
            índices de 2026 (leakage temporal, `plan-diseno.md` §Protocolo). Es opcional
            y no obligatorio porque fuera del backtest —una corrida de producción, donde
            "hoy" es hoy— no hay nada que recortar; la red que lo verifica de verdad es
            `motor.backtesting.leakage.verificar_sin_leakage`.

    Returns:
        DataFrame con `anio_mes` y `indice`, ordenado y sin huecos mensuales.

    Raises:
        IpcDesactualizado: si `hasta` supera el último mes del CSV.
    """
    with resources.files(__package__).joinpath(ARCHIVO).open(encoding="utf-8") as f:
        ipc = pd.read_csv(f, parse_dates=["anio_mes"]).astype(COLUMNAS)

    if hasta is None:
        return ipc

    hasta = pd.Timestamp(hasta).normalize().replace(day=1)
    ultimo = ipc["anio_mes"].max()
    if hasta > ultimo:
        raise IpcDesactualizado(
            f"Se pidió el IPC hasta {hasta.date()} pero {ARCHIVO} termina en "
            f"{ultimo.date()}. Devolver el último dato disponible subestimaría la "
            f"inflación sin avisar, así que se corta acá. Actualizá el CSV: ver la "
            f"procedencia en el docstring de este módulo."
        )
    return ipc[ipc["anio_mes"] <= hasta].reset_index(drop=True)
