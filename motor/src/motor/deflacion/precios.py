"""Precio implícito utilizable y relativos mensuales — la puerta de entrada de la deflación.

Si acá pasa basura, contamina todo lo de abajo: el índice de un nivel es una media
*geométrica*, así que un solo precio absurdo mueve a todos los productos que dependen de
ese nivel, y como el índice es encadenado el error no se diluye — se arrastra.

## Qué precio es utilizable

`precio_prom` viene de la ingesta como `revenue / unidades` (ADR-001), y medido sobre el
extract real (§5.5 #6) llega en tres estados:

| estado | filas reales | por qué |
|---|---|---|
| utilizable | 132.529 (96,46%) | — |
| `NaN` | 4.848 (3,53%) | `unidades == 0`: mes de neto cero, no hay precio observado |
| `<= 0` | 22 (0,016%) | netean por separado: una NC a otro precio cruza los signos |

Las 22 son el 0,016%, pero **un ancla negativa propagada por la cascada contamina mucho
más que 22 filas**. `es_utilizable` las descarta junto con los infinitos, que hoy no
existen porque el extract divide con `.where(unidades != 0)` — pero eso es una propiedad
de un script, no del contrato, y acá no cuesta nada cubrirlo.

## Por qué muestra apareada

Para el relativo de un mes se exigen **dos meses calendario consecutivos, ambos
utilizables** del mismo producto. Es el método clásico de muestra apareada, y la razón de
no interpolar sobre huecos es que un producto intermitente que reaparece a los 8 meses no
tiene un "cambio de precio mensual": tiene un salto de 8 meses que, repartido, inventaría
información que nadie observó.

El costo es bajo y está medido: **125.078 pares, el 94,4% de las filas utilizables**, con
una mediana de 1.360 pares por mes y un mínimo de 1.015.
"""

import numpy as np
import pandas as pd

COLUMNAS_RELATIVOS = ("id_producto", "anio_mes", "relativo", "peso")


def es_utilizable(precio: pd.Series) -> pd.Series:
    """Máscara de precios que pueden entrar al cálculo del índice.

    `np.isfinite` cubre `NaN` e infinitos de una sola vez; `> 0` saca los negativos y los
    ceros. Un cero no es "gratis": es la ausencia de precio, y ADR-010 §4 ya obliga a que
    la densificación deje `precio_prom` nulo y nunca en cero por este mismo motivo.
    """
    return np.isfinite(precio) & (precio > 0)


def _ordinal_mensual(fecha: pd.Series) -> pd.Series:
    """Mes como entero corrido, para preguntar "¿son consecutivos?" sin aritmética de fechas."""
    return fecha.dt.year * 12 + fecha.dt.month


def relativos_apareados(hechos: pd.DataFrame) -> pd.DataFrame:
    """Relativo `P_t / P_{t-1}` por producto, solo entre meses consecutivos utilizables.

    No filtra por corte: recortar es responsabilidad de quien llama, y se hace **una sola
    vez arriba de todo** (`TransformadorDeflacion.ajustar`) para que no haya dos lugares
    donde el filtro temporal pueda quedar mal puesto.

    Args:
        hechos: `hecho_venta_mensual_producto` (`id_producto`, `anio_mes`, `precio_prom`,
            `revenue`).

    Returns:
        Un DataFrame con `COLUMNAS_RELATIVOS`, donde `peso` es el revenue promedio de los
        dos meses del par. Ponderar por revenue es lo que hace que el índice represente
        lo que la distribuidora efectivamente vende, y no que un producto de $20 pese lo
        mismo que uno de $20.000. Se promedian los dos meses, y no se toma uno, porque
        usar solo el mes actual le daría todo el peso a un mes con una venta excepcional.
    """
    usable = hechos[es_utilizable(hechos["precio_prom"])]
    usable = usable.sort_values(["id_producto", "anio_mes"])

    por_producto = usable.groupby("id_producto", sort=False)
    precio_previo = por_producto["precio_prom"].shift(1)
    revenue_previo = por_producto["revenue"].shift(1)
    mes_previo = por_producto["anio_mes"].shift(1)

    consecutivos = _ordinal_mensual(usable["anio_mes"]) - _ordinal_mensual(mes_previo) == 1

    pares = usable[consecutivos]
    return pd.DataFrame(
        {
            "id_producto": pares["id_producto"].to_numpy(),
            "anio_mes": pares["anio_mes"].to_numpy(),
            "relativo": (pares["precio_prom"] / precio_previo[consecutivos]).to_numpy(),
            "peso": ((pares["revenue"] + revenue_previo[consecutivos]) / 2).to_numpy(),
        }
    )


def ultimo_precio_utilizable(hechos: pd.DataFrame) -> pd.DataFrame:
    """Último precio utilizable de cada producto: el punto desde el que la cascada traslada.

    Un producto sin ancla propia no hereda el *precio* de su categoría —sería absurdo con
    la dispersión que hay adentro de una— sino su *movimiento*, aplicado sobre este
    precio. Conserva su nivel, toma prestada la deriva.

    Returns:
        `id_producto`, `anio_mes`, `precio_prom` — una fila por producto con al menos un
        precio utilizable. Los productos que nunca tuvieron uno no aparecen: no hay nada
        desde donde trasladar, y su deflactor va a quedar nulo a propósito.
    """
    usable = hechos[es_utilizable(hechos["precio_prom"])]
    ultimo = usable.sort_values("anio_mes").groupby("id_producto", as_index=False).last()
    return ultimo[["id_producto", "anio_mes", "precio_prom"]]
