"""Reporte tabular de backtest (M1.0 (g)) — el entregable de M1.2.

Regla del gate: **ningún número global suelto sin desagregar.** Un WAPE promedio
esconde exactamente lo que hay que ver — que el error a 12 meses no es el de 1 mes,
que una categoría anda mucho peor que el resto, y que las series intermitentes se
comportan distinto de las suaves. Por eso el reporte no devuelve un número: devuelve
un juego de tablas por los cortes que exige `plan-diseno.md` (horizonte 1/3/6/12,
nivel de agregación, categoría, cuadrante de intermitencia).

`a_markdown()` produce el archivo que se congela en `motor/backtests/`. Solo métricas
agregadas, nunca registros — regla de oro de datos del cliente (ADR-006).
"""

import pandas as pd

from .corrida import Corrida
from .metricas import mase, sesgo, wape

HORIZONTES_DE_REPORTE = (1, 3, 6, 12)
"""Los horizontes que se reportan (`plan-diseno.md` §Protocolo). No son todos los
que se predicen: h=1 es el que tiene peso operativo y h=12 el de planificación."""


def _metricas_juntas(
    reporte: pd.DataFrame,
    columnas_grupo: list[str],
    columna_pred: str,
    columnas_nivel: list[str] | None,
) -> pd.DataFrame:
    """WAPE + sesgo en una sola tabla, conservando `n` y `cobertura` una sola vez."""
    w = wape(reporte, columnas_grupo, columna_pred=columna_pred, columnas_nivel=columnas_nivel)
    s = sesgo(reporte, columnas_grupo, columna_pred=columna_pred, columnas_nivel=columnas_nivel)
    if not columnas_grupo:
        return pd.concat([w[["wape", "n", "cobertura"]], s[["sesgo"]]], axis=1)[
            ["wape", "sesgo", "n", "cobertura"]
        ]
    juntas = w.merge(s.drop(columns=["n", "cobertura"]), on=columnas_grupo)
    return juntas[[*columnas_grupo, "wape", "sesgo", "n", "cobertura"]]


def construir_reporte(
    reporte: pd.DataFrame,
    columna_pred: str,
    train_df: pd.DataFrame | None = None,
    columna_categoria: str = "categoria",
    columna_cuadrante: str = "cuadrante",
    horizontes: tuple[int, ...] = HORIZONTES_DE_REPORTE,
) -> dict[str, pd.DataFrame]:
    """Arma el juego de tablas del backtest a partir del reporte de `ejecutar_backtest`.

    Devuelve un dict con, según lo que haya disponible en el reporte:

    - `corrida`: metadatos de trazabilidad (si el reporte trae `.attrs["corrida"]`).
    - `por_horizonte`: WAPE y sesgo a grano producto, para `horizontes`.
    - `por_nivel_y_horizonte`: el mismo corte pero al **nivel** producto / categoría /
      total, que es la lectura que pide ADR-008 y sobre la que se decide el gate de M2.
    - `por_categoria`: solo si el reporte trae `columna_categoria`.
    - `por_cuadrante`: solo si trae `columna_cuadrante`, que pone
      `motor.clasificacion.etiquetar()`. Si falta, la tabla no aparece y su ausencia queda
      escrita en el markdown en vez de pasar desapercibida.
    - `mase_por_horizonte`: solo si se pasa `train_df` (MASE necesita la historia).

    No calcula MAPE: ADR-008 lo deja solo para comunicación en niveles agregados, y
    esta tabla es la de evaluación interna.
    """
    tablas: dict[str, pd.DataFrame] = {}
    corrida = reporte.attrs.get("corrida")
    if isinstance(corrida, Corrida):
        tablas["corrida"] = corrida.como_fila()

    del_horizonte = reporte[reporte["horizonte"].isin(horizontes)]
    if del_horizonte.empty:
        raise ValueError(
            f"El reporte no tiene ninguna fila en los horizontes {horizontes}: "
            f"tiene {sorted(reporte['horizonte'].unique())}"
        )

    tablas["por_horizonte"] = _metricas_juntas(del_horizonte, ["horizonte"], columna_pred, None)

    niveles: list[tuple[str, list[str] | None]] = [("producto", None), ("total", [])]
    if columna_categoria in reporte.columns:
        niveles.insert(1, ("categoria", [columna_categoria]))
    por_nivel = []
    for etiqueta, columnas_nivel in niveles:
        tabla = _metricas_juntas(del_horizonte, ["horizonte"], columna_pred, columnas_nivel)
        por_nivel.append(tabla.assign(nivel=etiqueta))
    tablas["por_nivel_y_horizonte"] = pd.concat(por_nivel, ignore_index=True)[
        ["nivel", "horizonte", "wape", "sesgo", "n", "cobertura"]
    ]

    cortes_extra = ((columna_categoria, "por_categoria"), (columna_cuadrante, "por_cuadrante"))
    for columna, nombre in cortes_extra:
        if columna in reporte.columns:
            tablas[nombre] = _metricas_juntas(
                del_horizonte, [columna, "horizonte"], columna_pred, None
            )

    if train_df is not None:
        por_serie = mase(reporte, modelos=[columna_pred], train_df=train_df)
        tablas["mase_por_horizonte"] = (
            reporte.merge(por_serie, on=["id_producto", "corte"], suffixes=("", "_mase"))
            .groupby("horizonte", observed=True)[f"{columna_pred}_mase"]
            .agg(mase_medio="mean", mase_mediana="median", n="size")
            .reset_index()
            .query("horizonte in @horizontes")
        )

    return tablas


