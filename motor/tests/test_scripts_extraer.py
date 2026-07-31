"""Tests de la transformación del extract del snap (M1.8).

`motor/scripts/extraer_snap.py` no es parte del paquete (es operación del track, no
código del job batch), así que se carga por ruta.

**Qué cubren y qué no.** La agregación de verdad la hace MySQL, y eso no se puede
testear sin una base. Lo que sí está bajo test es (a) la regla de neteo escrita en
pandas, que es la misma cuenta y la que `--verificar-mes` corre contra la SQL en la
corrida real, y (b) todo el post-procesamiento, que es donde vive el bug silencioso:
un `precio_prom` infinito o un dtype que no matchea el diccionario no rompen nada,
solo ensucian el piso.
"""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from motor.datos.diccionario import ESQUEMAS

RAIZ_REPO = Path(__file__).resolve().parents[2]
_RUTA = RAIZ_REPO / "motor" / "scripts" / "extraer_snap.py"
_spec = importlib.util.spec_from_file_location("extraer_snap", _RUTA)
extraer_snap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(extraer_snap)


def _renglon(producto_id, fecha, cantidad, precio, nota_credito=0):
    return {
        "fecha": pd.Timestamp(fecha),
        "nota_credito": nota_credito,
        "producto_id": producto_id,
        "cantidad": cantidad,
        "precio": precio,
    }


# ---------------------------------------------------------------------------
# netear_renglones — la regla de neteo
# ---------------------------------------------------------------------------


def test_la_nota_de_credito_resta_unidades_y_revenue():
    renglones = pd.DataFrame(
        [
            _renglon(1, "2025-03-05", cantidad=10, precio=100.0),
            _renglon(1, "2025-03-20", cantidad=4, precio=100.0, nota_credito=1),
        ]
    )

    salida = extraer_snap.netear_renglones(renglones)

    assert len(salida) == 1
    assert salida.loc[0, "unidades"] == pytest.approx(6.0)
    assert salida.loc[0, "revenue"] == pytest.approx(600.0)


@pytest.mark.parametrize(
    "crudo, es_nc",
    [
        (b"\x01", True),   # lo que devuelve pymysql sobre un BIT(1) en 1
        (b"\x00", False),  # ...y en 0
        (1, True),
        (0, False),
        (True, True),
        (None, False),
        (float("nan"), False),
    ],
)
def test_reconoce_la_nota_de_credito_venga_como_venga(crudo, es_nc):
    """`nota_credito` es BIT(1): pymysql lo entrega como bytes, no como entero.

    Si `b'\\x01'` no se reconoce, las devoluciones **suman en vez de restar** y el
    extract queda mal sin que nada falle. Los fixtures con `1`/`0` no cubren el caso
    real, que es el de bytes.
    """
    renglones = pd.DataFrame(
        [_renglon(1, "2025-03-05", cantidad=10, precio=100.0, nota_credito=crudo)]
    )

    salida = extraer_snap.netear_renglones(renglones)

    assert salida.loc[0, "unidades"] == pytest.approx(-10.0 if es_nc else 10.0)


def test_agrupa_por_producto_y_mes_no_por_comprobante():
    renglones = pd.DataFrame(
        [
            _renglon(1, "2025-03-05", cantidad=10, precio=100.0),
            _renglon(1, "2025-03-28", cantidad=5, precio=100.0),
            _renglon(1, "2025-04-02", cantidad=7, precio=100.0),
            _renglon(2, "2025-03-11", cantidad=3, precio=50.0),
        ]
    )

    salida = extraer_snap.netear_renglones(renglones).set_index(["producto_id", "anio", "mes"])

    assert salida.loc[(1, 2025, 3), "unidades"] == pytest.approx(15.0)
    assert salida.loc[(1, 2025, 4), "unidades"] == pytest.approx(7.0)
    assert salida.loc[(2, 2025, 3), "unidades"] == pytest.approx(3.0)


def test_un_mes_cancelado_entero_queda_en_cero_no_desaparece():
    """ADR-010: la demanda cero es un dato, no una ausencia.

    La query de cotizaciones descarta estos meses con `HAVING cantidad_total != 0`
    porque le sirve a su caso de uso. Acá se conservan a propósito.
    """
    renglones = pd.DataFrame(
        [
            _renglon(1, "2025-03-05", cantidad=8, precio=100.0),
            _renglon(1, "2025-03-25", cantidad=8, precio=100.0, nota_credito=1),
        ]
    )

    salida = extraer_snap.netear_renglones(renglones)

    assert len(salida) == 1
    assert salida.loc[0, "unidades"] == pytest.approx(0.0)


def test_el_revenue_conserva_el_signo_negativo():
    """Cotizaciones anula el revenue no positivo; acá es el numerador de ADR-002."""
    renglones = pd.DataFrame(
        [_renglon(1, "2025-03-25", cantidad=3, precio=100.0, nota_credito=1)]
    )

    salida = extraer_snap.netear_renglones(renglones)

    assert salida.loc[0, "unidades"] == pytest.approx(-3.0)
    assert salida.loc[0, "revenue"] == pytest.approx(-300.0)


