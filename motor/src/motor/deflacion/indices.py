"""Índices de precio por nivel — el problema de números índice que hay detrás de ADR-002.

## Por qué no se promedian precios

Para deflactar un producto sin ancla propia hay que saber cuánto se movió su categoría.
La tentación es promediar los precios de la categoría, y está mal: una categoría mezcla
una jeringa de $20 con una vacuna de $20.000, así que ese promedio se mueve cada vez que
cambia **qué** se vendió, sin que ningún precio haya cambiado. Con 42% de series
intermitentes (EDA §3), el mix cambia todos los meses.

La salida es la clásica de números índice: promediar **variaciones** en vez de niveles y
encadenarlas.

```
R_N,t = exp( Σ w·ln r / Σ w )        media geométrica ponderada de los relativos del nivel
I_N,t = I_N,t-1 × R_N,t              índice encadenado
```

Geométrica y no aritmética porque los relativos son multiplicativos: subir 100% y bajar
50% tiene que volver al punto de partida, y la media aritmética de 2,0 y 0,5 da 1,25.

## El clamp, y por qué vale 3

La contracara de la media geométrica es que un relativo cercano a cero pesa `ln r → -∞`.
Un precio basura de `0,01` —el EDA §6 contó 3.691 renglones con precio ≤ 0,5— genera un
relativo de 1e-4 en un mes y 1e4 al siguiente, y arrastra al nivel entero.

`LIMITE_RELATIVO = 3` se eligió midiendo sobre las 125.078 muestras apareadas del extract
real (2026-07-31), no a ojo:

| clamp | pares recortados | en el peor mes |
|---|---|---|
| 1,5 | 1,841% | **31,35%** |
| 2 | 0,613% | 3,05% |
| **3** | **0,325%** | **0,77%** |
| 5 | 0,221% | 0,63% |
| 20 | 0,162% | 0,61% |

La columna que decide es la última. Con 1,5 y con 2 el clamp reacciona a la devaluación de
dic-2023 (el IPC hizo +25,47% ese mes): está recortando inflación real. En 3 el peor mes
cae a 0,77%, casi igual al promedio — dejó de ser sensible a eventos macro y solo corta
cola. De 3 en adelante casi no cambia nada.

Que la cola sea basura está verificado: de los 276 pares con `r > 5` o `r < 1/5`, **167
tienen algún precio por debajo de $5** y su revenue mediano es $1.148 contra $53.335 del
par típico — 46 veces más chicos.

La asimetría termina de cerrarlo: recortar un `r = 4` legítimo cuesta `ln(4/3) = 0,29` en
un producto de ~1.360 del mes, mientras que dejar pasar el `r = 45.000` que hay en los
datos cuesta `ln = 10,7` **y se arrastra por el encadenado**.

**El clamp es una constante, no un cuantil.** Derivarlo de los datos de cada corte sería
leakage temporal: el umbral dependería del futuro. Se midió una vez, offline, sobre todo
el histórico, y quedó fijo.

## Muestra mínima

Un "índice" calculado sobre un solo producto no es un índice: es el ruido de ese producto.
`MUESTRA_MINIMA = 3` es el piso para que un nivel tenga índice en un mes; por debajo, el
nivel no responde y la cascada baja un peldaño.

Medido sobre el extract: con este piso la categoría resuelve el **99,6%** de las celdas
producto×mes, laboratorio agrega 0,06% y el IPC atiende 0,34%. Subirlo a 5 casi no cambia
nada (el IPC pasaría a 0,40%) y bajarlo a 2 tampoco (0,22%), así que el valor exacto no es
crítico — lo que importa es que exista.
"""

import numpy as np
import pandas as pd

LIMITE_RELATIVO = 3.0
"""Cota del relativo mensual, simétrica en logaritmos: `[1/3, 3]`. Ver §"El clamp"."""

MUESTRA_MINIMA = 3
"""Pares apareados que necesita un nivel para tener índice en un mes."""

COLUMNAS_INDICE = ("nivel", "id_nivel", "anio_mes", "indice")
"""Esquema `indice_precio_nivel` del diccionario (C2), para apilar niveles sin renombrar."""


def clampear(relativo: pd.Series, limite: float = LIMITE_RELATIVO) -> pd.Series:
    """Recorta el relativo a `[1/limite, limite]`. Recorta, no descarta.

    Descartar el par sacaría al producto de la muestra de ese mes y el nivel pasaría a
    medir un conjunto distinto de productos cada mes — el mismo problema de mix que el
    índice viene a resolver. Recortando, el producto sigue adentro con una variación
    creíble.
    """
    if limite <= 1:
        raise ValueError(f"El límite tiene que ser > 1 para acotar de los dos lados, es {limite}")
    return relativo.clip(lower=1 / limite, upper=limite)


