"""Caso 2 — Clasificador de cuadrantes de intermitencia (M1.4).

Repite el gate de calibración de S0/M1.4: la distribución de cuadrantes del
sintético tiene que caer cerca de los % reales medidos en el EDA. Esto es también
lo que va a decidir, en M1.5/M1.6, qué método de forecast le toca a cada serie.
"""

from _comun import repositorio

from motor.clasificacion import clasificar_series, distribucion_cuadrantes

EDA_REFERENCIA = {"suave": 48, "intermitente": 31, "erratica": 10, "lumpy": 11}
"""Motor/eda/eda-2026-07-15.md §3 — cuadrantes medidos sobre datos reales."""


def main() -> None:
    repo = repositorio()
    hechos = repo.hecho_venta_mensual_producto()

    clasificacion = clasificar_series(hechos)
    distribucion = distribucion_cuadrantes(clasificacion)

    print("Distribución de cuadrantes — sintético (esta corrida) vs EDA (datos reales):")
    for cuadrante, pct_eda in EDA_REFERENCIA.items():
        pct_sintetico = distribucion.get(cuadrante, 0.0)
        print(f"  {cuadrante:14s} sintético={pct_sintetico:5.1f}%   eda_real={pct_eda}%")

    print()
    print("Un ejemplo de cada cuadrante extremo, para ver la serie detrás del número:")
    for cuadrante in ("suave", "lumpy"):
        candidatos = clasificacion[clasificacion["cuadrante"] == cuadrante]
        if candidatos.empty:
            print(f"\n  (ningún producto cayó en {cuadrante} en esta corrida)")
            continue
        ejemplo = candidatos.iloc[0]
        serie = hechos[hechos["id_producto"] == ejemplo["id_producto"]].sort_values("anio_mes")
        print(
            f"\n  producto {ejemplo['id_producto']} -> {cuadrante} "
            f"(ADI={ejemplo['adi']:.2f}, CV²={ejemplo['cv2']:.2f})"
        )
        ultimas = serie["unidades"].tail(12).tolist()
        print(f"  unidades vendidas, últimas 12 filas con venta: {ultimas}")


if __name__ == "__main__":
    main()