def _tabla_markdown(df: pd.DataFrame, decimales: int = 4) -> str:
    """Markdown de una tabla, sin depender de `tabulate`.

    Formatea a mano a propósito: estas tablas se **congelan** en `motor/backtests/` y
    se comparan entre corridas, así que la cantidad de decimales tiene que ser estable
    (un `repr` de float por defecto haría diffs ruidosos entre corridas equivalentes).
    """

    def celda(valor) -> str:
        if isinstance(valor, float):
            return "—" if pd.isna(valor) else f"{valor:.{decimales}f}"
        return "—" if valor is None or pd.isna(valor) else str(valor)

    encabezado = "| " + " | ".join(str(c) for c in df.columns) + " |"
    separador = "|" + "|".join("---" for _ in df.columns) + "|"
    filas = [
        "| " + " | ".join(celda(v) for v in fila) + " |"
        for fila in df.itertuples(index=False, name=None)
    ]
    return "\n".join([encabezado, separador, *filas])


def a_markdown(tablas: dict[str, pd.DataFrame], titulo: str, notas: str = "") -> str:
    """Serializa el juego de tablas al formato de `motor/backtests/`.

    Solo métricas agregadas (ADR-006): conteos, ratios y porcentajes. Ninguna tabla de
    acá contiene registros, nombres de cliente ni precios, así que es publicable al
    repo incluso cuando la corrida fue sobre datos reales del cliente.
    """
    partes = [f"# {titulo}", ""]
    if notas:
        partes += [notas, ""]

    if "corrida" not in tablas:
        partes += [
            "> ⚠️ Reporte **sin identificador de corrida**: se armó desde un reporte que "
            "perdió `.attrs` (pandas lo descarta en varias operaciones). No es "
            "congelable como referencia — volvé a generarlo tomando los metadatos "
            "antes de transformar el reporte.",
            "",
        ]
    if "por_cuadrante" not in tablas:
        partes += [
            "> Sin desagregado **por cuadrante de intermitencia**: falta la columna "
            "`cuadrante`. Agregala con `motor.clasificacion.etiquetar()` antes de armar "
            "las tablas. El gate de M1.2 la exige, así que este reporte no lo cumple del "
            "todo y no es congelable como referencia.",
            "",
        ]

    orden = [
        ("corrida", "Corrida"),
        ("ganadores_por_cuadrante", "Modelo ganador por cuadrante (selección por serie, M1.7)"),
        ("por_nivel_y_horizonte", "Por nivel de agregación y horizonte"),
        ("por_horizonte", "Por horizonte (grano producto)"),
        ("por_categoria", "Por categoría y horizonte"),
        ("por_cuadrante", "Por cuadrante de intermitencia y horizonte"),
        ("mase_por_horizonte", "MASE por horizonte"),
    ]
    for clave, encabezado in orden:
        if clave in tablas:
            partes += [f"## {encabezado}", "", _tabla_markdown(tablas[clave]), ""]

    # Una tabla con clave desconocida se renderiza igual al final, en vez de
    # desaparecer: quien la agregó al dict la quiere en el archivo, y una tabla que se
    # descarta en silencio es justo el tipo de "salió bien" engañoso contra el que este
    # módulo existe. Para darle título y posición propios, agregala a `orden`.
    for clave in tablas:
        if clave not in {c for c, _ in orden}:
            partes += [f"## {clave}", "", _tabla_markdown(tablas[clave]), ""]
    return "\n".join(partes)
