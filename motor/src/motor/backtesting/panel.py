"""Densificación del calendario (ADR-010) — el paso previo a medir y a modelar.

Las tablas de hechos son **dispersas**: un producto-mes sin venta no tiene fila. Eso
es correcto para una tabla de hechos (no se persisten no-eventos) pero no para el
consumo analítico: un pronóstico se evalúa mes a mes, exista o no la fila. Sin ceros
explícitos, **sobre-pronosticar donde la demanda fue cero es invisible** — el error
dominante en un portafolio intermitente.

Regla de ADR-010: de la primera venta de cada serie al último mes del período; se
rellenan con cero solo las columnas de cantidad; el precio queda nulo.
"""

import pandas as pd


def densificar(
    datos: pd.DataFrame,
    columnas_id: list[str] | None = None,
    columna_fecha: str = "anio_mes",
    columnas_cero: list[str] | None = None,
    hasta: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Devuelve el panel mensual denso de `datos`, según ADR-010.

    Args:
        columnas_id: las que identifican la serie. Por defecto `["id_producto"]`.
        columnas_cero: columnas de **cantidad** a rellenar con 0 en los meses sin
            venta. Por defecto `["unidades"]`. **Nunca incluir `precio_prom`**: en un
            mes sin venta no hay precio observado, y un cero contaminaría el índice
            implícito de la deflación (ADR-002). Las columnas que no estén listadas
            quedan nulas, que es lo correcto para un no-evento.
        hasta: último mes del panel. Por defecto, el último mes presente en `datos`
            — se rellenan los ceros de cola aunque la serie haya dejado de vender
            (detectar obsolescencia es el objetivo, no un efecto colateral).

    El inicio es **por serie**: el primer mes con venta de cada una. Un producto que
    entró al catálogo en 2023 no tuvo demanda cero en 2019.

    Nota de escala: el panel se arma con un producto cartesiano series × meses. A
    nivel producto (~2.300 × 96) es trivial; a nivel cliente×producto (~319k pares)
    son ~30M de filas, así que ahí hay que densificar por ventana de evaluación y no
    el histórico completo (ADR-010, consecuencias).
    """
    columnas_id = list(columnas_id) if columnas_id else ["id_producto"]
    columnas_cero = list(columnas_cero) if columnas_cero else ["unidades"]

    if datos.empty:
        return datos.copy()

    ultimo_mes = pd.Timestamp(hasta) if hasta is not None else datos[columna_fecha].max()
    primer_mes_por_serie = (
        datos.groupby(columnas_id, observed=True)[columna_fecha]
        .min()
        .rename("_desde")
        .reset_index()
    )
    calendario = pd.DataFrame(
        {columna_fecha: pd.date_range(datos[columna_fecha].min(), ultimo_mes, freq="MS")}
    )

    grilla = primer_mes_por_serie.merge(calendario, how="cross")
    grilla = grilla[grilla[columna_fecha] >= grilla["_desde"]].drop(columns="_desde")

    denso = grilla.merge(datos, on=columnas_id + [columna_fecha], how="left")
    for columna in columnas_cero:
        if columna in denso.columns:
            denso[columna] = denso[columna].fillna(0.0)

    return denso.sort_values(columnas_id + [columna_fecha]).reset_index(drop=True)
