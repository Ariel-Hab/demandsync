"""Caso 7 — Selección por serie: cada producto con su mejor baseline por MASE (M1.7).

Corre los 7 candidatos (M1.5+M1.6) sobre una muestra chica y muestra qué modelo ganó
en cada producto — la pieza que faltaba: M1.5/M1.6 corren los 7, pero ninguno decide.

Ojo con la escala: a diferencia de los casos 1-6 (predictor de juguete, ~0s), acá
corren `AutoARIMA`/`AutoTheta` de verdad. Por eso la muestra es más chica que
`N_PRODUCTOS_MUESTRA` y esto **no** es la tabla oficial de M1.7 (esa la genera
`motor/scripts/congelar_baselines_sintetico.py` sobre el catálogo completo).
"""

from _comun import repositorio

from motor.backtesting.arnes import ejecutar_backtest
from motor.backtesting.reporte import a_markdown, construir_reporte
from motor.clasificacion import clasificar_series, etiquetar
from motor.modelado.seleccion import (
    armar_reporte_seleccionado,
    elegir_mejor_por_serie,
    predecir_todos_los_candidatos,
)

N_PRODUCTOS_CASO_7 = 8
"""Más chico que `N_PRODUCTOS_MUESTRA` (20): con los 7 candidatos reales (incluido
`AutoARIMA`) el costo por producto es segundos, no milisegundos — ver
`modelado/README.md` §Riesgo de performance."""

N_CORTES_CASO_7 = 6


def main() -> None:
    repo = repositorio()
    hechos = repo.hecho_venta_mensual_producto()
    catalogo = repo.catalogo_producto()

    muestra = hechos["id_producto"].drop_duplicates().head(N_PRODUCTOS_CASO_7)
    datos = hechos[hechos["id_producto"].isin(muestra)]

    reporte = ejecutar_backtest(
        datos, predecir_todos_los_candidatos, n_cortes=N_CORTES_CASO_7, horizonte_max=12
    )
    corrida = reporte.attrs["corrida"]

    ganadores = elegir_mejor_por_serie(reporte, train_df=hechos)
    print("Modelo ganador por producto (MASE medio a través de los cortes):")
    print(ganadores.to_string(index=False))

    seleccionado = armar_reporte_seleccionado(reporte, ganadores)
    seleccionado = seleccionado.merge(
        catalogo[["id_producto", "categoria"]], on="id_producto", how="left"
    )
    seleccionado = etiquetar(seleccionado, clasificar_series(hechos))
    seleccionado.attrs["corrida"] = corrida

    tablas = construir_reporte(seleccionado, columna_pred="pred", train_df=hechos)
    md = a_markdown(
        tablas,
        titulo="Caso 7 — selección por serie (ejemplo)",
        notas=f"Muestra de {N_PRODUCTOS_CASO_7} productos, {N_CORTES_CASO_7} cortes. "
        "**No es la tabla oficial de M1.7** — esa sale de "
        "`motor/scripts/congelar_baselines_sintetico.py` sobre el catálogo completo.",
    )
    print()
    print(md)


if __name__ == "__main__":
    main()
