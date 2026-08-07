"""Tests de la reconciliación de M3.1 (`roadmap-motor.md` §7.2).

Tres focos:

1. **Coherencia** — la salida reconciliada suma. Es el punto 1 del gate y lo que distingue a
   esta unidad de "predecir cada nivel por separado".
2. **Regla prospectiva** (`test_la_reconciliacion_no_mira_el_futuro`, `innegociable`) — la
   covarianza de MinT se estima solo con lo observado al corte. Es el punto 2 de §7.2 y la
   trampa fina de la unidad: acá el hindsight no quedaría en una elección de modelo visible
   en una tabla sino **adentro de una matriz de pesos**, donde nadie lo mira.
3. **Degradación honesta** — si en un corte no hay residuos, `mint_shrink` queda en `NaN` en
   vez de correr con una covarianza inventada.
"""

import numpy as np
import pandas as pd
import pytest

from motor.reconciliacion.estructura import construir_estructura, verificar_coherencia
from motor.reconciliacion.reconciliar import reconciliar

MESES = pd.date_range("2025-01-01", periods=12, freq="MS")
CATALOGO = [(1, "A", "L1"), (2, "A", "L2"), (3, "B", "L1"), (4, "B", "L3")]
CORTES = [MESES[5], MESES[6], MESES[7]]
HORIZONTE = 3


def _catalogo() -> pd.DataFrame:
    return pd.DataFrame(CATALOGO, columns=["id_producto", "categoria", "laboratorio"])


def _hechos() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"id_producto": p, "anio_mes": mes, "unidades": 10.0 * p + i + (i % 3)}
            for p, _, _ in CATALOGO
            for i, mes in enumerate(MESES)
        ]
    )


def _base(estructura, factor: float = 1.1) -> pd.DataFrame:
    """Pronósticos base **incoherentes a propósito**: cada serie se predice por separado con
    un sesgo que depende del nivel, así que los niveles no suman y hay algo que reconciliar.

    Un base ya coherente haría que todos los métodos devolvieran lo mismo y los tests pasarían
    sin distinguir nada — el modo de falla de los fixtures de M2.2.
    """
    reales = estructura.Y_df.reset_index()
    filas = []
    for corte in CORTES:
        objetivos = [m for m in MESES if m > corte][:HORIZONTE]
        for h, objetivo in enumerate(objetivos, start=1):
            del_mes = reales[reales["ds"] == objetivo]
            for _, fila in del_mes.iterrows():
                nivel = estructura.niveles[fila["unique_id"]]
                sesgo = factor if nivel == "producto" else 1.0
                filas.append(
                    {
                        "unique_id": fila["unique_id"],
                        "ds": objetivo,
                        "corte": corte,
                        "horizonte": h,
                        "y": fila["y"],
                        "modelo": fila["y"] * sesgo,
                    }
                )
    # los residuos salen de las filas ya observadas: se agregan los meses <= corte a h=1
    for corte in CORTES:
        for mes in MESES[MESES <= corte]:
            del_mes = reales[reales["ds"] == mes]
            for _, fila in del_mes.iterrows():
                filas.append(
                    {
                        "unique_id": fila["unique_id"],
                        "ds": mes,
                        "corte": corte,
                        "horizonte": 1,
                        "y": fila["y"],
                        "modelo": fila["y"] * 1.05,
                    }
                )
    return pd.DataFrame(filas)


@pytest.fixture
def escenario():
    estructura = construir_estructura(_hechos(), _catalogo())
    return estructura, _base(estructura)


def _del_corte(reconciliado: pd.DataFrame, corte, columna: str) -> pd.DataFrame:
    del_corte = reconciliado[
        (reconciliado["corte"] == corte) & (reconciliado["ds"] > corte)
    ]
    return del_corte[["unique_id", "ds", columna]]


# --------------------------------------------------------------------------------------
# 1. Coherencia
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "metodo", ["bottom_up", "ols", "wls_struct", "mint_shrink"]
)
def test_la_salida_reconciliada_es_coherente(escenario, metodo):
    """Todos los métodos tienen que producir niveles que suman. Es la definición de
    reconciliar; si alguno no lo cumple, está mal enchufado."""
    estructura, base = escenario
    reconciliado = reconciliar(base, estructura, columna_modelo="modelo", metodos=[metodo])

    for corte in CORTES:
        incoherentes = verificar_coherencia(
            _del_corte(reconciliado, corte, f"pred_{metodo}"),
            estructura,
            columna_valor=f"pred_{metodo}",
        )
        assert incoherentes.empty, f"{metodo} no cierra en {corte}: {incoherentes.head()}"


def test_el_base_sin_reconciliar_no_es_coherente(escenario):
    """La contraparte del test de arriba: si el base ya sumara, reconciliar no haría nada y
    los tests de coherencia pasarían sin probar que la reconciliación funciona."""
    estructura, base = escenario
    incoherentes = verificar_coherencia(
        _del_corte(base, CORTES[0], "modelo"), estructura, columna_valor="modelo"
    )
    assert not incoherentes.empty


