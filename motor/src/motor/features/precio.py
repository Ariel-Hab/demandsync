"""Features de precio real (M2.2) — el precio del producto contra el de su vecindario.

## Por qué no es "el precio deflactado"

`plan-diseno.md` §M2 pedía "precio real deflactado y su variación". Tomado literal a grano
producto **es una columna constante y otra de ceros**, y es por construcción, no por un
error de datos: el deflactor de ADR-002 es `d = ancla / P̂`, y cuando el mes tiene precio
propio utilizable `P̂ = precio_prom`, así que

```
precio_prom_t × d_t = precio_prom_t × (ancla / precio_prom_t) = ancla
```

Medido sobre el extract real (`C:/dfv-extract-v2`, corte 2025-05): la igualdad se cumple en
el **99,15%** de las filas con precio propio utilizable, y el CV intra-producto de esa
columna da **0,0000** contra 1,2809 del precio nominal. Deflactar el precio de un producto
con su propio deflactor devuelve el ancla porque el deflactor **se construyó a partir de
ese precio**: es una identidad, no una medición.

Lo mismo vale para los montos: `revenue_real = revenue × d = unidades × ancla` (99,13% de
las filas), o sea el target reescalado por una constante por serie. Ninguna de las dos
entra como feature. Ver **ADR-013**.

## Qué sí tiene señal

El precio del producto llevado a pesos del corte **con el índice de su nivel** y no con el
suyo propio, relativo a su ancla:

```
precio_rel_nivel_t = precio_prom_t × I_nivel(corte)/I_nivel(t) / ancla
```

Es adimensional, no arrastra inflación (numerador y denominador la llevan igual) y es
justamente el precio relativo del que depende la elasticidad.

**Lo que la feature dice es la forma de la serie, no su nivel.** El nivel lleva una
constante por producto, porque el ancla es el promedio ponderado de los últimos 3 meses y
no el precio del corte: en una serie que crece al 5% mensual esa constante vale ≈1,05. Así
que "vale 1" es aproximado. Lo exacto —y lo que entrena— es:

- un producto que se movió **igual que su categoría** tiene la serie **plana**, y variación
  exactamente cero;
- uno que se **encareció** contra ella la tiene **creciente**, porque en el pasado estaba
  relativamente más barato de lo que está hoy. El signo se lee al revés de lo que sugiere
  la intuición, y por eso está fijado en un test.

Las columnas de variación son cocientes de la misma serie, así que la constante se cancela
y son escala-libres de punta a punta.

Medido sobre el mismo extract: CV intra-producto **0,1511** (p25 0,1056, p90 0,5098) sobre
1.680 productos con ≥12 meses, cobertura **98,99%** de las filas con precio propio, y la
variación a 3 meses reparte entre −0,216 (p5) y +0,237 (p95), sin una sola fila en cero.

## El contraste es contra categoría/laboratorio, nunca contra el IPC

Mismo criterio que `LIMITE_DESVIO_NIVEL` en `deflacion.transformador`: categoría y
laboratorio se construyen con los relativos de los propios productos del cliente, así que
despegarse de ellos es señal; el IPC es un índice macro externo que no tiene ninguna
obligación de seguir precios veterinarios, y despegarse de él no prueba nada. Por eso se usa
`factor_de_nivel`, cuyo default es `NIVELES_CONTRASTE`.
"""

import numpy as np
import pandas as pd

from motor.deflacion.precios import es_utilizable

MESES_VARIACION = (3, 12)
"""Ventanas de la variación del precio relativo, en meses calendario.

3 y 12 para que haya una de reacción corta y una interanual, alineadas con las ventanas de
media móvil de `especificacion.VENTANAS_MEDIA_MOVIL`.
"""


def _alinear_calendario(tabla: pd.DataFrame, columna: str, meses: int) -> pd.Series:
    """El valor de `columna` `meses` **calendario** atrás, no `meses` filas atrás.

    La distinción importa porque el panel puede venir disperso: en una serie intermitente,
    tres filas hacia atrás pueden ser ocho meses. Un `shift(3)` mediría "el precio de la
    antepenúltima vez que vendió", que no es una variación trimestral de nada.
    """
    previo = tabla[["id_producto", "anio_mes", columna]].copy()
    previo["anio_mes"] = (previo["anio_mes"].dt.to_period("M") + meses).dt.to_timestamp()
    previo = previo.rename(columns={columna: "_previo"})

    unido = tabla[["id_producto", "anio_mes"]].merge(
        previo, on=["id_producto", "anio_mes"], how="left"
    )
    return unido["_previo"]


def precio_relativo_al_nivel(visible: pd.DataFrame, transformador) -> pd.DataFrame:
    """`precio_rel_nivel` y sus variaciones, por (producto, mes) de `visible`.

    Args:
        visible: hechos **ya recortados al corte**. Esta función no filtra por fecha: el
            recorte se hace una sola vez, arriba, en `construir_features`.
        transformador: un `TransformadorDeflacion` ya ajustado al corte. Se le piden el
            ancla y el factor de nivel, que son las dos piezas que M2.1 dejó bajo test.

    Returns:
        `id_producto`, `anio_mes`, `precio_rel_nivel`, `var_precio_rel_3m`,
        `var_precio_rel_12m` — una fila por fila de `visible`, en su mismo orden.

    Las filas sin precio propio utilizable, o cuyo nivel no pudo responder (el 1,4% sin
    categoría ni laboratorio), quedan en `NaN` y **no se descartan**: la cobertura tiene que
    ser visible, no silenciosa. LightGBM maneja `NaN` nativamente, así que no se imputa —
    imputar acá inventaría un precio que nadie observó.
    """
    base = visible[["id_producto", "anio_mes", "precio_prom"]].reset_index(drop=True)

    factor, _nivel = transformador.factor_de_nivel(
        pd.DataFrame(
            {
                "id_producto": base["id_producto"],
                "mes_desde": base["anio_mes"],
                "mes_hasta": transformador.corte_,
            }
        )
    )

    ancla = transformador.ancla_.set_index("id_producto")["precio_prom_hoy"]
    ancla = ancla.reindex(base["id_producto"]).to_numpy()

    with np.errstate(divide="ignore", invalid="ignore"):
        relativo = base["precio_prom"].to_numpy() * factor.to_numpy() / ancla
    # Un ancla <= 0 no debería existir (`es_utilizable` la filtra aguas arriba), pero si
    # llegara, dividir por ella daría un precio relativo negativo que parece un dato.
    relativo = np.where(np.isfinite(ancla) & (ancla > 0), relativo, np.nan)

    salida = base[["id_producto", "anio_mes"]].copy()
    salida["precio_rel_nivel"] = pd.Series(relativo).where(es_utilizable(base["precio_prom"]))

    for meses in MESES_VARIACION:
        previo = _alinear_calendario(salida, "precio_rel_nivel", meses)
        salida[f"var_precio_rel_{meses}m"] = salida["precio_rel_nivel"] / previo - 1.0

    return salida
