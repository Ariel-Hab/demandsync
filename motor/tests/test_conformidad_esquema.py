"""Test de conformidad de esquema (T0.3, ADR-009).

Si el diccionario de columnas (`motor.datos.diccionario.ESQUEMAS`) diverge de lo que
efectivamente sobrevive un roundtrip por parquet, este test rompe. Es intencional:
el diccionario es espejo del DER, y cualquier drift se detecta acá antes de llegar
a producción (M4).
"""

import pandas as pd
import pytest

from motor.datos.archivos import RepositorioArchivos
from motor.datos.diccionario import ESQUEMAS

FILA_EJEMPLO = {
    "hecho_venta_mensual_producto": {
        "id_producto": 1,
        "anio_mes": "2026-01-01",
        "unidades": 10.0,
        "revenue": 1000.0,
        "precio_prom": 100.0,
    },
    "hecho_venta_mensual_cliente_producto": {
        "id_cliente": 1,
        "id_producto": 1,
        "anio_mes": "2026-01-01",
        "unidades": 5.0,
        "revenue": 500.0,
    },
    "catalogo_producto": {
        "id_producto": 1,
        "categoria": "antiparasitarios",
        "laboratorio": "labs_demo",
        "activo": True,
    },
    "cliente_feature": {
        "id_cliente": 1,
        "categoria_principal": "mayorista",
        "frecuencia_compra": "mensual",
        "volumen_anual": 1200.0,
        "valor_anual_estimado": 120000.0,
        "tendencia_volumen_3m": 0.05,
        "recency_dias": 15,
        "fecha_calculo": "2026-07-25",
    },
    "ancla_precio_producto": {
        "id_producto": 1,
        "precio_prom_hoy": 105.0,
        "fecha_calculo": "2026-07-25",
    },
    "indice_precio_nivel": {
        "nivel": "categoria",
        "id_nivel": "antiparasitarios",
        "anio_mes": "2026-01-01",
        "indice": 1.12,
    },
}


def _dataframe_tipado(tabla: str) -> pd.DataFrame:
    columnas = ESQUEMAS[tabla]
    df = pd.DataFrame([FILA_EJEMPLO[tabla]])
    for columna, dtype in columnas.items():
        df[columna] = df[columna].astype(dtype)
    return df


@pytest.mark.parametrize("tabla", ESQUEMAS.keys())
def test_esquema_sobrevive_roundtrip_parquet(tmp_path, tabla):
    columnas = ESQUEMAS[tabla]
    df = _dataframe_tipado(tabla)

    repo = RepositorioArchivos(tmp_path)
    repo._escribir(tabla, df)
    releido = repo._leer(tabla)

    assert list(releido.columns) == list(columnas.keys()), (
        f"{tabla}: columnas esperadas {list(columnas.keys())}, salieron {list(releido.columns)}"
    )
    for columna, dtype in columnas.items():
        assert str(releido[columna].dtype) == dtype, (
            f"{tabla}.{columna}: esperado dtype {dtype!r}, salió {releido[columna].dtype!r}"
        )


def test_tablas_lectura_y_escritura_cubren_el_diccionario():
    from motor.datos.diccionario import TABLAS_ESCRITURA, TABLAS_LECTURA

    assert set(TABLAS_LECTURA) | set(TABLAS_ESCRITURA) == set(ESQUEMAS.keys())
    assert set(TABLAS_LECTURA) & set(TABLAS_ESCRITURA) == set()