def test_bottom_up_respeta_las_predicciones_de_producto(escenario):
    """Bottom-up no toca el nivel base: reconstruye todo sumando hacia arriba. Es lo que lo
    hace el piso gratis de la unidad — no necesita las 296 series agregadas."""
    estructura, base = escenario
    reconciliado = reconciliar(base, estructura, columna_modelo="modelo", metodos=["bottom_up"])

    del_corte = reconciliado[
        (reconciliado["corte"] == CORTES[0]) & (reconciliado["ds"] > CORTES[0])
    ]
    productos = del_corte[del_corte["unique_id"].isin(estructura.series_base)]
    assert np.allclose(productos["modelo"], productos["pred_bottom_up"])

    # y arriba sí cambió algo, o el test no probaría nada
    total = del_corte[del_corte["unique_id"] == "total"]
    assert not np.allclose(total["modelo"], total["pred_bottom_up"])


# --------------------------------------------------------------------------------------
# 2. Regla prospectiva — el gate de la unidad
# --------------------------------------------------------------------------------------


@pytest.mark.innegociable
def test_la_reconciliacion_no_mira_el_futuro(escenario):
    """**El gate de M3.1.** Perturbar los reales posteriores al corte `T` no puede mover la
    reconciliación de los cortes `<= T`.

    Es la red de M1.3/M1.9 sobre la matriz de pesos de MinT. Si la covarianza se estimara con
    todos los cortes, este test falla — y lo haría en silencio en producción, porque el
    hindsight no dejaría rastro en ninguna columna del reporte.

    La segunda mitad —que un corte posterior **sí** se mueva— es lo que evita que el test
    pase porque la perturbación no perturbó nada.
    """
    estructura, base = escenario
    corte_limite = CORTES[0]

    original = reconciliar(base, estructura, columna_modelo="modelo", metodos=["mint_shrink"])

    perturbado_df = base.copy()
    posterior = perturbado_df["ds"] > corte_limite
    perturbado_df.loc[posterior, "y"] = perturbado_df.loc[posterior, "y"] * 7.0
    perturbado = reconciliar(
        perturbado_df, estructura, columna_modelo="modelo", metodos=["mint_shrink"]
    )

    def hasta(r):
        return (
            r[r["corte"] <= corte_limite]
            .sort_values(["unique_id", "ds"])
            .reset_index(drop=True)["pred_mint_shrink"]
        )

    pd.testing.assert_series_equal(hasta(original), hasta(perturbado))

    def en(r, corte):
        return (
            r[r["corte"] == corte]
            .sort_values(["unique_id", "ds"])
            .reset_index(drop=True)["pred_mint_shrink"]
        )

    assert not np.allclose(en(original, CORTES[2]), en(perturbado, CORTES[2]))


def test_sin_residuos_observados_mint_queda_nulo_y_los_otros_corren(escenario):
    """Degradación honesta: en un corte sin nada observado, `mint_shrink` no corre con una
    covarianza inventada — queda `NaN` y la columna `cobertura` del reporte lo expone.

    Caer a una identidad silenciosa sería peor que no correr: la tabla diría `mint_shrink` y
    el número sería el de `ols`.
    """
    estructura, base = escenario
    # Solo el primer corte y solo su futuro: ahí no hay ningún mes ya observado. Recortar
    # `ds > corte` sobre los tres cortes NO alcanza — los pronósticos del corte 1 caen dentro
    # del pasado del corte 3 y sí son residuo válido para él.
    primer_corte = base[(base["corte"] == CORTES[0]) & (base["ds"] > CORTES[0])]

    reconciliado = reconciliar(
        primer_corte, estructura, columna_modelo="modelo",
        metodos=["bottom_up", "mint_shrink"],
    )
    assert reconciliado["pred_mint_shrink"].isna().all()
    assert reconciliado["pred_bottom_up"].notna().all()


# --------------------------------------------------------------------------------------
# 3. Contrato
# --------------------------------------------------------------------------------------


def test_conserva_la_forma_del_base(escenario):
    """El merge no puede duplicar ni perder filas: `backtesting.reporte` y `comparacion`
    consumen esta tabla sin saber que pasó por reconciliación."""
    estructura, base = escenario
    reconciliado = reconciliar(base, estructura, columna_modelo="modelo")

    assert len(reconciliado) == len(base)
    assert set(base.columns) <= set(reconciliado.columns)
    for metodo in ("bottom_up", "ols", "wls_struct", "mint_shrink"):
        assert f"pred_{metodo}" in reconciliado.columns


def test_corta_ante_un_metodo_desconocido(escenario):
    estructura, base = escenario
    with pytest.raises(ValueError, match="Métodos desconocidos"):
        reconciliar(base, estructura, columna_modelo="modelo", metodos=["mint_magico"])
