"""`construir_features` — el punto de entrada único de M2.2.

Devuelve un panel a grano (`id_producto`, `anio_mes ≤ corte`): **una fila por mes visible**,
no una foto del corte. Cada fila es un **origen de pronóstico válido** — M2.3 usa las de
`anio_mes == corte` para predecir y las anteriores como orígenes de entrenamiento.

Esa forma es lo que hace que la feature de precio aporte señal temporal sin necesitar
ningún valor futuro: el precio de `corte+h` no se conoce, pero el del origen sí, y es el
que describe "este producto viene de encarecerse contra su categoría".

## Anti-leakage

El recorte al corte se hace **una sola vez, en la primera línea de esta función**, y todo
lo de abajo es puro: ni `precio.py` ni el merge del catálogo vuelven a mirar fechas.
(`TransformadorDeflacion.ajustar` repite su propio recorte, que sobre datos ya recortados
es un no-op — se le pasa `visible` justamente para que este módulo tenga un solo lugar
donde el filtro temporal puede quedar mal puesto.)

La red que lo verifica es `motor.backtesting.leakage.verificar_sin_leakage`, escrita en
M1.3 antes que esto, y es el **gate de salida de M2.2**.
"""

import pandas as pd

from motor.deflacion.transformador import TransformadorDeflacion
from motor.features.especificacion import COLUMNAS_CATALOGO, COLUMNAS_PRECIO
from motor.features.precio import precio_relativo_al_nivel

COLUMNAS_CLAVE = ["id_producto", "anio_mes"]

COLUMNAS_FEATURES = COLUMNAS_CLAVE + COLUMNAS_PRECIO + COLUMNAS_CATALOGO
"""Esquema de salida, estable: las columnas están siempre, aunque falte el catálogo."""


def _validar_grano(datos: pd.DataFrame) -> None:
    """Corta si hay más de una fila por producto-mes.

    Mismo motivo que la guarda del arnés: con grano más fino, el merge del catálogo y el
    alineado por calendario multiplican filas en silencio y las features salen con cara de
    válidas. Caso concreto: pasar `hecho_venta_mensual_cliente_producto` por error.
    """
    duplicadas = datos.duplicated(subset=COLUMNAS_CLAVE, keep=False)
    if duplicadas.any():
        ejemplo = datos.loc[duplicadas, COLUMNAS_CLAVE].iloc[0].to_dict()
        raise ValueError(
            f"`historia` tiene grano más fino que {COLUMNAS_CLAVE}: "
            f"{int(duplicadas.sum())} filas duplicadas (ej. {ejemplo}). Las features son a "
            "grano producto-mes; si son hechos de cliente×producto, agregalos antes."
        )


def construir_features(
    historia: pd.DataFrame,
    corte: pd.Timestamp,
    catalogo: pd.DataFrame | None = None,
    transformador: TransformadorDeflacion | None = None,
) -> pd.DataFrame:
    """Construye las features de M2.2 para el corte dado.

    Args:
        historia: `hecho_venta_mensual_producto`. Puede traer meses posteriores al corte:
            se recortan acá. **No se densifica**: eso es de ADR-010 y ya lo hace el arnés
            antes de invocar al predictor, así que hacerlo de nuevo sería duplicar el
            criterio de calendario en dos lugares.
        corte: el "hoy" de esta corrida. En backtest, el hoy de *ese* corte.
        catalogo: `catalogo_producto`. Sin él no hay `categoria`/`laboratorio` **y tampoco
            hay contraste de nivel**, así que `precio_rel_nivel` queda todo nulo: las
            columnas salen igual, en `NaN`, para que el esquema no dependa del insumo.
        transformador: uno ya ajustado a `corte`, para no re-ajustar la deflación en cada
            llamada (M2.3 corre 18 cortes). Si el corte no coincide, **corta**: reusar uno
            ajustado a otro corte es leakage silencioso y la red de M1.3 no lo vería,
            porque el transformador llegaría contaminado desde afuera.

    Returns:
        `COLUMNAS_FEATURES`, ordenado por producto y mes.
    """
    corte = pd.Timestamp(corte).normalize().replace(day=1)
    visible = historia[historia["anio_mes"] <= corte]
    _validar_grano(visible)

    if transformador is None:
        transformador = TransformadorDeflacion(catalogo=catalogo).ajustar(visible, corte)
    elif transformador.corte_ != corte:
        raise ValueError(
            f"El transformador está ajustado a {transformador.corte_.date()} y las features "
            f"se piden para {corte.date()}: el ancla y los índices serían de otro 'hoy'. "
            "Ajustalo a este corte o pasá transformador=None."
        )

    features = precio_relativo_al_nivel(visible, transformador)

    ancla = transformador.ancla_.rename(columns={"precio_prom_hoy": "precio_ancla"})
    features = features.merge(ancla[["id_producto", "precio_ancla"]], on="id_producto", how="left")

    if catalogo is not None:
        disponibles = [c for c in COLUMNAS_CATALOGO if c in catalogo.columns]
        features = features.merge(
            catalogo[["id_producto", *disponibles]].drop_duplicates("id_producto"),
            on="id_producto",
            how="left",
        )
    for columna in COLUMNAS_FEATURES:
        if columna not in features.columns:
            features[columna] = pd.Series(pd.NA, index=features.index, dtype="object")

    return (
        features[COLUMNAS_FEATURES]
        .sort_values(COLUMNAS_CLAVE)
        .reset_index(drop=True)
    )


def cobertura_de_features(features: pd.DataFrame) -> pd.DataFrame:
    """Qué fracción de las filas tiene valor en cada feature.

    Existe por la misma razón que la columna `cobertura` de las métricas: una feature que
    llega nula en la mitad del panel no falla, entrena peor. Que el número esté a mano hace
    que se mire.
    """
    columnas = [c for c in features.columns if c not in COLUMNAS_CLAVE]
    return pd.DataFrame(
        {
            "feature": columnas,
            "n": [int(features[c].notna().sum()) for c in columnas],
            "cobertura": [float(features[c].notna().mean()) for c in columnas],
        }
    )
