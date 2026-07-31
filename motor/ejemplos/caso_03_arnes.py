"""Caso 3 — El arnés de backtesting rolling-origin en acción (M1.1).

El predictor de acá NO es un baseline real (eso es M1.5/M1.6 — el próximo paso):
repite el último valor conocido, solo para ver la plomería del arnés — cortes,
anti-leakage, cruce contra el real — funcionando de punta a punta.
"""

from _comun import correr_backtest_muestra, repositorio


def main() -> None:
    repo = repositorio()
    hechos = repo.hecho_venta_mensual_producto()

    reporte = correr_backtest_muestra(hechos)

    print(f"Reporte: {len(reporte):,} filas (una por id_producto × corte × horizonte)")
    print(f"id_corrida: {reporte['id_corrida'].iloc[0]}")
    horizontes = sorted(reporte["horizonte"].unique())
    print(f"cortes distintos: {reporte['corte'].nunique()}  ·  horizontes: {horizontes}")

    print()
    print("Primeras filas del reporte crudo:")
    print(reporte.head(10).to_string(index=False))

    print()
    print("Cobertura por horizonte (fracción de celdas con predicción — acá debería ser 1.0):")
    print(reporte.groupby("horizonte")["pred_naive"].apply(lambda s: s.notna().mean()).to_string())


if __name__ == "__main__":
    main()
