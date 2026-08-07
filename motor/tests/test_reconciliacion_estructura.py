"""Tests de la estructura agrupada de M3.1 (`roadmap-motor.md` §7.2).

Lo que estos tests protegen es **lo que no falla solo**. Armar la jerarquía como árbol, o
fusionar dos etiquetas al construir el `unique_id`, produce una matriz `S` perfectamente
válida que reconcilia contra restricciones equivocadas: números plausibles, resultado mal.
Por eso casi todos son casos donde la función tiene que **cortar**.

El fixture es deliberadamente el caso que motiva §7.2: `L1` vende en las categorías `A` y
`B`, así que la estructura **no** es un árbol. Un fixture donde cada laboratorio viviera en
una sola categoría pasaría en verde con la implementación de árbol y con la agrupada — sería
uno de los fixtures que confirman en vez de probar.
"""

import numpy as np
import pandas as pd
import pytest

from motor.reconciliacion.estructura import (
    NIVELES,
    construir_estructura,
    verificar_coherencia,
)

MESES = pd.date_range("2025-01-01", periods=6, freq="MS")

# (producto, categoria, laboratorio) — L1 cruza A y B: es el caso de §7.2
CATALOGO = [(1, "A", "L1"), (2, "A", "L2"), (3, "B", "L1"), (4, "B", "L3")]


def _catalogo(filas=None) -> pd.DataFrame:
    return pd.DataFrame(
        filas if filas is not None else CATALOGO,
        columns=["id_producto", "categoria", "laboratorio"],
    )


def _hechos(productos=None) -> pd.DataFrame:
    productos = productos if productos is not None else [p for p, _, _ in CATALOGO]
    filas = [
        {"id_producto": p, "anio_mes": mes, "unidades": 10.0 * p + i}
        for p in productos
        for i, mes in enumerate(MESES)
    ]
    return pd.DataFrame(filas)


def test_la_estructura_es_agrupada_y_no_un_arbol():
    """El corazón de §7.2: `L1` cuelga de productos que están en **dos** categorías.

    En un árbol `total → categoria → laboratorio → producto` esto no se puede representar:
    `L1` tendría que elegir una categoría. Se verifica sobre la matriz `S`, que es donde vive
    la afirmación estructural.
    """
    estructura = construir_estructura(_hechos(), _catalogo())

    fila_l1 = estructura.S.loc["total/L1"]
    cuelgan = sorted(fila_l1[fila_l1 > 0].index)
    assert cuelgan == ["total/A/L1/1", "total/B/L1/3"]

    # y las dos categorías siguen separadas: la agrupación no las fusionó
    assert estructura.S.loc["total/A"].sum() == 2
    assert estructura.S.loc["total/B"].sum() == 2


def test_los_cinco_niveles_existen_y_estan_etiquetados():
    estructura = construir_estructura(_hechos(), _catalogo())

    assert sorted(set(estructura.niveles)) == sorted(NIVELES)
    conteo = estructura.niveles.value_counts()
    assert conteo["total"] == 1
    assert conteo["categoria"] == 2
    assert conteo["laboratorio"] == 3
    assert conteo["categoria_laboratorio"] == 4  # A/L1, A/L2, B/L1, B/L3
    assert conteo["producto"] == 4
    assert len(estructura) == 14


def test_la_coherencia_cierra_sobre_los_reales():
    """`S · base` reproduce los agregados exacto. Es el punto 1 del gate y no necesita
    backtest: la coherencia es algebraica."""
    estructura = construir_estructura(_hechos(), _catalogo())
    incoherentes = verificar_coherencia(
        estructura.Y_df.reset_index(), estructura, columna_valor="y"
    )
    assert incoherentes.empty


def test_la_verificacion_detecta_una_incoherencia_sembrada():
    """Guarda contra el modo de falla más aburrido: que `verificar_coherencia` devuelva vacío
    siempre y el test de arriba no pruebe nada."""
    estructura = construir_estructura(_hechos(), _catalogo())
    valores = estructura.Y_df.reset_index()
    roto = valores["unique_id"] == "total"
    valores.loc[roto, "y"] = valores.loc[roto, "y"] + 1.0

    incoherentes = verificar_coherencia(valores, estructura, columna_valor="y")
    assert not incoherentes.empty
    assert set(incoherentes["unique_id"]) == {"total"}
    assert np.allclose(incoherentes["desvio"], 1.0)


