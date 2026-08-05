"""Features del modelo global (M2.2).

El gate de la unidad es que `construir_features` pase la red anti-leakage de M1.3, y ese
test está marcado `innegociable`. Lo demás cubre las tres cosas que se rompen en silencio:
la feature degenerada que la especificación pedía literal, el contraste contra el IPC (que
contradiría a ADR-002) y el alineado por calendario sobre series dispersas.
"""

import numpy as np
import pandas as pd
import pytest

from motor.backtesting.leakage import verificar_sin_leakage
from motor.deflacion.transformador import TransformadorDeflacion
from motor.features import (
    COLUMNAS_FEATURES,
    LAGS,
    STATIC_FEATURES,
    cobertura_de_features,
    construir_features,
)

MESES = 24
INICIO = "2024-01-01"


def _hechos(filas: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(filas).astype({"id_producto": "int64"})


@pytest.fixture
def catalogo():
    """Ocho productos en dos categorías de cuatro.

    **Cuatro por categoría no es decorativo:** `MUESTRA_MINIMA = 3` exige tres pares de
    relativos para que un nivel tenga índice en un mes, y el producto 3 deja de vender en el
    mes 10. Con tres por categoría, la baja dejaría a esa categoría sin índice y las tablas
    que compara la red anti-leakage quedarían casi vacías — pasaría sin probar nada. Es
    exactamente el agujero que la mutación encontró en el fixture de M2.1 (§6.2).
    """
    return pd.DataFrame(
        {
            "id_producto": range(1, 9),
            "categoria": ["A"] * 4 + ["B"] * 4,
            "laboratorio": ["L1"] * 8,
            "activo": [True] * 8,
        }
    ).astype({"id_producto": "int64"})


@pytest.fixture
def datos():
    """Ocho productos, 24 meses, precios inflacionarios.

    El producto 1 sube **más rápido que su categoría** (9% mensual contra 5%): es el que
    hace que `precio_rel_nivel` se despegue de 1,0 y que el test tenga algo que medir. El
    producto 3 **deja de vender en el mes 10**, que es el camino del fallback.
    """
    meses = pd.date_range(INICIO, periods=MESES, freq="MS")
    filas = []
    for p in range(1, 9):
        tasa = 1.09 if p == 1 else 1.05
        for i, m in enumerate(meses):
            if p == 3 and i >= 10:
                continue
            precio = 100.0 * p * tasa**i
            unidades = float(10 + (i % 5))
            filas.append(
                {
                    "id_producto": p,
                    "anio_mes": m,
                    "unidades": unidades,
                    "revenue": unidades * precio,
                    "precio_prom": precio,
                }
            )
    return _hechos(filas)


@pytest.fixture
def cortes(datos):
    ultimo = datos["anio_mes"].max()
    return [ultimo - pd.DateOffset(months=k) for k in (12, 6, 1)]


@pytest.fixture
def corte(datos):
    return datos["anio_mes"].max()


# ---------------------------------------------------------------------------------
# El gate: la red anti-leakage de M1.3
# ---------------------------------------------------------------------------------


@pytest.mark.innegociable
def test_construir_features_no_mira_el_futuro(datos, catalogo, cortes):
    """**Gate de salida de M2.2.**

    Si esto falla, las features vieron datos posteriores al corte y el WAPE de M2.3 va a
    salir *mejor* de lo que corresponde — el error que se manifiesta como buena noticia.
    """
    verificar_sin_leakage(
        lambda d, c: construir_features(d, c, catalogo=catalogo),
        datos=datos,
        cortes=cortes,
    )


@pytest.mark.innegociable
def test_el_fixture_de_la_red_no_esta_vacio(datos, catalogo, cortes):
    """Una red que compara dos tablas de nulos pasa siempre y no prueba nada.

    Fija que en el corte más exigente (el más viejo, con menos historia) las features de
    precio están efectivamente pobladas, así que el test de arriba tiene sustancia.
    """
    features = construir_features(datos, cortes[0], catalogo=catalogo)
    assert features["precio_rel_nivel"].notna().mean() > 0.9
    assert features["var_precio_rel_3m"].notna().sum() > 0
    # Y que no sea todo el mismo número: si `precio_rel_nivel` fuera constante, un leakage
    # que la moviera parejo tampoco se vería.
    assert features["precio_rel_nivel"].std() > 0


# ---------------------------------------------------------------------------------
# Lo que NO se construye, y por qué (ADR-013)
# ---------------------------------------------------------------------------------


def test_el_precio_deflactado_propio_es_exactamente_el_ancla(datos, catalogo, corte):
    """La medición que justifica ADR-013 y toda la reformulación de M2.2.

    Deflactar el precio de un producto con su **propio** deflactor devuelve el ancla, porque
    el deflactor se construyó a partir de ese precio: `precio × (ancla/precio) = ancla`. La
    columna que pedía `plan-diseno.md` §M2 es constante por serie y su variación, cero.

    Este test está para que nadie la reintroduzca creyendo que es señal.
    """
    t = TransformadorDeflacion(catalogo=catalogo).ajustar(datos, corte)
    visible = datos[datos["anio_mes"] <= corte]
    con_deflactor = visible.merge(t.deflactor_, on=["id_producto", "anio_mes"], how="left")

    precio_deflactado = con_deflactor["precio_prom"] * con_deflactor["deflactor"]
    ancla = t.ancla_.set_index("id_producto")["precio_prom_hoy"]
    esperado = ancla.reindex(con_deflactor["id_producto"]).to_numpy()

    medibles = precio_deflactado.notna()
    assert medibles.sum() > 0
    assert np.allclose(precio_deflactado[medibles], esperado[medibles], rtol=1e-9)

    # Y por lo tanto: cero variación temporal intra-producto.
    cv = (
        pd.DataFrame({"id": con_deflactor["id_producto"], "p": precio_deflactado})
        .dropna()
        .groupby("id")["p"]
        .std()
    )
    assert cv.max() == pytest.approx(0.0, abs=1e-9)


def test_el_monto_deflactado_es_el_target_reescalado(datos, catalogo, corte):
    """La otra mitad de ADR-013: `revenue_real = unidades × ancla`.

    O sea que a grano producto el monto deflactado es el target multiplicado por una
    constante por serie — no es señal independiente y no entra como feature.
    """
    t = TransformadorDeflacion(catalogo=catalogo).ajustar(datos, corte)
    real = t.transformar(datos[datos["anio_mes"] <= corte])
    ancla = t.ancla_.set_index("id_producto")["precio_prom_hoy"]
    esperado = real["unidades"] * ancla.reindex(real["id_producto"]).to_numpy()

    medibles = real["revenue_real"].notna()
    assert medibles.sum() > 0
    assert np.allclose(real.loc[medibles, "revenue_real"], esperado[medibles], rtol=1e-9)


def test_las_features_no_incluyen_montos_deflactados(datos, catalogo, corte):
    features = construir_features(datos, corte, catalogo=catalogo)
    assert not [c for c in features.columns if "revenue" in c or c == "precio_real"]


# ---------------------------------------------------------------------------------
# La feature que sí tiene señal
# ---------------------------------------------------------------------------------


def test_un_producto_que_se_mueve_como_su_categoria_da_una_serie_plana(datos, catalogo, corte):
    """La propiedad **exacta** de la feature, que es de forma y no de nivel.

    El nivel de `precio_rel_nivel` lleva una constante por producto (`ancla / precio` — el
    ancla es el promedio ponderado de 3 meses, no el precio del corte), así que "vale 1"
    es aproximado. Lo que **sí** es exacto, y es lo que la feature aporta:

    - La categoría B (productos 5 a 8) crece toda al 5%: cada miembro se mueve igual que su
      índice, y su serie queda **plana**. Ese es el "se movió con su categoría".
    - El producto 1 crece al 9% dentro de la categoría A, o sea que **se encareció** contra
      su vecindario. Su serie es entonces **estrictamente creciente**: en el pasado estaba
      relativamente más barato de lo que está hoy. El signo se lee al revés de lo que
      sugiere la intuición, y por eso está fijado acá.
    """
    features = construir_features(datos, corte, catalogo=catalogo)
    serie = features.dropna(subset=["precio_rel_nivel"]).set_index("anio_mes")

    de_b = serie.loc[serie["id_producto"] == 5, "precio_rel_nivel"]
    assert len(de_b) > 12
    assert de_b.std() == pytest.approx(0.0, abs=1e-12)
    # Plana también significa variación exactamente nula, que es la columna que entrena.
    var_b = features.loc[features["id_producto"] == 5, "var_precio_rel_3m"].dropna()
    assert len(var_b) > 0
    assert var_b.abs().max() == pytest.approx(0.0, abs=1e-12)

    de_a = serie.loc[serie["id_producto"] == 1, "precio_rel_nivel"].sort_index()
    assert len(de_a) > 12
    assert (de_a.diff().dropna() > 0).all()
    assert de_a.iloc[0] < 0.7 * de_a.iloc[-1]


def test_el_primer_mes_del_panel_no_tiene_nivel(datos, catalogo, corte):
    """Propiedad de cobertura, no defecto: el índice de un nivel se construye con **pares**
    de meses consecutivos, así que el primer mes del panel no tiene relativo y ningún
    producto tiene contra qué medirse ahí. Sobre el extract real esto es parte del 1,01% de
    filas sin `precio_rel_nivel`; queda en `NaN` y no se imputa."""
    features = construir_features(datos, corte, catalogo=catalogo)
    primer_mes = features["anio_mes"].min()

    assert features.loc[features["anio_mes"] == primer_mes, "precio_rel_nivel"].isna().all()
    assert features.loc[features["anio_mes"] > primer_mes, "precio_rel_nivel"].notna().any()


def test_la_variacion_es_por_calendario_y_no_por_filas():
    """Sobre una serie con huecos, tres filas atrás no son tres meses atrás.

    Con `shift(3)` este producto compararía contra un mes de hace ocho, y el número saldría
    con cara de variación trimestral. El único mes que puede tener `var_precio_rel_3m` es el
    que tiene un mes calendario a exactamente −3.

    Tres detalles del fixture que son los que le dan poder de discriminación, y que la
    verificación por mutación encontró al pasar la primera versión sin cazar nada:

    1. Los productos 2 a 4 venden **todos los meses**, para que la categoría tenga índice.
    2. El producto 1 crece al **10% contra el 4% de su categoría**, así que su
       `precio_rel_nivel` cambia mes a mes. Si creciera igual que ella la serie sería plana
       y las dos formas de alinear darían el mismo número.
    3. El panel arranca **un mes antes** de la primera venta del producto 1, para que su
       primer mes tenga índice: si fuera nulo, el alineado por filas daría `NaN` por la vía
       equivocada y el test pasaría igual.
    """
    calendario = pd.date_range("2023-12-01", "2025-02-01", freq="MS")
    meses_dispersos = [
        pd.Timestamp("2024-01-01"),
        pd.Timestamp("2024-02-01"),
        pd.Timestamp("2024-03-01"),
        pd.Timestamp("2024-11-01"),
        pd.Timestamp("2025-02-01"),
    ]
    filas = [
        {
            "id_producto": p,
            "anio_mes": m,
            "unidades": 10.0,
            "revenue": 10.0 * 100.0 * p * (1.10 if p == 1 else 1.04) ** i,
            "precio_prom": 100.0 * p * (1.10 if p == 1 else 1.04) ** i,
        }
        for p in (1, 2, 3, 4)
        for i, m in enumerate(calendario)
        if p != 1 or m in meses_dispersos
    ]
    catalogo = pd.DataFrame(
        {"id_producto": [1, 2, 3, 4], "categoria": ["A"] * 4, "laboratorio": ["L1"] * 4}
    ).astype({"id_producto": "int64"})

    features = construir_features(_hechos(filas), calendario[-1], catalogo=catalogo)
    del_producto = features[features["id_producto"] == 1].set_index("anio_mes")

    # 2025-02 está a 3 meses de 2024-11: es el único par válido.
    assert del_producto.loc[pd.Timestamp("2025-02-01"), "var_precio_rel_3m"] == pytest.approx(
        del_producto.loc[pd.Timestamp("2025-02-01"), "precio_rel_nivel"]
        / del_producto.loc[pd.Timestamp("2024-11-01"), "precio_rel_nivel"]
        - 1.0
    )
    # 2024-11 está a 8 meses del anterior con dato, no a 3: no hay variación trimestral.
    assert pd.isna(del_producto.loc[pd.Timestamp("2024-11-01"), "var_precio_rel_3m"])


def test_el_contraste_no_usa_el_ipc(corte):
    """ADR-002 al revés sería contrastar contra el IPC, y eso no prueba nada.

    Un producto cuya categoría y cuyo laboratorio son de un solo miembro no tiene espejo
    construido con precios del cliente, así que `precio_rel_nivel` **tiene que quedar nulo**.
    Si alguien cambiara el default de `factor_de_nivel` a la cascada completa, el IPC
    respondería y este producto saldría con un número — que es justamente el error.
    """
    meses = pd.date_range(INICIO, periods=12, freq="MS")
    filas = [
        {
            "id_producto": p,
            "anio_mes": m,
            "unidades": 10.0,
            "revenue": 10.0 * 100.0 * p * 1.05**i,
            "precio_prom": 100.0 * p * 1.05**i,
        }
        for p in (1, 2, 3, 4, 9)
        for i, m in enumerate(meses)
    ]
    catalogo = pd.DataFrame(
        {
            "id_producto": [1, 2, 3, 4, 9],
            "categoria": ["A", "A", "A", "A", "SOLO"],
            "laboratorio": ["L1", "L1", "L1", "L1", "LSOLO"],
        }
    ).astype({"id_producto": "int64"})

    features = construir_features(_hechos(filas), meses[-1], catalogo=catalogo)
    solitario = features[features["id_producto"] == 9]
    acompanados = features[features["id_producto"] == 1]

    assert solitario["precio_rel_nivel"].isna().all()
    assert acompanados["precio_rel_nivel"].notna().any()


# ---------------------------------------------------------------------------------
# Casos degenerados — donde este repo ya se quemó
# ---------------------------------------------------------------------------------


def _con_producto_9(datos, catalogo, filas_9):
    extra = _hechos(filas_9)
    catalogo_ext = pd.concat(
        [catalogo, pd.DataFrame([{"id_producto": 9, "categoria": "A", "laboratorio": "L1"}])],
        ignore_index=True,
    ).astype({"id_producto": "int64"})
    return pd.concat([datos, extra], ignore_index=True), catalogo_ext


def test_producto_sin_ningun_precio_utilizable(datos, catalogo, corte):
    """Un producto que solo tuvo meses de neto cero (`unidades == 0` → precio nulo) y notas
    de crédito con precio negativo. Es el 3,53% + 0,016% de las filas reales (§5.5 #6): no
    rompe, queda en `NaN` —no tiene ancla desde donde medirse— y no sale negativo."""
    hechos, catalogo_ext = _con_producto_9(
        datos,
        catalogo,
        [
            {
                "id_producto": 9,
                "anio_mes": m,
                "unidades": 0.0 if i % 2 else -2.0,
                "revenue": 0.0 if i % 2 else 300.0,
                "precio_prom": np.nan if i % 2 else -150.0,
            }
            for i, m in enumerate(pd.date_range(INICIO, periods=MESES, freq="MS"))
        ],
    )
    features = construir_features(hechos, corte, catalogo=catalogo_ext)
    del_producto = features[features["id_producto"] == 9]

    assert len(del_producto) == MESES
    assert del_producto["precio_rel_nivel"].isna().all()
    assert not (features["precio_rel_nivel"] < 0).any()


def test_precios_negativos_aislados_no_contaminan_al_producto(datos, catalogo, corte):
    """El caso real de §5.5 #6: un producto **que vende normalmente** y tiene dos meses con
    precio implícito negativo, porque unidades y revenue netean por separado y una nota de
    crédito a otro precio cruza los signos.

    Ese producto **sí** tiene ancla, así que el `NaN` no puede venir de ahí: si la máscara
    `es_utilizable` no estuviera, esos meses saldrían con un precio relativo **negativo**,
    que a un árbol le parece un dato perfectamente válido.
    """
    meses = pd.date_range(INICIO, periods=MESES, freq="MS")
    rotos = {5, 11}
    hechos, catalogo_ext = _con_producto_9(
        datos,
        catalogo,
        [
            {
                "id_producto": 9,
                "anio_mes": m,
                "unidades": -2.0 if i in rotos else 10.0,
                "revenue": 300.0 if i in rotos else 10.0 * 150.0 * 1.05**i,
                "precio_prom": -150.0 if i in rotos else 150.0 * 1.05**i,
            }
            for i, m in enumerate(meses)
        ],
    )
    features = construir_features(hechos, corte, catalogo=catalogo_ext)
    del_producto = features[features["id_producto"] == 9].set_index("anio_mes")

    assert del_producto["precio_ancla"].notna().all(), "el producto tiene que tener ancla"
    for i in rotos:
        assert pd.isna(del_producto.loc[meses[i], "precio_rel_nivel"])
    assert del_producto["precio_rel_nivel"].notna().sum() > 10
    assert not (features["precio_rel_nivel"] < 0).any()


def test_un_ancla_no_positiva_no_produce_un_relativo_con_signo(datos, catalogo, corte):
    """Defensa en profundidad, y por eso se prueba inyectando el caso.

    Hoy `es_utilizable` hace imposible un ancla ≤ 0 por el camino público, así que ningún
    dato la produce. Pero si un cambio futuro la dejara pasar, dividir por ella daría un
    precio relativo negativo o infinito **con cara de dato**. Mismo criterio que la guarda
    de anchos fijos de `modelado.seleccion`: el caso es inalcanzable hoy y aun así tiene su
    red, porque lo que lo hace inalcanzable vive en otro módulo.
    """
    transformador = TransformadorDeflacion(catalogo=catalogo).ajustar(datos, corte)
    transformador.ancla_.loc[transformador.ancla_["id_producto"] == 2, "precio_prom_hoy"] = 0.0

    features = construir_features(datos, corte, catalogo=catalogo, transformador=transformador)
    del_producto = features[features["id_producto"] == 2]

    assert del_producto["precio_rel_nivel"].isna().all()
    assert np.isfinite(features["precio_rel_nivel"].dropna()).all()


def test_producto_con_un_solo_mes_de_historia(datos, catalogo, corte):
    extra = _hechos(
        [{"id_producto": 9, "anio_mes": corte, "unidades": 5.0, "revenue": 500.0,
          "precio_prom": 100.0}]
    )
    catalogo_ext = pd.concat(
        [catalogo, pd.DataFrame([{"id_producto": 9, "categoria": "A", "laboratorio": "L1"}])],
        ignore_index=True,
    ).astype({"id_producto": "int64"})

    features = construir_features(
        pd.concat([datos, extra], ignore_index=True), corte, catalogo=catalogo_ext
    )
    del_producto = features[features["id_producto"] == 9]

    assert len(del_producto) == 1
    # Su precio es el del corte, así que es su propia ancla: relativo 1 y sin variación.
    assert del_producto["precio_rel_nivel"].iloc[0] == pytest.approx(1.0)
    assert del_producto["var_precio_rel_3m"].isna().all()


def test_producto_dado_de_baja_usa_el_fallback(datos, catalogo, corte):
    """El producto 3 dejó de vender en el mes 10: sin precio propio reciente, su ancla sale
    de la cascada. Sus features existen igual — es el 25,4% de EDA §4."""
    features = construir_features(datos, corte, catalogo=catalogo)
    del_producto = features[features["id_producto"] == 3]

    assert len(del_producto) == 10
    assert del_producto["precio_rel_nivel"].notna().any()
    assert del_producto["precio_ancla"].notna().all()


# ---------------------------------------------------------------------------------
# Contrato del módulo
# ---------------------------------------------------------------------------------


def test_no_devuelve_filas_posteriores_al_corte(datos, catalogo, cortes):
    features = construir_features(datos, cortes[0], catalogo=catalogo)
    assert features["anio_mes"].max() <= cortes[0]


def test_no_densifica_el_panel(datos, catalogo, corte):
    """La densificación de ADR-010 es del arnés. Hacerla acá también dejaría el criterio de
    calendario en dos lugares, y el producto 3 (que dejó de vender) es el que lo delata."""
    visibles = (datos["anio_mes"] <= corte).sum()
    assert len(construir_features(datos, corte, catalogo=catalogo)) == visibles


def test_el_esquema_es_estable_sin_catalogo(datos, corte):
    """Sin catálogo no hay contraste de nivel ni atributos, pero las columnas están: si el
    esquema dependiera del insumo, M2.3 tendría dos configuraciones de features."""
    features = construir_features(datos, corte, catalogo=None)
    assert list(features.columns) == COLUMNAS_FEATURES
    assert features["precio_rel_nivel"].isna().all()
    assert features["precio_ancla"].notna().any()


def test_un_transformador_de_otro_corte_corta(datos, catalogo, corte):
    """Reusar un transformador ajustado a otro corte es leakage que la red de M1.3 **no
    vería**, porque llegaría contaminado desde afuera. Por eso corta acá."""
    ajeno = TransformadorDeflacion(catalogo=catalogo).ajustar(datos, corte)
    with pytest.raises(ValueError, match="ajustado a"):
        construir_features(datos, corte - pd.DateOffset(months=6), transformador=ajeno)


def test_un_transformador_del_mismo_corte_se_reusa(datos, catalogo, corte):
    ajustado = TransformadorDeflacion(catalogo=catalogo).ajustar(datos, corte)
    reusando = construir_features(datos, corte, catalogo=catalogo, transformador=ajustado)
    de_cero = construir_features(datos, corte, catalogo=catalogo)
    pd.testing.assert_frame_equal(reusando, de_cero)


def test_grano_mas_fino_corta(datos, catalogo, corte):
    """El caso real: pasar los hechos de cliente×producto. Sin la guarda, el merge del
    catálogo multiplica filas y las features salen con cara de válidas."""
    duplicado = pd.concat([datos, datos], ignore_index=True)
    with pytest.raises(ValueError, match="grano más fino"):
        construir_features(duplicado, corte, catalogo=catalogo)


def test_cobertura_de_features_reporta_todas_las_columnas(datos, catalogo, corte):
    cobertura = cobertura_de_features(construir_features(datos, corte, catalogo=catalogo))
    assert set(cobertura["feature"]) == set(COLUMNAS_FEATURES) - {"id_producto", "anio_mes"}
    assert (cobertura["cobertura"] <= 1.0).all()


def test_la_especificacion_cubre_el_mismo_mes_del_anio_anterior():
    """`mismo_mes_año_anterior` no es una feature aparte: a grano mensual es `lag 12`.
    Si alguien saca el 12 de `LAGS`, la estacionalidad anual se pierde sin que nada avise."""
    assert 12 in LAGS


def test_las_estaticas_existen_en_la_salida(datos, catalogo, corte):
    features = construir_features(datos, corte, catalogo=catalogo)
    assert set(STATIC_FEATURES) <= set(features.columns)
    # Estáticas de verdad: un solo valor por serie dentro del corte.
    for columna in STATIC_FEATURES:
        assert (features.groupby("id_producto")[columna].nunique(dropna=False) <= 1).all()