# ---------------------------------------------------------------------------
# armar_hechos_producto — post-procesamiento
# ---------------------------------------------------------------------------


def _agregado(filas):
    return pd.DataFrame(
        filas, columns=["producto_id", "anio", "mes", "unidades", "revenue"]
    )


def test_precio_prom_es_revenue_sobre_unidades():
    hechos = extraer_snap.armar_hechos_producto(_agregado([(1, 2025, 3, 10.0, 1250.0)]))

    assert hechos.loc[0, "precio_prom"] == pytest.approx(125.0)
    assert hechos.loc[0, "anio_mes"] == pd.Timestamp("2025-03-01")


def test_con_cero_unidades_el_precio_queda_nan_y_no_infinito():
    """El caso real: un mes cuya venta se canceló entera con una NC a otro precio.

    Sin la guarda, `revenue / 0` es `inf` en pandas — y un infinito entra callado a la
    cadena de deflación de M2. Es el bug que este test existe para atajar: quitá el
    `.where(unidades != 0)` de armar_hechos_producto y esta aserción rompe.
    """
    hechos = extraer_snap.armar_hechos_producto(_agregado([(1, 2025, 3, 0.0, 100.0)]))

    valor = hechos.loc[0, "precio_prom"]
    assert not np.isinf(valor), f"precio_prom quedó en {valor}, tiene que ser NaN"
    assert pd.isna(valor)


def test_un_mes_de_neto_negativo_conserva_el_signo():
    hechos = extraer_snap.armar_hechos_producto(_agregado([(1, 2025, 3, -2.0, -240.0)]))

    assert hechos.loc[0, "unidades"] == pytest.approx(-2.0)
    assert hechos.loc[0, "precio_prom"] == pytest.approx(120.0)


def test_los_dtypes_son_los_del_diccionario():
    """Si esto rompe, `RepositorioArchivos` lee un parquet que no cumple el DER."""
    hechos = extraer_snap.armar_hechos_producto(
        _agregado([(7, 2025, 3, 10.0, 1000.0), (7, 2025, 4, 5.0, 500.0)])
    )

    esperado = ESQUEMAS["hecho_venta_mensual_producto"]
    assert list(hechos.columns) == list(esperado)
    for columna, dtype in esperado.items():
        assert str(hechos[columna].dtype) == dtype, f"{columna}: salió {hechos[columna].dtype}"


def test_el_producto_id_alfanumerico_del_erp_llega_como_entero():
    """MySQL devuelve el código como texto; el diccionario exige int64."""
    agregado = _agregado([("204", 2025, 3, 1.0, 10.0)])

    hechos = extraer_snap.armar_hechos_producto(agregado)

    assert hechos.loc[0, "id_producto"] == 204
    assert str(hechos["id_producto"].dtype) == "int64"


# ---------------------------------------------------------------------------
# resolver_variantes — `producto.id` es varchar, no entero
# ---------------------------------------------------------------------------


def test_mapea_el_entero_al_codigo_de_texto_que_vendio():
    """`'0057'` y `'57'` son productos distintos en el ERP; solo uno tiene ventas."""
    agregado = _agregado([("0057", 2025, 3, 10.0, 100.0), ("58", 2025, 3, 1.0, 10.0)])

    variantes = extraer_snap.resolver_variantes(agregado)

    assert dict(zip(variantes["id_producto"], variantes["id_texto"])) == {
        57: "0057",
        58: "58",
    }


def test_corta_si_dos_variantes_del_mismo_numero_tienen_ventas():
    """Colapsarlas fusionaría dos productos reales en una serie. No se elige una."""
    agregado = _agregado([("02", 2025, 3, 5.0, 50.0), ("2", 2025, 3, 7.0, 70.0)])

    with pytest.raises(SystemExit, match="fusionaría dos productos"):
        extraer_snap.resolver_variantes(agregado)


# ---------------------------------------------------------------------------
# filtrar_universo
# ---------------------------------------------------------------------------


def _hechos(filas):
    df = pd.DataFrame(filas, columns=["id_producto", "anio_mes", "unidades"])
    df["anio_mes"] = pd.to_datetime(df["anio_mes"])
    df["revenue"] = df["unidades"] * 10.0
    df["precio_prom"] = 10.0
    return df


def test_saca_los_productos_sin_venta_reciente():
    hechos = _hechos(
        [
            (1, "2019-01-01", 5.0),  # vendió hace años y nunca más
            (2, "2019-01-01", 5.0),
            (2, "2026-05-01", 3.0),  # activo
        ]
    )

    salida = extraer_snap.filtrar_universo(hechos, meses_actividad=36)

    assert set(salida["id_producto"]) == {2}
    # Al producto activo se le conserva TODA la historia, no solo la ventana reciente.
    assert len(salida) == 2


def test_un_producto_con_puros_ceros_recientes_no_cuenta_como_activo():
    """Densificar mete ceros; un cero no es una venta."""
    hechos = _hechos([(1, "2026-05-01", 0.0), (2, "2026-05-01", 1.0)])

    salida = extraer_snap.filtrar_universo(hechos, meses_actividad=36)

    assert set(salida["id_producto"]) == {2}


