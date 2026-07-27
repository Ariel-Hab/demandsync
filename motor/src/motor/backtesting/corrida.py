"""Identificación de corridas de backtest (M1.0 (g)).

Sin esto, `ejecutar_backtest` devolvía un DataFrame anónimo: no había forma de saber
qué configuración ni qué datos produjeron una tabla de error. Es requisito del gate
de M1.1 ("corridas identificadas") y precondición para congelar el piso de baselines
en M1.7/M1.8 — una tabla de referencia sin trazabilidad no es referencia de nada.

El `id` es un **hash de la configuración más una huella de los datos**, no un número
de secuencia ni un timestamp: la misma configuración sobre los mismos datos da el
mismo id (reproducible, comparable entre máquinas), y cualquier cambio en la
configuración *o en los datos* lo cambia. La fecha de ejecución se registra aparte,
justamente para que no afecte al id.
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

import pandas as pd


@dataclass(frozen=True)
class Corrida:
    """Metadatos de una corrida de backtest. Se adjunta al reporte y encabeza las
    tablas de `motor/backtests/`."""

    id: str
    fecha_ejecucion: str
    n_cortes: int
    horizonte_max: int
    columnas_id: tuple[str, ...]
    columna_objetivo: str
    densificado: bool
    primer_corte: str
    ultimo_corte: str
    huella_datos: dict = field(default_factory=dict)

    def como_fila(self) -> pd.DataFrame:
        """Una fila con todos los metadatos, para pegar arriba de la tabla de error."""
        plano = {k: v for k, v in asdict(self).items() if k != "huella_datos"}
        plano.update({f"datos_{k}": v for k, v in self.huella_datos.items()})
        return pd.DataFrame([plano])


def _huella(datos: pd.DataFrame, columnas_id: list[str], columna_fecha: str, objetivo: str) -> dict:
    """Huella de los datos de entrada: si cambian, el id de la corrida cambia.

    No es un hash del contenido completo (sería caro y no aporta): con el conteo de
    filas y series, el rango de fechas y la suma del objetivo alcanza para detectar
    que se corrió contra otro dataset o contra una versión distinta del mismo.
    """
    return {
        "filas": int(len(datos)),
        "series": int(datos.groupby(columnas_id, observed=True).ngroups),
        "primer_mes": str(datos[columna_fecha].min().date()),
        "ultimo_mes": str(datos[columna_fecha].max().date()),
        "suma_objetivo": round(float(datos[objetivo].sum()), 2),
    }


def identificar_corrida(
    datos: pd.DataFrame,
    cortes: list[pd.Timestamp],
    n_cortes: int,
    horizonte_max: int,
    columnas_id: list[str],
    columna_fecha: str,
    columna_objetivo: str,
    densificado: bool,
    fecha_ejecucion: str | None = None,
) -> Corrida:
    """Construye la `Corrida`. `fecha_ejecucion` se puede pasar para tests
    determinísticos; por defecto es hoy en UTC."""
    huella = _huella(datos, columnas_id, columna_fecha, columna_objetivo)
    config = {
        "n_cortes": n_cortes,
        "horizonte_max": horizonte_max,
        "columnas_id": list(columnas_id),
        "columna_objetivo": columna_objetivo,
        "densificado": densificado,
        "primer_corte": str(cortes[0].date()),
        "ultimo_corte": str(cortes[-1].date()),
        "huella_datos": huella,
    }
    canonico = json.dumps(config, sort_keys=True, ensure_ascii=False)
    id_corrida = hashlib.blake2s(canonico.encode("utf-8"), digest_size=6).hexdigest()

    return Corrida(
        id=id_corrida,
        fecha_ejecucion=fecha_ejecucion or datetime.now(tz=UTC).date().isoformat(),
        n_cortes=n_cortes,
        horizonte_max=horizonte_max,
        columnas_id=tuple(columnas_id),
        columna_objetivo=columna_objetivo,
        densificado=densificado,
        primer_corte=config["primer_corte"],
        ultimo_corte=config["ultimo_corte"],
        huella_datos=huella,
    )
