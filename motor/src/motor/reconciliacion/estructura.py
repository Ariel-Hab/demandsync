"""La estructura agrupada `total → {categoría, laboratorio} → producto` y su matriz `S`.

**Es agrupada, no jerárquica, y eso se midió (§7.2):** 47 de 77 laboratorios venden en más de
una categoría y cubren 1.889 de 2.128 productos. Un laboratorio **no** está anidado en una
categoría; son dos dimensiones que se cruzan sobre el mismo nivel base.

La distinción no es académica. Codificarlo como árbol `total → categoría → laboratorio →
producto` **no falla**: produce una `S` que afirma que cada laboratorio pertenece a una sola
categoría y después reconcilia contra restricciones que no existen, con números
perfectamente plausibles. Es el mismo modo de falla que el mes incompleto de §5.5.1.

Los cinco niveles y sus tamaños en el universo real (2.128 productos):

| nivel | series |
|---|---|
| `total` | 1 |
| `categoria` | 12 |
| `laboratorio` | 77 |
| `categoria_laboratorio` | 206 |
| `producto` | 2.128 |

**Gotcha de `hierarchicalforecast`, y no es el bug de §5.5 al revés.** `aggregate` exige que
**todas** las columnas de agrupación sean `str`, así que `id_producto` se castea. Eso es
seguro: el peligro de §5.5 era `str → int`, que es muchos-a-uno (`'2'`, `'02'` y `'0002'`
colapsan); acá vamos `int → str`, que es inyectivo y no puede fusionar dos productos.

**El otro gotcha sí puede fusionar series y por eso corta:** `aggregate` arma el
`unique_id` pegando los niveles con `/` y **reemplaza por `_` cualquier `/` que venga en un
valor**. Dos categorías que difieran solo en ese carácter quedarían con el mismo id, sumadas
en silencio. `construir_estructura` lo verifica antes de llamar a la librería.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from hierarchicalforecast.utils import aggregate

from ..backtesting.panel import densificar

COLUMNA_TOTAL = "total"
"""Columna constante que hace de raíz. `hierarchicalforecast` no agrega el total solo: se
consigue poniendo un nivel con un único valor, que es la convención de la librería."""

ESPECIFICACION: list[list[str]] = [
    [COLUMNA_TOTAL],
    [COLUMNA_TOTAL, "categoria"],
    [COLUMNA_TOTAL, "laboratorio"],
    [COLUMNA_TOTAL, "categoria", "laboratorio"],
    [COLUMNA_TOTAL, "categoria", "laboratorio", "id_producto"],
]
"""Las dos dimensiones aparecen **por separado** (`total/categoria` y `total/laboratorio`) y
además cruzadas. Sacar cualquiera de las dos filas del medio convierte esto en un árbol y
vuelve a afirmar un anidamiento que no existe."""

NOMBRE_DE_NIVEL = {
    COLUMNA_TOTAL: "total",
    f"{COLUMNA_TOTAL}/categoria": "categoria",
    f"{COLUMNA_TOTAL}/laboratorio": "laboratorio",
    f"{COLUMNA_TOTAL}/categoria/laboratorio": "categoria_laboratorio",
    f"{COLUMNA_TOTAL}/categoria/laboratorio/id_producto": "producto",
}

NIVELES = tuple(NOMBRE_DE_NIVEL.values())


@dataclass(frozen=True)
class Estructura:
    """La estructura agrupada lista para reconciliar.

    `Y_df` viene en el formato de `hierarchicalforecast` (índice `unique_id`, columnas `ds` e
    `y`); `S` es la matriz de agregación (todas las series × series base) y `niveles` mapea
    cada `unique_id` a su nivel legible, que es lo que después permite reportar la ganancia
    **por nivel** como pide el gate.
    """

    Y_df: pd.DataFrame
    S: pd.DataFrame
    tags: dict[str, np.ndarray]
    niveles: pd.Series

    @property
    def series_base(self) -> list[str]:
        """Los `unique_id` del nivel producto — las columnas de `S`."""
        return list(self.S.columns)

    def __len__(self) -> int:
        return len(self.S)


def _validar_catalogo(catalogo: pd.DataFrame, columna_id: str) -> pd.DataFrame:
    faltantes = sorted({"categoria", "laboratorio"} - set(catalogo.columns))
    if faltantes:
        raise ValueError(
            f"El catálogo no tiene {faltantes}. La estructura agrupada de §7.2 necesita las "
            "dos dimensiones; con una sola sería el árbol que los datos no soportan."
        )

    unico = catalogo[[columna_id, "categoria", "laboratorio"]].drop_duplicates()
    duplicados = unico[unico.duplicated(columna_id, keep=False)]
    if not duplicados.empty:
        cuantos = duplicados[columna_id].nunique()
        raise ValueError(
            f"{cuantos} productos tienen más de un par (categoria, laboratorio). Un producto "
            "tiene que ser hoja de exactamente un grupo o la matriz `S` lo contaría dos "
            f"veces. Ejemplo: {duplicados.head(4).to_dict('records')}"
        )

    nulos = unico[unico[["categoria", "laboratorio"]].isna().any(axis=1)]
    if not nulos.empty:
        raise ValueError(
            f"{len(nulos)} productos tienen categoria o laboratorio nulos. `aggregate` los "
            "agruparía bajo la etiqueta 'nan' sin avisar; si son un grupo real, etiquetalos "
            "explícitamente (como `SIN CATEGORIA`, que sí es un valor del ERP)."
        )
    return unico


def _validar_sin_barras(unico: pd.DataFrame, columnas: list[str]) -> None:
    """`aggregate` reemplaza `/` por `_` al armar el `unique_id`: dos etiquetas que difieran
    solo en ese carácter se fusionarían en una sola serie, sumadas y sin aviso."""
    for columna in columnas:
        valores = unico[columna].astype(str)
        con_barra = sorted(set(valores[valores.str.contains("/", regex=False)]))
        if not con_barra:
            continue
        normalizados = {v.replace("/", "_") for v in valores}
        if len(normalizados) < valores.nunique():
            raise ValueError(
                f"La columna '{columna}' tiene etiquetas que colapsan al reemplazar '/' por "
                f"'_': {con_barra[:4]}. `aggregate` las fusionaría en una sola serie."
            )


def construir_estructura(
    hechos: pd.DataFrame,
    catalogo: pd.DataFrame,
    columna_id: str = "id_producto",
    columna_fecha: str = "anio_mes",
    columna_objetivo: str = "unidades",
    hasta: pd.Timestamp | None = None,
) -> Estructura:
    """Arma la estructura agrupada a partir de los hechos mensuales y el catálogo.

    **Densifica antes de agregar (ADR-010).** El extract es disperso —un producto-mes sin
    venta no tiene fila, densidad 72,8% (§5.1)— y agregar sobre eso deja a los grupos chicos
    sin las filas de los meses en que ninguno de sus productos vendió. Un laboratorio de 3
    productos tendría huecos que el total no tiene, y la matriz `S` dejaría de cerrar
    exactamente en esos meses: la incoherencia parecería del método de reconciliación cuando
    en realidad es del panel. Es la misma trampa que §12.0 documenta para el diagnóstico
    dentro-vs-fuera: **antes de interpretar, verificá que las muestras sean comparables.**

    `hasta` recorta el panel al corte cuando se construye dentro de un backtest.
    """
    unico = _validar_catalogo(catalogo, columna_id)
    _validar_sin_barras(unico, ["categoria", "laboratorio"])

    denso = densificar(
        hechos,
        columnas_id=[columna_id],
        columna_fecha=columna_fecha,
        columnas_cero=[columna_objetivo],
        hasta=hasta,
    )
    con_grupos = denso.merge(unico, on=columna_id, how="left")

    sin_catalogo = con_grupos["categoria"].isna()
    if sin_catalogo.any():
        productos = sorted(con_grupos.loc[sin_catalogo, columna_id].unique())
        raise ValueError(
            f"{len(productos)} productos de los hechos no están en el catálogo "
            f"(ej. {productos[:5]}). Sin grupo no se pueden colgar del árbol, y dejarlos "
            "afuera cambiaría el total en silencio."
        )

    largo = pd.DataFrame(
        {
            COLUMNA_TOTAL: COLUMNA_TOTAL,
            # `int -> str` es inyectivo; el peligro de §5.5 era el sentido contrario.
            "categoria": con_grupos["categoria"].astype(str),
            "laboratorio": con_grupos["laboratorio"].astype(str),
            columna_id: con_grupos[columna_id].astype(str),
            "ds": con_grupos[columna_fecha],
            "y": con_grupos[columna_objetivo].astype(float),
        }
    )

    Y_df, S, tags = aggregate(largo, ESPECIFICACION)
    niveles = pd.Series(
        {
            serie: NOMBRE_DE_NIVEL[etiqueta]
            for etiqueta, series in tags.items()
            for serie in series
        },
        name="nivel",
    )
    niveles.index.name = "unique_id"

    estructura = Estructura(Y_df=Y_df, S=S, tags=tags, niveles=niveles)
    verificar_coherencia(Y_df.reset_index(), estructura, columna_valor="y")
    return estructura


def verificar_coherencia(
    valores: pd.DataFrame,
    estructura: Estructura,
    columna_valor: str,
    columna_serie: str = "unique_id",
    columna_fecha: str = "ds",
    rtol: float = 1e-4,
    atol: float = 1e-6,
) -> pd.DataFrame:
    """`S · base` reproduce los niveles agregados. Devuelve las filas que **no** cierran.

    Es el punto 1 del gate de M3.1 y se verifica sin backtest: la coherencia es una propiedad
    algebraica de la salida, no algo que haya que creerle al método. Sobre los reales tiene
    que dar vacío por construcción —es la red contra un armado mal hecho—; sobre los
    pronósticos **reconciliados** es la verificación de que la reconciliación hizo su trabajo.

    Corre en la corrida además de en los tests a propósito: es barata y ataja el caso en que
    la estructura se arma bien con un fixture de 4 productos y mal con 2.128.

    **La tolerancia es relativa, y eso no es cosmético.** `hierarchicalforecast` castea `S` a
    `float32` (`core.py:267`), así que la salida reconciliada arrastra esa precisión: sobre
    valores de 136 el desvío numérico ya es de 4e-6. Con una tolerancia **absoluta** de 1e-6
    esto pasa en un fixture chico y marca **todo** como incoherente a escala real, donde las
    unidades están en miles — un falso positivo que haría abandonar un método sano. Un error
    estructural, en cambio, es de orden 1 **relativo** y `rtol=1e-4` lo caza igual.
    """
    # `fill_value=0` y no NaN: una celda ausente en el panel base es una serie que todavía
    # no existía, y `aggregate` la trata igual — no suma nada. Con NaN el producto `S · base`
    # daría NaN, la comparación `> tolerancia` sería `False` y **la incoherencia pasaría sin
    # marcarse**, que es peor que no verificar: da una falsa señal de que cierra.
    ancho = valores.pivot_table(
        index=columna_fecha,
        columns=columna_serie,
        values=columna_valor,
        aggfunc="sum",
        fill_value=0,
    )
    faltantes = sorted(set(estructura.S.index) - set(ancho.columns))
    if faltantes:
        raise ValueError(
            f"Faltan {len(faltantes)} series en `valores` (ej. {faltantes[:4]}). La "
            "coherencia no se puede verificar sobre una tabla incompleta."
        )

    base = ancho[estructura.series_base].to_numpy(dtype=float)
    esperado = base @ estructura.S.to_numpy(dtype=float).T
    observado = ancho[list(estructura.S.index)].to_numpy(dtype=float)

    desvio = np.abs(esperado - observado)
    filas, columnas = np.nonzero(~np.isclose(esperado, observado, rtol=rtol, atol=atol))
    return pd.DataFrame(
        {
            columna_fecha: ancho.index.to_numpy()[filas],
            columna_serie: np.asarray(estructura.S.index)[columnas],
            "esperado": esperado[filas, columnas],
            "observado": observado[filas, columnas],
            "desvio": desvio[filas, columnas],
        }
    )
