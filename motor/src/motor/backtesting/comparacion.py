"""Comparación cabeza a cabeza entre predictores, **por serie** (M2.5).

`reporte.py` responde "¿cuánto error tiene este predictor?" agregando por nivel. M2.5
pregunta otra cosa: **¿en qué series gana cada uno?** Un agregado mejor puede convivir con
un montón de series donde el baseline gana —§6.5 ya avisó que las hay, con el `producto
h=12` perdiendo contra el piso— y el criterio de promoción de `plan-diseno.md` §M2 es
explícitamente por serie: *"el global ML reemplaza al baseline solo en las series/niveles
donde le gana en backtest"*.

Las tres lecturas de acá, y para qué sirve cada una:

- `wape_por_serie` — el insumo: WAPE de cada candidato en cada `(serie, horizonte)`.
- `cabeza_a_cabeza` — el veredicto agregado de varios contendientes en una sola tabla,
  a igual cobertura.
- `distribucion_de_mejora` — **cuántas** series mejora el retador y por cuánto. Un WAPE
  agregado que baja puede venir de mejorar mucho en pocas series grandes: el WAPE pondera
  por magnitud, y en el catálogo real las magnitudes van de jeringas a vacunas.

**Lo que este módulo no hace: seleccionar.** El champion/challenger lo decide
`modelado.seleccion.elegir_mejor_por_corte` con la regla prospectiva de ADR-016 (por corte,
solo con error ya observado). Acá se mide el resultado, y medir con el WAPE de todos los
cortes —que es lo que hace `wape_por_serie`— es legítimo *para reportar*, pero **no** para
elegir: ese es exactamente el hindsight que ADR-016 sacó del piso.
"""

import numpy as np
import pandas as pd

from .metricas import sesgo, wape


def wape_por_serie(
    reporte: pd.DataFrame,
    modelos: list[str],
    columna_id: str = "id_producto",
    columna_real: str = "real",
    columna_horizonte: str = "horizonte",
) -> pd.DataFrame:
    """WAPE de cada modelo en cada `(serie, horizonte)`, en formato largo.

    Devuelve `columna_id`, `columna_horizonte`, `modelo`, `wape`, `n`, `cobertura`. El
    formato largo y no ancho es a propósito: los candidatos no cubren las mismas filas
    (una serie joven puede tener predicción del global y no de `AutoARIMA`), y en formato
    ancho esa diferencia se disfraza de `NaN` en una celda en vez de aparecer como
    `cobertura` distinta.

    Reusa `metricas.wape` en vez de recalcular: el WAPE por serie tiene que ser el mismo
    número que el de la tabla agregada, y dos implementaciones equivalentes son dos
    definiciones que se separan en el primer caso borde (`real` todo cero → NaN, no cero).
    """
    if not modelos:
        raise ValueError("Hace falta al menos un modelo para comparar")
    faltantes = sorted(set(modelos) - set(reporte.columns))
    if faltantes:
        raise ValueError(f"El reporte no tiene columnas para los modelos {faltantes}")

    partes = []
    for modelo in modelos:
        tabla = wape(
            reporte,
            columnas_grupo=[columna_id, columna_horizonte],
            columna_real=columna_real,
            columna_pred=modelo,
        )
        tabla.insert(2, "modelo", modelo)
        partes.append(tabla)
    return pd.concat(partes, ignore_index=True)


