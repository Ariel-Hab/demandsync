"""Helpers compartidos por los casos de ejemplo.

Esta carpeta no es parte del paquete `motor` (no hay `motor.ejemplos` importable
desde afuera): son scripts sueltos, documentación ejecutable de lo que ya está
construido. Se corren con el venv del motor:

    motor/.venv/Scripts/python motor/ejemplos/caso_01_datos.py
"""

from pathlib import Path

import pandas as pd

from motor.backtesting.arnes import ejecutar_backtest
from motor.datos.archivos import RepositorioArchivos

RAIZ_REPO = Path(__file__).resolve().parents[2]
RUTA_HECHOS = RAIZ_REPO / "datasets" / "sintetico" / "salida" / "hechos"
RUTA_SALIDA = Path(__file__).resolve().parent / "salida"

N_PRODUCTOS_MUESTRA = 20
"""Cuántos productos usan los casos 3/4/5 para que corran en segundos. Es a propósito
un parámetro fácil de tocar: subilo para ver el arnés a más escala — M1.8 corre lo
mismo sobre los ~2.300 productos reales, no sobre esta muestra chica."""


def repositorio() -> RepositorioArchivos:
    if not RUTA_HECHOS.exists():
        raise FileNotFoundError(
            f"No hay dataset sintético en {RUTA_HECHOS}. Generalo desde la raíz del "
            "repo (ver motor/README.md §Arranque desde cero):\n\n"
            "  motor/.venv/Scripts/python -m datasets.sintetico.generar_sintetico "
            "--semilla 42 --sin-contrato"
        )
    return RepositorioArchivos(RUTA_HECHOS)


def predictor_ultimo_valor(
    historia: pd.DataFrame, corte: pd.Timestamp, horizonte_max: int
) -> pd.DataFrame:
    """El mismo truco que usan los tests del arnés (`test_backtesting_arnes.py`):
    repite el último valor conocido de cada producto. **No es un baseline real** —
    esos son M1.5/M1.6 — solo sirve para ejercitar la plomería del arnés de punta a
    punta sin depender todavía de `statsforecast`."""
    ultimo = (
        historia.sort_values("anio_mes")
        .groupby("id_producto", as_index=False)
        .tail(1)[["id_producto", "unidades"]]
        .rename(columns={"unidades": "pred_naive"})
    )
    fechas = pd.date_range(corte + pd.DateOffset(months=1), periods=horizonte_max, freq="MS")
    return ultimo.merge(pd.DataFrame({"anio_mes": fechas}), how="cross")


def correr_backtest_muestra(
    hechos: pd.DataFrame, n_productos: int = N_PRODUCTOS_MUESTRA, n_cortes: int = 18
) -> pd.DataFrame:
    """Corre `ejecutar_backtest` con el predictor de juguete sobre una muestra chica
    de productos, para que los casos 3/4/5 corran en segundos."""
    muestra = hechos["id_producto"].drop_duplicates().head(n_productos)
    return ejecutar_backtest(
        hechos[hechos["id_producto"].isin(muestra)],
        predictor_ultimo_valor,
        n_cortes=n_cortes,
        horizonte_max=12,
    )
