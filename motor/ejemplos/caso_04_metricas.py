"""Caso 4 — Medir el mismo reporte a distintos niveles de agregación (M1.2).

La lectura clave de ADR-008: el error por producto, por categoría y total NO son
el mismo número — en este dataset difieren por un factor de 3 a 4x (ver
motor/src/motor/backtesting/README.md). Ninguno es "el" WAPE: sirven para cosas
distintas (reponer un SKU vs. planificar una categoría).
"""

from _comun import correr_backtest_muestra, repositorio

from motor.backtesting.metricas import mase, sesgo, wape


def main() -> None:
    repo = repositorio()
    hechos = repo.hecho_venta_mensual_producto()
    reporte = correr_backtest_muestra(hechos)

    print("WAPE por horizonte, a dos niveles distintos (mismo reporte, mismo predictor):")
    for etiqueta, columnas_nivel in [("producto (por defecto)", None), ("total", [])]:
        tabla = wape(
            reporte, ["horizonte"], columna_pred="pred_naive", columnas_nivel=columnas_nivel
        )
        print(f"\n  nivel={etiqueta}")
        print(tabla.to_string(index=False))

    print()
    print("Sesgo a nivel total (el que pide el gate de M2 '±5%' — con un predictor de juguete):")
    sesgo_total = sesgo(reporte, ["horizonte"], columna_pred="pred_naive", columnas_nivel=[])
    print(sesgo_total.to_string(index=False))

    print()
    print("MASE por producto y corte (compara contra SeasonalNaive; NaN = escala 0, no inf):")
    print(mase(reporte, modelos=["pred_naive"], train_df=hechos).head(10).to_string(index=False))


if __name__ == "__main__":
    main()