def distribucion_de_mejora(
    por_serie: pd.DataFrame,
    campeon: str,
    retador: str,
    horizontes: tuple[int, ...] | None = None,
    clasificacion: pd.DataFrame | None = None,
    columna_id: str = "id_producto",
    columna_horizonte: str = "horizonte",
    columna_cuadrante: str = "cuadrante",
) -> pd.DataFrame:
    """Cuántas series mejora el `retador` sobre el `campeon`, y por cuánto.

    `mejora = wape(campeon) - wape(retador)`: **positivo es a favor del retador**. Se
    reporta la mediana y no la media porque la distribución tiene colas largas — una serie
    con `wape` de 40 la corre entera y esconde a las 2.000 que se movieron 0,01.

    **Comparable significa misma cobertura, y hay que exigirlo explícitamente.** En
    `metricas.wape` una predicción nula aporta 0 al numerador, así que una serie que un
    modelo **no predijo** sale con `wape` de 0,0 —perfecto— y lo único que lo delata es la
    columna `cobertura`. Comparar por WAPE definido coronaría ganador al que no predijo.
    Entran entonces solo las celdas donde los dos tienen cobertura **mayor que cero e
    igual**: si uno cubrió 3 cortes de 5 y el otro los 5, sus WAPE miden sobre distinto
    conjunto de filas. El resto se cuenta en `no_comparable` —las dos causas juntas— para
    que la exclusión no sea invisible; la diferencia de cobertura en sí se lee en
    `cabeza_a_cabeza`.

    Con `clasificacion` (la de `motor.clasificacion.clasificar_series`) abre por cuadrante,
    que es donde se ve lo que el agregado tapa: en M2.4 el intervalo calibraba en promedio
    porque `suave` es la mayoría de las filas, mientras `erratica` sub-cubría 12 puntos.
    """
    for modelo in (campeon, retador):
        if modelo not in set(por_serie["modelo"]):
            raise ValueError(f"`por_serie` no tiene filas del modelo '{modelo}'")

    datos = por_serie[por_serie["modelo"].isin([campeon, retador])]
    if horizontes is not None:
        datos = datos[datos[columna_horizonte].isin(horizontes)]

    ancho = datos.pivot_table(
        index=[columna_id, columna_horizonte],
        columns="modelo",
        values=["wape", "cobertura"],
        dropna=False,
    )
    ancho.columns = [f"{metrica}_{modelo}" for metrica, modelo in ancho.columns]
    ancho = ancho.reset_index()

    cobertura_campeon, cobertura_retador = ancho[f"cobertura_{campeon}"], ancho[
        f"cobertura_{retador}"
    ]
    comparables = (
        (cobertura_campeon > 0) & (cobertura_retador > 0) & (cobertura_campeon == cobertura_retador)
    )
    ancho["mejora"] = ancho[f"wape_{campeon}"] - ancho[f"wape_{retador}"]

    grupos: list[str] = [columna_horizonte]
    if clasificacion is not None:
        ancho = ancho.merge(
            clasificacion[[columna_id, columna_cuadrante]], on=columna_id, how="left"
        )
        ancho[columna_cuadrante] = ancho[columna_cuadrante].fillna("sin_clasificar")
        grupos = [columna_cuadrante, columna_horizonte]

    ancho["_comparable"] = comparables.to_numpy()
    filas = []
    for clave, grupo in ancho.groupby(grupos, observed=True):
        comparable = grupo[grupo["_comparable"]]
        mejora = comparable["mejora"]
        clave = clave if isinstance(clave, tuple) else (clave,)
        vacio = len(mejora) == 0
        filas.append(
            {
                **dict(zip(grupos, clave, strict=True)),
                "series": len(comparable),
                "no_comparable": int((~grupo["_comparable"]).sum()),
                "gana_retador": int((mejora > 0).sum()),
                "%_gana_retador": np.nan if vacio else round(float((mejora > 0).mean() * 100), 1),
                "mejora_mediana": np.nan if vacio else float(mejora.median()),
                "mejora_p25": np.nan if vacio else float(mejora.quantile(0.25)),
                "mejora_p75": np.nan if vacio else float(mejora.quantile(0.75)),
            }
        )
    return pd.DataFrame(filas).sort_values(grupos).reset_index(drop=True)