def test_meses_actividad_cero_no_filtra_nada():
    hechos = _hechos([(1, "2019-01-01", 5.0), (2, "2026-05-01", 3.0)])

    salida = extraer_snap.filtrar_universo(hechos, meses_actividad=0)

    assert set(salida["id_producto"]) == {1, 2}


# ---------------------------------------------------------------------------
# validar_contra_eda
# ---------------------------------------------------------------------------


def _catalogo(n_categorias):
    return pd.DataFrame(
        {
            "id_producto": range(n_categorias),
            "categoria": [f"CAT {i}" for i in range(n_categorias)],
            "laboratorio": ["1"] * n_categorias,
            "activo": [True] * n_categorias,
        }
    )


def _controles(hechos, catalogo):
    return {
        detalle.split(":")[0]: (fatal, estado)
        for fatal, estado, detalle in extraer_snap.validar_contra_eda(hechos, catalogo, 36)
    }


def test_es_fatal_que_la_historia_no_arranque_donde_dice_el_eda():
    hechos = _hechos([(1, "2020-01-01", 5.0), (1, "2020-02-01", 5.0)])

    controles = _controles(hechos, _catalogo(12))

    fatal, estado = controles["primer mes"]
    assert fatal and estado == "FALLA"


def test_es_fatal_que_falten_categorias():
    hechos = _hechos([(1, "2018-07-01", 5.0)])

    controles = _controles(hechos, _catalogo(8))

    fatal, estado = controles["categorías distintas"]
    assert fatal and estado == "FALLA"


def test_detecta_huecos_en_la_serie_de_meses():
    hechos = _hechos([(1, "2018-07-01", 5.0), (1, "2018-09-01", 5.0)])

    controles = _controles(hechos, _catalogo(12))

    fatal, estado = controles["meses sin huecos"]
    assert fatal and estado == "FALLA"


def test_un_extract_vacio_falla_sin_explotar():
    vacio = _hechos([]).iloc[0:0]

    resultado = extraer_snap.validar_contra_eda(vacio, _catalogo(12), 36)

    assert resultado == [(True, "FALLA", "filas devueltas: 0")]


# ---------------------------------------------------------------------------
# Conexión y regla de datos
# ---------------------------------------------------------------------------


def test_la_url_usa_el_driver_sync(monkeypatch):
    monkeypatch.setenv("DB_SNAP_URL", "mysql://u:p@host:3306/base")

    assert extraer_snap.construir_url() == "mysql+pymysql://u:p@host:3306/base"


def test_remapea_el_host_de_docker_al_tunel_local(monkeypatch):
    """El `.env` de cotizaciones apunta a `host.docker.internal`, que solo resuelve
    dentro de un contenedor. Nativo, el mismo túnel está en 127.0.0.1; sin el remapeo
    la corrida muere a los ~60 s con un timeout que no dice nada."""
    monkeypatch.setenv("DB_SNAP_URL", "mysql://u:p@host.docker.internal:3306/base")

    assert extraer_snap.construir_url() == "mysql+pymysql://u:p@127.0.0.1:3306/base"


def test_arma_la_url_desde_las_variables_de_cotizaciones(monkeypatch):
    monkeypatch.delenv("DB_SNAP_URL", raising=False)
    for sufijo, valor in [
        ("HOST", "10.0.0.1"),
        ("PORT", "3307"),
        ("NAME", "defeve"),
        ("USER", "lector"),
        ("PASS", "x"),
    ]:
        monkeypatch.setenv(f"DB_DFV_PROD_SNAP_{sufijo}", valor)

    assert extraer_snap.construir_url() == "mysql+pymysql://lector:x@10.0.0.1:3307/defeve"


def test_sin_credenciales_corta_con_un_mensaje_util(monkeypatch):
    for nombre in ["DB_SNAP_URL"] + [
        f"DB_DFV_PROD_SNAP_{s}" for s in ("HOST", "PORT", "NAME", "USER", "PASS")
    ]:
        monkeypatch.delenv(nombre, raising=False)

    with pytest.raises(SystemExit, match="DB_DFV_PROD_SNAP_HOST"):
        extraer_snap.construir_url()


def test_se_niega_a_escribir_en_una_ruta_versionada_del_repo():
    """Regla de oro (CLAUDE.md §4): el extract son datos reales, no van al repo."""
    assert extraer_snap._esta_versionado(RAIZ_REPO / "motor" / "backtests") is True


def test_la_guarda_tambien_atrapa_una_ruta_relativa(monkeypatch):
    """`--salida motor/backtests` tiene que quedar rechazada igual que la absoluta.

    Sin `resolve()`, `relative_to` tira ValueError sobre una ruta relativa y el destino
    pasa por "fuera del repo": el falso negativo deja datos reales en una ruta
    versionada, que es justo lo que la guarda tiene que impedir.
    """
    monkeypatch.chdir(RAIZ_REPO)

    assert extraer_snap._esta_versionado(Path("motor/backtests")) is True


def test_una_ruta_fuera_del_repo_es_destino_valido(tmp_path):
    assert extraer_snap._esta_versionado(tmp_path) is False
