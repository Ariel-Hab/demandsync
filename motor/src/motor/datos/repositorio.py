"""Interfaces de acceso a datos del motor (ADR-009).

El motor nunca lee ni escribe archivos/tablas fuera de esta capa: todo entra por
`RepositorioHechos` y sale por `RepositorioResultados`. Habilita dos implementaciones
intercambiables (archivos locales hoy, PostgreSQL en M4) sin tocar M1-M3.
"""

from abc import ABC, abstractmethod

import pandas as pd


class RepositorioHechos(ABC):
    """Lectura: hechos mensuales, catálogo y features de cliente (C1/C3 + catálogo)."""

    @abstractmethod
    def hecho_venta_mensual_producto(self) -> pd.DataFrame: ...

    @abstractmethod
    def hecho_venta_mensual_cliente_producto(self) -> pd.DataFrame: ...

    @abstractmethod
    def catalogo_producto(self) -> pd.DataFrame: ...

    @abstractmethod
    def cliente_feature(self) -> pd.DataFrame: ...


class RepositorioResultados(ABC):
    """Escritura: entidades de deflación (C2), calculadas por el motor en M2."""

    @abstractmethod
    def guardar_ancla_precio_producto(self, df: pd.DataFrame) -> None: ...

    @abstractmethod
    def guardar_indice_precio_nivel(self, df: pd.DataFrame) -> None: ...
