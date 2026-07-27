"""Implementación de RepositorioHechos/RepositorioResultados sobre archivos parquet locales.

Habilita M1-M3 sin depender de PostgreSQL/R1 (ADR-009). El swap a la implementación
PostgreSQL/SQLModel es exclusivo de M4; el resto del motor no cambia.
"""

from pathlib import Path

import pandas as pd

from .repositorio import RepositorioHechos, RepositorioResultados


class RepositorioArchivos(RepositorioHechos, RepositorioResultados):
    def __init__(self, directorio: str | Path):
        self.directorio = Path(directorio)

    def _leer(self, tabla: str) -> pd.DataFrame:
        return pd.read_parquet(self.directorio / f"{tabla}.parquet")

    def _escribir(self, tabla: str, df: pd.DataFrame) -> None:
        self.directorio.mkdir(parents=True, exist_ok=True)
        df.to_parquet(self.directorio / f"{tabla}.parquet", index=False)

    def hecho_venta_mensual_producto(self) -> pd.DataFrame:
        return self._leer("hecho_venta_mensual_producto")

    def hecho_venta_mensual_cliente_producto(self) -> pd.DataFrame:
        return self._leer("hecho_venta_mensual_cliente_producto")

    def catalogo_producto(self) -> pd.DataFrame:
        return self._leer("catalogo_producto")

    def cliente_feature(self) -> pd.DataFrame:
        return self._leer("cliente_feature")

    def guardar_ancla_precio_producto(self, df: pd.DataFrame) -> None:
        self._escribir("ancla_precio_producto", df)

    def guardar_indice_precio_nivel(self, df: pd.DataFrame) -> None:
        self._escribir("indice_precio_nivel", df)