def cabeza_a_cabeza(
    reporte: pd.DataFrame,
    contendientes: dict[str, str],
    horizontes: tuple[int, ...] = (1, 3, 6, 12),
    columna_id: str = "id_producto",
    columna_real: str = "real",
    columna_horizonte: str = "horizonte",
    columna_categoria: str = "categoria",
) -> pd.DataFrame:
    """WAPE, sesgo y cobertura de varios contendientes por nivel y horizonte, en una tabla.

    `contendientes` es `nombre legible -> columna del reporte`, y el nombre es el que sale
    en la tabla congelada ("piso", "global", "champion/challenger"). Los niveles son los de
    ADR-008: producto, categoría y total.

    **La columna `cobertura` es parte del veredicto, no decoración.** Dos WAPE solo se
    comparan si cubren las mismas filas: omitir las series difíciles mejora el score sin
    predecir mejor, que es lo que §5.6.1 midió en el piso retrospectivo. Si esta tabla
    muestra coberturas distintas entre contendientes, la comparación de WAPE **no vale** y
    hay que igualar antes de leerla.
    """
    if not contendientes:
        raise ValueError("Hace falta al menos un contendiente")
    faltantes = sorted(set(contendientes.values()) - set(reporte.columns))
    if faltantes:
        raise ValueError(f"El reporte no tiene columnas para los contendientes {faltantes}")

    del_horizonte = reporte[reporte[columna_horizonte].isin(horizontes)]
    niveles: dict[str, list[str] | None] = {"producto": [columna_id], "total": []}
    if columna_categoria in reporte.columns:
        niveles = {
            "producto": [columna_id],
            "categoria": [columna_categoria],
            "total": [],
        }

    filas = []
    for nombre, columna in contendientes.items():
        for nivel, columnas_nivel in niveles.items():
            comun = {
                "columnas_grupo": [columna_horizonte],
                "columna_real": columna_real,
                "columna_pred": columna,
                "columnas_nivel": columnas_nivel,
            }
            tabla = wape(del_horizonte, **comun)
            # El sesgo va en la misma tabla porque el gate de M2 se lee de las dos cosas
            # a la vez: ganar en WAPE con un sesgo fuera del ±5% no cumple ADR-008.
            tabla["sesgo"] = sesgo(del_horizonte, **comun)["sesgo"]
            tabla.insert(0, "contendiente", nombre)
            tabla.insert(1, "nivel", nivel)
            filas.append(tabla)

    resultado = pd.concat(filas, ignore_index=True)
    orden_nivel = pd.CategoricalDtype(list(niveles), ordered=True)
    resultado["nivel"] = resultado["nivel"].astype(orden_nivel)
    orden_contendiente = pd.CategoricalDtype(list(contendientes), ordered=True)
    resultado["contendiente"] = resultado["contendiente"].astype(orden_contendiente)
    return resultado.sort_values(["nivel", columna_horizonte, "contendiente"]).reset_index(
        drop=True
    )


def cabeza_a_cabeza_desagregado(
    reporte: pd.DataFrame,
    contendientes: dict[str, str],
    columna_corte: str = "cuadrante",
    horizontes: tuple[int, ...] = (1, 3, 6, 12),
    columna_id: str = "id_producto",
    columna_real: str = "real",
    columna_horizonte: str = "horizonte",
) -> pd.DataFrame:
    """Lo mismo que `cabeza_a_cabeza` pero abierto por `columna_corte`, **con el peso**.

    La columna `peso_%` es la participación de cada grupo en el `sum(|real|)` de su
    horizonte, o sea **cuánto pesa ese grupo en el WAPE agregado**. Sin ella la tabla se
    lee al revés: en la corrida real de M2.5, `suave` carga el 86% del peso y los dos
    cuadrantes intermitentes juntos el 0,6%, así que un modelo puede errar por 3x en
    `lumpy` y ganar igual el agregado. Un promedio que esconde de qué está hecho es el
    modo de falla que M2.4 ya encontró con la cobertura del intervalo.

    Va a grano producto y nada más: los niveles categoría/total no se cruzan con un corte
    por cuadrante, porque una categoría mezcla series de los cuatro.
    """
    if not contendientes:
        raise ValueError("Hace falta al menos un contendiente")
    if columna_corte not in reporte.columns:
        raise ValueError(f"El reporte no tiene la columna '{columna_corte}'")

    del_horizonte = reporte[reporte[columna_horizonte].isin(horizontes)]
    filas = []
    for nombre, columna in contendientes.items():
        comun = {
            "columnas_grupo": [columna_corte, columna_horizonte],
            "columna_real": columna_real,
            "columna_pred": columna,
            "columnas_nivel": [columna_id],
        }
        tabla = wape(del_horizonte, **comun)
        tabla["sesgo"] = sesgo(del_horizonte, **comun)["sesgo"]
        tabla.insert(0, "contendiente", nombre)
        filas.append(tabla)

    resultado = pd.concat(filas, ignore_index=True)
    peso = (
        del_horizonte.assign(_abs=del_horizonte[columna_real].abs())
        .groupby([columna_corte, columna_horizonte], observed=True)["_abs"]
        .sum()
        .rename("_peso")
        .reset_index()
    )
    peso["peso_%"] = peso.groupby(columna_horizonte, observed=True)["_peso"].transform(
        lambda s: s / s.sum() * 100
    )
    resultado = resultado.merge(
        peso.drop(columns=["_peso"]), on=[columna_corte, columna_horizonte], how="left"
    )

    orden = pd.CategoricalDtype(list(contendientes), ordered=True)
    resultado["contendiente"] = resultado["contendiente"].astype(orden)
    return resultado.sort_values(
        [columna_corte, columna_horizonte, "contendiente"]
    ).reset_index(drop=True)
