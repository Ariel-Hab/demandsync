"""CLI: genera el dataset sintético (T0.1). Determinístico por semilla.

Uso (desde la raíz del repo, con el venv de motor/):
    motor/.venv/Scripts/python -m datasets.sintetico.generar_sintetico --semilla 42
    motor/.venv/Scripts/python -m datasets.sintetico.generar_sintetico --semilla 42 \
        --n-productos 200 --n-clientes 150 --sin-contrato   # iteración rápida en desarrollo
"""

import argparse
from datetime import date
from pathlib import Path

import numpy as np

from . import parametros as P
from .exportar_contrato import construir_ventas, escribir_ventas
from .hechos import generar_todo
from .manifiesto import calcular_metricas, escribir_manifiesto

DIRECTORIO_SALIDA_DEFECTO = Path(__file__).parent / "salida"
# El manifiesto se commitea (es la evidencia del gate de S0); la salida generada, no
# — por eso vive fuera de `salida/`, que está en .gitignore.
MANIFIESTO_DEFECTO = Path(__file__).parent / "manifiesto.json"


def main():
    parser = argparse.ArgumentParser(description="Generador de dataset sintético DemandSync (T0.1)")
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--n-productos", type=int, default=P.N_PRODUCTOS)
    parser.add_argument("--n-clientes", type=int, default=P.N_CLIENTES)
    parser.add_argument("--salida", type=Path, default=DIRECTORIO_SALIDA_DEFECTO)
    parser.add_argument("--manifiesto", type=Path, default=MANIFIESTO_DEFECTO)
    parser.add_argument(
        "--sin-contrato",
        action="store_true",
        help="No exporta ventas_<AAAAMM>.json (más rápido para iterar en desarrollo)",
    )
    args = parser.parse_args()

    rng = np.random.default_rng(args.semilla)
    tablas, _series_producto, _productos = generar_todo(rng, args.n_productos, args.n_clientes)

    directorio_hechos = args.salida / "hechos"
    directorio_hechos.mkdir(parents=True, exist_ok=True)
    for nombre_tabla, df in tablas.items():
        df.to_parquet(directorio_hechos / f"{nombre_tabla}.parquet", index=False)

    if not args.sin_contrato:
        ventas_por_mes = construir_ventas(rng, tablas["hecho_venta_mensual_cliente_producto"])
        escribir_ventas(ventas_por_mes, args.salida / "contrato")

    metricas = calcular_metricas(
        tablas,
        hoy=date.today(),  # noqa: DTZ011 — fecha del manifiesto, sin relevancia de huso horario
        semilla=args.semilla,
        n_productos=args.n_productos,
        n_clientes=args.n_clientes,
    )
    archivo_manifiesto = escribir_manifiesto(metricas, args.manifiesto)

    print(f"Escrito en {args.salida}")
    print(f"Manifiesto: {archivo_manifiesto}")
    print(f"Gate cuadrantes de intermitencia OK: {metricas['cuadrantes_intermitencia']['gate_ok']}")
    print(f"Desvios (pts): {metricas['cuadrantes_intermitencia']['desvio_puntos']}")


if __name__ == "__main__":
    main()
