"""Caso 5 — El reporte tabular completo + el markdown que se congela (M1.0(g)/M1.2).

Ojo: esto escribe a `motor/ejemplos/salida/`, NO a `motor/backtests/`. Esa carpeta
es para tablas oficiales de referencia (M1.7 sobre sintético, M1.8 sobre datos
reales) — no para una exploración con un predictor de juguete y 20 productos.
"""

from _comun import RUTA_SALIDA, correr_backtest_muestra, repositorio

from motor.backtesting.reporte import a_markdown, construir_reporte
from motor.clasificacion import clasificar_series, etiquetar


def main() -> None:
    repo = repositorio()
    hechos = repo.hecho_venta_mensual_producto()
    catalogo = repo.catalogo_producto()

    reporte = correr_backtest_muestra(hechos)

    # El merge de abajo descarta reporte.attrs (pandas lo hace en varias operaciones) —
    # hay que guardarse la Corrida y reponerla, o el markdown sale "sin identificar".
    corrida = reporte.attrs["corrida"]
    reporte = reporte.merge(catalogo[["id_producto", "categoria"]], on="id_producto", how="left")
    reporte = etiquetar(reporte, clasificar_series(hechos))
    reporte.attrs["corrida"] = corrida

    tablas = construir_reporte(reporte, columna_pred="pred_naive", train_df=hechos)
    md = a_markdown(
        tablas,
        titulo="Caso 5 — reporte de ejemplo",
        notas="Predictor de juguete (último valor conocido), muestra de productos. "
        "**No es una tabla de referencia** — eso sale de M1.7/M1.8.",
    )

    RUTA_SALIDA.mkdir(exist_ok=True)
    destino = RUTA_SALIDA / "caso_05_reporte_ejemplo.md"
    destino.write_text(md, encoding="utf-8")

    print(md)
    print(f"\n(también escrito en {destino})")


if __name__ == "__main__":
    main()