def test_un_hueco_en_el_panel_base_no_pasa_como_coherente():
    """Un mes ausente se cuenta como 0 y **no** como NaN.

    Con NaN el producto `S · base` daría NaN, la comparación sería `False` y la incoherencia
    pasaría sin marcarse — una falsa señal de que cierra, que es peor que no verificar.
    """
    estructura = construir_estructura(_hechos(), _catalogo())
    valores = estructura.Y_df.reset_index()
    sin_un_producto = valores[
        ~((valores["unique_id"] == "total/A/L1/1") & (valores["ds"] == MESES[2]))
    ]

    incoherentes = verificar_coherencia(sin_un_producto, estructura, columna_valor="y")
    assert not incoherentes.empty
    assert "total" in set(incoherentes["unique_id"])


def test_densifica_antes_de_agregar():
    """Un mes sin ventas de ningún producto de un laboratorio chico igual tiene fila en 0.

    Sin densificar (ADR-010) el laboratorio tendría huecos que el total no tiene y `S`
    dejaría de cerrar justo ahí: la incoherencia parecería del método de reconciliación
    cuando es del panel.
    """
    hechos = _hechos()
    hueco = (hechos["id_producto"] == 4) & (hechos["anio_mes"] == MESES[3])
    estructura = construir_estructura(hechos[~hueco], _catalogo())

    l3 = estructura.Y_df.loc["total/L3"]
    assert len(l3) == len(MESES)
    assert float(l3.loc[l3["ds"] == MESES[3], "y"].iloc[0]) == 0.0


# --------------------------------------------------------------------------------------
# Lo que tiene que cortar
# --------------------------------------------------------------------------------------


def test_corta_si_un_producto_tiene_dos_grupos():
    """Un producto en dos laboratorios lo contaría dos veces en `S` y el total dejaría de
    ser el total. No hay forma de resolverlo sin elegir por el usuario."""
    catalogo = _catalogo([*CATALOGO, (1, "A", "L9")])
    with pytest.raises(ValueError, match="más de un par"):
        construir_estructura(_hechos(), catalogo)


def test_corta_si_falta_categoria_o_laboratorio():
    catalogo = _catalogo().drop(columns=["laboratorio"])
    with pytest.raises(ValueError, match="laboratorio"):
        construir_estructura(_hechos(), catalogo)


def test_corta_ante_grupos_nulos():
    """`aggregate` agruparía los nulos bajo la etiqueta 'nan' sin avisar. `SIN CATEGORIA` es
    un valor real del ERP y sí es un grupo legítimo; `None` no."""
    catalogo = _catalogo([(1, "A", "L1"), (2, None, "L2"), (3, "B", "L1"), (4, "B", "L3")])
    with pytest.raises(ValueError, match="nulos"):
        construir_estructura(_hechos(), catalogo)


def test_corta_si_dos_etiquetas_colapsan_al_sacar_la_barra():
    """`aggregate` arma el `unique_id` pegando niveles con `/` y reemplaza el `/` de los
    valores por `_`: `A/B` y `A_B` quedarían con el mismo id y se sumarían en silencio."""
    catalogo = _catalogo(
        [(1, "A/B", "L1"), (2, "A_B", "L2"), (3, "B", "L1"), (4, "B", "L3")]
    )
    with pytest.raises(ValueError, match="colapsan"):
        construir_estructura(_hechos(), catalogo)


def test_corta_si_un_producto_de_los_hechos_no_esta_en_el_catalogo():
    """Dejarlo afuera cambiaría el total en silencio, que es el peor de los resultados
    posibles para una estructura cuya razón de ser es que los niveles sumen."""
    with pytest.raises(ValueError, match="no están en el catálogo"):
        construir_estructura(_hechos([1, 2, 3, 4, 99]), _catalogo())


def test_el_id_de_producto_se_castea_a_texto_sin_fusionar():
    """`aggregate` exige columnas de agrupación `str`. El casteo es `int → str`, que es
    inyectivo — **no** es el bug de §5.5, donde el peligro era `str → int` (muchos a uno:
    `'2'`, `'02'` y `'0002'` colapsan al mismo entero)."""
    catalogo = _catalogo([(2, "A", "L1"), (20, "A", "L2"), (200, "B", "L1"), (4, "B", "L3")])
    estructura = construir_estructura(_hechos([2, 20, 200, 4]), catalogo)

    productos = estructura.niveles[estructura.niveles == "producto"].index
    assert len(set(productos)) == 4
