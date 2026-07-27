"""Clasificador Syntetos-Boylan (ADI/CV²) — mismo criterio que motor/eda/eda-2026-07-15.md §3.

Lo usa el generador para verificar su propia calibración (gate de S0). Reutilizable
por M1.4 (`motor/roadmap-motor.md`) cuando el motor tenga que enrutar el método de
forecast por cuadrante — no hace falta reescribirlo, importarlo de acá.
"""

import numpy as np
import pandas as pd

from . import parametros as P


def clasificar_serie(unidades_mensuales: np.ndarray) -> tuple[str, float, float]:
    """Clasifica una serie mensual (con ceros en meses sin demanda) en un cuadrante."""
    no_cero = unidades_mensuales[unidades_mensuales > 0]
    n_meses = len(unidades_mensuales)
    n_demandas = len(no_cero)
    if n_demandas == 0:
        return "sin_actividad", np.inf, np.nan

    adi = n_meses / n_demandas
    media = no_cero.mean()
    cv2 = (no_cero.std(ddof=0) / media) ** 2 if media > 0 else np.nan

    if adi < P.ADI_UMBRAL and cv2 < P.CV2_UMBRAL:
        cuadrante = "suave"
    elif adi >= P.ADI_UMBRAL and cv2 < P.CV2_UMBRAL:
        cuadrante = "intermitente"
    elif adi < P.ADI_UMBRAL and cv2 >= P.CV2_UMBRAL:
        cuadrante = "erratica"
    else:
        cuadrante = "lumpy"
    return cuadrante, adi, cv2


def clasificar_productos(
    hecho_producto: pd.DataFrame, ventana_meses: int = P.VENTANA_INTERMITENCIA_MESES
) -> pd.DataFrame:
    """hecho_producto: columnas id_producto, anio_mes, unidades. Clasifica sobre los últimos `ventana_meses`."""
    ultimo_mes = hecho_producto["anio_mes"].max()
    inicio_ventana = ultimo_mes - pd.DateOffset(months=ventana_meses - 1)
    meses_ventana = pd.date_range(inicio_ventana, ultimo_mes, freq="MS")
    ventana = hecho_producto[hecho_producto["anio_mes"] >= inicio_ventana]

    filas = []
    for id_producto, grupo in ventana.groupby("id_producto"):
        serie = (
            grupo.set_index("anio_mes")["unidades"]
            .reindex(meses_ventana, fill_value=0.0)
            .to_numpy()
        )
        cuadrante, adi, cv2 = clasificar_serie(serie)
        filas.append({"id_producto": id_producto, "cuadrante": cuadrante, "adi": adi, "cv2": cv2})
    return pd.DataFrame(filas)


def distribucion_cuadrantes(clasificacion: pd.DataFrame) -> dict:
    """% de productos clasificados (excluye sin_actividad) en cada cuadrante."""
    clasificados = clasificacion[clasificacion["cuadrante"] != "sin_actividad"]
    if len(clasificados) == 0:
        return {}
    return (clasificados["cuadrante"].value_counts(normalize=True) * 100).to_dict()


def desvios_vs_objetivo(distribucion: dict) -> dict:
    """Diferencia en puntos porcentuales contra PROPORCION_ARQUETIPOS (para el gate ±3 pts)."""
    objetivo = {k: v * 100 for k, v in P.PROPORCION_ARQUETIPOS.items()}
    return {
        cuadrante: round(distribucion.get(cuadrante, 0.0) - objetivo_pct, 2)
        for cuadrante, objetivo_pct in objetivo.items()
    }
