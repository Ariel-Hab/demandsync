"""Arma `ventas_<AAAAMM>.json` — esquema §1 de docs/contrato-ingesta.md v0.9 — a partir de
`hecho_venta_mensual_cliente_producto` (ya está a la granularidad de un renglón por venta).

Simplificación deliberada: una venta por (cliente, mes) con un renglón por producto
comprado ese mes, en vez de modelar facturas individuales — alcanza para probar el ETL
y la validación de garantías del contrato sin la complejidad de facturación real.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import parametros as P


def construir_ventas(
    rng: np.random.Generator, hecho_cliente_producto: pd.DataFrame
) -> dict[pd.Timestamp, list[dict]]:
    """Devuelve {anio_mes: [venta, ...]} con ~PORCENTAJE_NOTAS_CREDITO de ventas incluyendo
    un renglón de nota de crédito (cantidad negativa, EDA §1)."""
    df = hecho_cliente_producto.copy()
    df["precio"] = df["revenue"] / df["unidades"]

    ventas_por_mes: dict[pd.Timestamp, list[dict]] = {}
    for anio_mes, grupo_mes in df.groupby("anio_mes"):
        ventas_mes = []
        for id_cliente, grupo_cliente in grupo_mes.groupby("id_cliente"):
            renglones = [
                {
                    "producto_id": str(int(fila.id_producto)),
                    "cantidad": round(float(fila.unidades), 2),
                    "precio": round(float(fila.precio), 4),
                    "fecha_vencimiento": None,
                }
                for fila in grupo_cliente.itertuples(index=False)
            ]
            if rng.random() < P.PORCENTAJE_NOTAS_CREDITO:
                renglones.append(_renglon_nota_credito(rng, renglones))

            dia = int(rng.integers(1, 29))
            fecha = anio_mes.replace(day=dia)
            venta = {
                "venta_ref": f"SINT-{id_cliente}-{anio_mes:%Y%m}",
                "fecha": fecha.strftime("%Y-%m-%d"),
                "cliente_id": str(int(id_cliente)),
                "total": round(sum(r["cantidad"] * r["precio"] for r in renglones), 2),
                "zona": None,
                "vendedor_id": None,
                "renglones": renglones,
            }
            ventas_mes.append(venta)
        ventas_por_mes[anio_mes] = ventas_mes
    return ventas_por_mes


def _renglon_nota_credito(rng: np.random.Generator, renglones: list[dict]) -> dict:
    """Nota de crédito parcial sobre uno de los renglones ya presentes en la venta."""
    base = renglones[int(rng.integers(0, len(renglones)))]
    fraccion = rng.uniform(0.1, 0.4)
    cantidad_nc = -round(max(base["cantidad"] * fraccion, 1.0), 2)
    return {
        "producto_id": base["producto_id"],
        "cantidad": cantidad_nc,
        "precio": base["precio"],
        "fecha_vencimiento": None,
    }


def escribir_ventas(ventas_por_mes: dict[pd.Timestamp, list[dict]], directorio: Path) -> None:
    directorio.mkdir(parents=True, exist_ok=True)
    for anio_mes, ventas in ventas_por_mes.items():
        archivo = directorio / f"ventas_{anio_mes:%Y%m}.json"
        with archivo.open("w", encoding="utf-8") as f:
            json.dump(ventas, f, ensure_ascii=False, indent=None)