def _media_geometrica_ponderada(grupo: pd.DataFrame) -> float:
    peso = grupo["peso"].to_numpy(dtype="float64")
    # Un peso nulo o negativo (un mes de neto negativo por devoluciones, §5.5 #5) no puede
    # entrar: pesos negativos dan una media sin sentido y todo-cero da 0/0. Se cae a peso
    # uniforme, que es peor que ponderar pero mejor que un NaN que se propaga.
    if not np.isfinite(peso).all() or (peso <= 0).any() or peso.sum() <= 0:
        peso = np.ones_like(peso)
    return float(np.exp(np.average(np.log(grupo["relativo"].to_numpy()), weights=peso)))


def indice_de_nivel(
    relativos: pd.DataFrame,
    nivel: str,
    muestra_minima: int = MUESTRA_MINIMA,
    limite: float = LIMITE_RELATIVO,
) -> pd.DataFrame:
    """Índice encadenado de un nivel, a partir de los relativos ya asignados a sus grupos.

    Args:
        relativos: `id_nivel`, `anio_mes`, `relativo`, `peso` — la salida de
            `precios.relativos_apareados` con la columna de agrupación ya pegada.
        nivel: etiqueta que va en la columna `nivel` del resultado (`"categoria"`, …).

    Returns:
        `COLUMNAS_INDICE`. **La base es el primer mes de cada grupo, valor 1,0.**

    La base va en el primer mes y no en el último para que **esta función sea pura
    respecto del futuro**: con base en el último, agregar un mes reescala toda la serie
    hacia atrás, así que el índice de enero dependería de si ya llegó diciembre.

    Aclaración honesta sobre el alcance, verificada por mutación: eso **no** es leakage
    para `TransformadorDeflacion`, que recorta en el corte antes de llamar acá y después
    solo usa *cocientes* entre dos meses — una constante por corrida se cancela, y de
    hecho `verificar_sin_leakage` no detecta el cambio de base. Quien lo detecta es
    `test_agregar_meses_futuros_no_cambia_el_indice_de_los_meses_previos`. La base en el
    primer mes protege al próximo que llame a esta función sin recortar antes, no al
    transformador de hoy.
    """
    if relativos.empty:
        return pd.DataFrame({c: pd.Series(dtype=t) for c, t in _tipos().items()})

    acotados = relativos.assign(relativo=clampear(relativos["relativo"], limite))

    por_grupo_mes = acotados.groupby(["id_nivel", "anio_mes"], sort=True)
    variacion = por_grupo_mes.apply(_media_geometrica_ponderada, include_groups=False)
    suficiente = por_grupo_mes.size() >= muestra_minima

    variacion = variacion[suficiente].rename("variacion").reset_index()
    if variacion.empty:
        return pd.DataFrame({c: pd.Series(dtype=t) for c, t in _tipos().items()})

    # Encadenado dentro de cada grupo. Un mes sin muestra suficiente no aparece: la cadena
    # lo saltea en vez de cortarse, porque el índice de un nivel es una serie de niveles y
    # un hueco de un mes no invalida los meses siguientes.
    acumulado = variacion.groupby("id_nivel", sort=False)["variacion"].cumprod()
    # Por el PRIMER mes del grupo: no se mueve cuando llegan datos nuevos, el último sí
    # (ver el §Returns, que aclara qué protege esto y qué no).
    variacion["indice"] = acumulado / acumulado.groupby(variacion["id_nivel"]).transform("first")

    return pd.DataFrame(
        {
            "nivel": nivel,
            "id_nivel": variacion["id_nivel"].astype("object"),
            "anio_mes": variacion["anio_mes"],
            "indice": variacion["indice"].astype("float64"),
        }
    )


def _tipos() -> dict[str, str]:
    return {
        "nivel": "object",
        "id_nivel": "object",
        "anio_mes": "datetime64[ns]",
        "indice": "float64",
    }


def factor_entre(indice: pd.Series, desde: pd.Timestamp, hasta: pd.Timestamp) -> float:
    """Cuánto se movió un nivel entre dos meses: `I_hasta / I_desde`.

    Args:
        indice: serie del nivel, indexada por `anio_mes`.

    Returns:
        El factor, o `NaN` si al nivel le falta alguno de los dos meses — que es la señal
        de que hay que bajar un peldaño de la cascada, no un error.
    """
    if desde not in indice.index or hasta not in indice.index:
        return float("nan")
    base = indice.loc[desde]
    return float("nan") if base <= 0 else float(indice.loc[hasta] / base)
