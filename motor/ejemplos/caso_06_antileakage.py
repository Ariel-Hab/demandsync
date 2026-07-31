"""Caso 6 — La red anti-leakage en acción (M1.3).

Todavía no existe el transformador de deflación (M2.1), así que acá se arma un
cálculo mínimo con la misma forma (un "ancla" de precio promedio por producto) en
dos versiones: una correcta y una contaminada. La red no sabe nada de deflación —
verifica una propiedad general: "para el corte t, el resultado no puede cambiar si
cambia el futuro". Cualquier candidata futura (la de M2.1 incluida) se prueba igual.
"""

import pandas as pd
from _comun import repositorio

from motor.backtesting.cortes import generar_cortes
from motor.backtesting.leakage import LeakageTemporal, verificar_sin_leakage


def ancla_correcta(datos: pd.DataFrame, corte: pd.Timestamp) -> pd.DataFrame:
    """Así se tiene que escribir cualquier ancla: solo mira `anio_mes <= corte`."""
    hasta_corte = datos[datos["anio_mes"] <= corte]
    return hasta_corte.groupby("id_producto", as_index=False)["precio_prom"].mean()


def ancla_contaminada(datos: pd.DataFrame, corte: pd.Timestamp) -> pd.DataFrame:
    """Bug realista: ignora `corte` y promedia TODA la historia, pasada y futura —
    el error exacto que detectó la red al validar contra el fallback de categoría."""
    return datos.groupby("id_producto", as_index=False)["precio_prom"].mean()


def main() -> None:
    repo = repositorio()
    hechos = repo.hecho_venta_mensual_producto()
    cortes = generar_cortes(hechos["anio_mes"], n_cortes=6)

    print("Probando la implementación CORRECTA...")
    verificar_sin_leakage(ancla_correcta, datos=hechos, cortes=cortes)
    print("  pasó sin excepción: no depende de nada posterior al corte.\n")

    print("Probando la implementación CONTAMINADA (promedia todo el histórico)...")
    try:
        verificar_sin_leakage(ancla_contaminada, datos=hechos, cortes=cortes)
        print("  ADVERTENCIA: la red no la detectó (no debería pasar esto — avisá si ves esto)")
    except LeakageTemporal as error:
        print(f"  la red la agarró:\n\n{error}")


if __name__ == "__main__":
    main()
