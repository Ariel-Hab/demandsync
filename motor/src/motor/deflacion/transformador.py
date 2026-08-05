"""`TransformadorDeflacion` — la deflación read-time de ADR-002, de punta a punta.

## La fórmula, y por qué preserva el descuento

```
monto_real = revenue_c,t × (P_hoy / P_t) = unidades_c,t × P_hoy × (p_c,t / P_t)
                                                                  └─────────┘
                                                                  el descuento
```

`P_t` es el precio promedio del **producto** ese mes y `p_c,t` el que pagó ese cliente. El
promedio del producto es el índice, no el valor a deflactar, así que el cociente entre lo
que pagó el cliente y el promedio —su descuento individual— sobrevive intacto.

La forma prohibida por ADR-002, `unidades × P_hoy`, es literalmente la misma cuenta con
ese factor forzado a 1: le borra el descuento a todo el mundo. Y el descuento por cliente
es de las pocas señales fuertes que hay a nivel cliente×producto.

## Todo colapsa a una matriz de deflactores

El objeto que este transformador construye es un deflactor por (producto, mes ≤ corte):

```
d_i,t = ancla_i / P̂_i,t          revenue_real = revenue × d_i,t
```

`P̂_i,t` es el precio estimado del producto ese mes: **el propio cuando es utilizable**, y
si no, el precio utilizable más cercano trasladado con el índice de su nivel. Cuando el
mes es utilizable el traslado es un factor 1, así que es una fórmula sola y no dos ramas.

El ancla deja de ser un objeto aparte: es el caso `d_i,corte = 1`.

## La cascada presta el índice, no el nivel

Un producto sin precio propio **no hereda el precio de su categoría**. Con la dispersión
que hay adentro de una categoría —jeringas de $20 y vacunas de $20.000— eso sería
disparatado. Hereda el *movimiento*: conserva su último precio propio y le aplica cuánto
se movió el vecindario.

Orden de peldaños fijado por ADR-002: `producto → categoría → laboratorio → IPC`. Medido
sobre el extract real, la categoría resuelve el **99,6%** de las celdas producto×mes, el
laboratorio agrega 0,06% y el IPC atiende 0,34%. Que el laboratorio sea más granular que
la categoría (82 valores contra 12) y por eso tenga menos muestra no lo hace inútil: es
justamente el peldaño de los productos que caen en categorías diminutas.

**Consecuencia para los tests:** con 0,06% de uso, los datos reales no ejercitan el
peldaño laboratorio. Se prueba con un caso construido o esa rama queda sin cubrir.

## Anti-leakage

El recorte por corte se hace **una sola vez, acá arriba**, y todo lo de abajo es puro. Esa
única línea es lo que sostiene el anti-leakage: sacarla hace fallar la red en las tres
salidas (verificado por mutación). Las otras dos precauciones son las que la red no podría
atrapar sola: no hay ningún promedio global sobre toda la historia —el caso que el
docstring de `leakage.py` señala como el realista— y los umbrales del clamp son constantes
medidas offline, no cuantiles de la corrida, que dependerían del futuro.

La red es `motor.backtesting.leakage.verificar_sin_leakage`, escrita en M1.3 antes que este
módulo, y se corre sobre `ancla_`, `indices_` y `deflactor_`.
"""

from typing import Self

import numpy as np
import pandas as pd

from motor.datos.ipc import cargar_ipc
from motor.deflacion.indices import (
    LIMITE_RELATIVO,
    MUESTRA_MINIMA,
    indice_de_nivel,
)
from motor.deflacion.precios import es_utilizable, relativos_apareados

VENTANA_ANCLA_MESES = 3
"""Meses calendario hacia atrás desde el corte que definen el ancla propia. Es la ventana
con la que el EDA §4 midió el 74,6% de cobertura, así que cambiarla mueve ese número."""

NIVELES_CASCADA = ("categoria", "laboratorio", "ipc")
"""Orden de ADR-002. `ipc` es el fondo: siempre tiene todos los meses."""

NIVELES_CONTRASTE = ("categoria", "laboratorio")
"""Niveles contra los que se puede juzgar si el precio propio de un producto es creíble.

**El IPC queda deliberadamente afuera.** Categoría y laboratorio se construyen con los
relativos de los propios productos del cliente, así que un producto que se despega 10× de
su categoría se está despegando de un espejo de sí mismo — eso es señal. El IPC es un
índice macro externo que no tiene ninguna obligación de seguir precios veterinarios:
despegarse de él es normal y no prueba nada.

Distinguirlos es lo que hace que este recorte **no contradiga a ADR-002**. La cascada de
ADR-002 sirve para *estimar un precio que falta*; esto es otra operación: *validar uno que
se observó*. Por eso acá el orden de peldaños no aplica y el fondo de la cascada no sirve
de contraste.
"""

ID_NIVEL_IPC = "nacional"

LIMITE_DESVIO_NIVEL = 10.0
"""Cuánto puede alejarse el deflactor de un producto del que da su nivel, en veces.

`LIMITE_RELATIVO` protege el **índice**; esto protege el **deflactor directo**, que es el
caso en que el producto sí tiene precio propio ese mes y por lo tanto no consulta ningún
índice. Ahí `d = ancla / precio_propio` y un precio centinela lo hace explotar sin freno.

**No se puede acotar `d` con una constante**, y está medido: su magnitud legítima crece con
la distancia al corte, porque es inflación acumulada. La mediana va de 1,02 en el año en
curso a 54,4 a ocho años, con p99 de 1,27 a 129 y máximos legítimos de ~560. Cualquier cota
que atrape un deflactor absurdo de 2021 recorta inflación real de 2018.

Lo que sí está acotado es el **desvío contra el nivel**, `q = d / d_nivel`: adimensional y
sin dependencia de la distancia (mediana 0,980, p95 1,45, p99 2,22). Y a diferencia de
`LIMITE_RELATIVO` —que tuvo que subir a 3 para dejar de reaccionar a dic-2023— `q` es
inmune a los eventos macro, porque una devaluación mueve numerador y denominador juntos.

El valor sale de la misma tabla que decidió `LIMITE_RELATIVO`, con el mismo criterio: la
columna del peor mes.

| límite | recorta | **peor mes** | deflactor máx | Δ revenue real |
|---|---|---|---|---|
| 3 | 1,877% | **17,21%** | 246,8 | +1,106% |
| 5 | 1,123% | 8,81% | 308,6 | −0,164% |
| **10** | **0,775%** | **2,51%** | **319,3** | **−0,322%** |
| 20 | 0,626% | 2,34% | 421,1 | −0,135% |

En 3 y en 5 muerde sistemáticamente en el tramo viejo de la serie, donde la base del índice
encadenado es más floja; en 10 el peor mes cae al nivel del promedio y de ahí en más casi no
cambia. Sobre el extract deja **0 filas con deflactor > 1.000**, contra 55 sin él.

**Es una constante, no un cuantil de la corrida** — mismo motivo que `LIMITE_RELATIVO`:
derivarla de los datos de cada corte haría que el umbral dependiera del futuro.
"""


class TransformadorDeflacion:
    """Lleva montos nominales a pesos del corte, preservando el descuento por cliente.

    El catálogo y el IPC entran por el constructor porque son datos de referencia que no
    varían con el corte; `ajustar` recibe solo lo que sí varía. Esa separación no es
    estética: `verificar_sin_leakage` invoca `calcular(datos, corte)` con exactamente dos
    argumentos posicionales, así que la firma quedó fijada en M1.3.

    Sin catálogo la cascada es `producto → IPC`, que es lo que hace válida la construcción
    sin argumentos.
    """

    def __init__(
        self,
        catalogo: pd.DataFrame | None = None,
        ipc: pd.DataFrame | None = None,
        ventana_ancla: int = VENTANA_ANCLA_MESES,
        limite: float = LIMITE_RELATIVO,
        muestra_minima: int = MUESTRA_MINIMA,
        limite_desvio: float = LIMITE_DESVIO_NIVEL,
    ) -> None:
        self.catalogo = catalogo
        self.ipc = ipc
        self.ventana_ancla = ventana_ancla
        self.limite = limite
        self.muestra_minima = muestra_minima
        self.limite_desvio = limite_desvio

    def ajustar(self, hechos: pd.DataFrame, corte: pd.Timestamp) -> Self:
        """Calcula índices, anclas y deflactores usando **solo** datos ≤ `corte`.

        Args:
            hechos: `hecho_venta_mensual_producto`.
            corte: el "hoy" de esta corrida. En backtest es el hoy de *ese* corte.
        """
        corte = pd.Timestamp(corte).normalize().replace(day=1)
        visible = hechos[hechos["anio_mes"] <= corte].copy()

        self.corte_ = corte
        self.indices_ = self._construir_indices(visible, corte)
        self.ancla_, self.origen_ancla_ = self._construir_ancla(visible, corte)
        self.deflactor_ = self._construir_deflactores(visible)
        return self

    # ---------------------------------------------------------------- índices

    def _construir_indices(self, visible: pd.DataFrame, corte: pd.Timestamp) -> pd.DataFrame:
        relativos = relativos_apareados(visible)
        piezas = []

        for nivel in ("categoria", "laboratorio"):
            if self.catalogo is None or nivel not in self.catalogo.columns:
                continue
            con_nivel = relativos.merge(
                self.catalogo[["id_producto", nivel]].rename(columns={nivel: "id_nivel"}),
                on="id_producto",
                how="inner",
            ).dropna(subset=["id_nivel"])
            piezas.append(
                indice_de_nivel(
                    con_nivel, nivel, muestra_minima=self.muestra_minima, limite=self.limite
                )
            )

        piezas.append(self._indice_ipc(corte))
        return pd.concat(piezas, ignore_index=True)

    def _indice_ipc(self, corte: pd.Timestamp) -> pd.DataFrame:
        """El IPC ya viene como índice de nivel: no hay relativos que promediar.

        Se recorta en el corte igual que todo lo demás. Su base (dic-2016 = 100) es
        arbitraria y se cancela, porque solo se usan cocientes entre dos meses.
        """
        ipc = self.ipc if self.ipc is not None else cargar_ipc(hasta=corte)
        ipc = ipc[ipc["anio_mes"] <= corte]
        return pd.DataFrame(
            {
                "nivel": "ipc",
                "id_nivel": ID_NIVEL_IPC,
                "anio_mes": ipc["anio_mes"].to_numpy(),
                "indice": ipc["indice"].to_numpy(dtype="float64"),
            }
        )

    # ------------------------------------------------------------------ ancla

    def _construir_ancla(
        self, visible: pd.DataFrame, corte: pd.Timestamp
    ) -> tuple[pd.DataFrame, pd.Series]:
        usable = visible[es_utilizable(visible["precio_prom"])]
        productos = pd.Index(visible["id_producto"].unique(), name="id_producto").sort_values()

        propia = self._ancla_propia(usable, corte).reindex(productos)
        origen = pd.Series(
            np.where(propia.notna(), "producto", None), index=productos, dtype="object"
        )

        faltan = propia.isna()
        if faltan.any():
            derivada, nivel = self._ancla_derivada(usable, productos[faltan], corte)
            propia = propia.fillna(derivada)
            origen[faltan] = nivel.reindex(productos[faltan]).to_numpy()

        ancla = pd.DataFrame(
            {
                "id_producto": productos.to_numpy(dtype="int64"),
                "precio_prom_hoy": propia.to_numpy(dtype="float64"),
                "fecha_calculo": corte,
            }
        )
        return ancla, origen.fillna("sin_ancla")

    def _ancla_propia(self, usable: pd.DataFrame, corte: pd.Timestamp) -> pd.Series:
        """Precio del producto en la ventana reciente, ponderado por unidades.

        Ponderar por unidades y no promediar los `precio_prom` a secas mantiene la
        definición de ADR-001 (el precio del producto es el promedio ponderado por
        cantidad). Si en la ventana no hay unidades positivas —una ventana que es toda
        devoluciones— se cae al promedio simple, que es peor pero no es un `NaN`.
        """
        desde = corte - pd.DateOffset(months=self.ventana_ancla - 1)
        ventana = usable[usable["anio_mes"] >= desde]
        if ventana.empty:
            return pd.Series(dtype="float64", name="precio_prom_hoy")

        simple = ventana.groupby("id_producto")["precio_prom"].mean()

        positivas = ventana[ventana["unidades"] > 0]
        if positivas.empty:
            return simple.rename("precio_prom_hoy")

        ponderada = positivas.groupby("id_producto").apply(
            lambda g: float(np.average(g["precio_prom"], weights=g["unidades"])),
            include_groups=False,
        )
        return ponderada.reindex(simple.index).fillna(simple).rename("precio_prom_hoy")

    def _ancla_derivada(
        self, usable: pd.DataFrame, productos: pd.Index, corte: pd.Timestamp
    ) -> tuple[pd.Series, pd.Series]:
        """Último precio propio, trasladado al corte por el primer nivel que responda."""
        ultimo = (
            usable[usable["id_producto"].isin(productos)]
            .sort_values("anio_mes")
            .groupby("id_producto", as_index=False)
            .last()[["id_producto", "anio_mes", "precio_prom"]]
            .rename(columns={"anio_mes": "mes_desde"})
        )
        if ultimo.empty:
            vacio = pd.Series(dtype="float64")
            return vacio, pd.Series(dtype="object")

        ultimo["mes_hasta"] = corte
        factor, nivel = self._factor_cascada(ultimo)
        derivada = (ultimo["precio_prom"] * factor).set_axis(ultimo["id_producto"])
        return derivada, nivel.set_axis(ultimo["id_producto"])

    # ------------------------------------------------------------- deflactores

    def _construir_deflactores(self, visible: pd.DataFrame) -> pd.DataFrame:
        """Un deflactor por (producto, mes) de los que aparecen en los hechos visibles.

        Para los meses sin precio propio utilizable se toma el precio utilizable más
        cercano del mismo producto —hacia atrás y, si no hay, hacia adelante dentro del
        corte— y se lo traslada con el índice del nivel. Ir "hacia adelante" no es
        leakage: todo lo visible ya está recortado en el corte, y la deflación es una
        transformación de lectura que se hace parada en ese hoy.
        """
        base = visible[["id_producto", "anio_mes", "precio_prom"]].sort_values(
            ["id_producto", "anio_mes"]
        )
        base["propio"] = base["precio_prom"].where(es_utilizable(base["precio_prom"]))
        base["mes_propio"] = base["anio_mes"].where(base["propio"].notna())

        # El `groupby` se rearma en cada paso a propósito: reusar uno tomado antes de
        # mutar `base` lo deja apuntando a una foto vieja del frame.
        for columna in ("propio", "mes_propio"):
            relleno = base.groupby("id_producto", sort=False)[columna].ffill()
            base[columna] = relleno
            base[columna] = base.groupby("id_producto", sort=False)[columna].bfill()

        base = base.rename(columns={"mes_propio": "mes_desde", "anio_mes": "mes_hasta"})
        base = base.dropna(subset=["propio"])
        if base.empty:
            return pd.DataFrame(
                {
                    "id_producto": pd.Series(dtype="int64"),
                    "anio_mes": pd.Series(dtype="datetime64[ns]"),
                    "deflactor": pd.Series(dtype="float64"),
                }
            )

        # Mismo mes: el traslado es la identidad y no hace falta consultar ningún nivel.
        mismo = base["mes_desde"] == base["mes_hasta"]
        factor = pd.Series(1.0, index=base.index)
        if (~mismo).any():
            factor[~mismo] = self._factor_cascada(base[~mismo])[0].to_numpy()

        precio_estimado = base["propio"] * factor
        ancla = self.ancla_.set_index("id_producto")["precio_prom_hoy"]
        deflactor = pd.Series(
            ancla.reindex(base["id_producto"]).to_numpy()
            / precio_estimado.where(precio_estimado > 0).to_numpy(),
            index=base.index,
        )

        return pd.DataFrame(
            {
                "id_producto": base["id_producto"].to_numpy(dtype="int64"),
                "anio_mes": base["mes_hasta"].to_numpy(),
                "deflactor": self._acotar_contra_nivel(base, deflactor).to_numpy(),
            }
        )

    def _acotar_contra_nivel(self, base: pd.DataFrame, deflactor: pd.Series) -> pd.Series:
        """Recorta el desvío del deflactor contra el de su nivel a `[1/L, L]`.

        Se recorta `q = d / d_nivel` y se reconstruye `d = clip(q) × d_nivel`, en vez de
        reemplazar por `d_nivel` a secas: el producto conserva la parte de su desvío que es
        creíble, igual que `clampear` recorta el relativo en lugar de descartar el par.

        **Solo se juzga contra `NIVELES_CONTRASTE`.** Una fila cuyo único nivel disponible
        es el IPC queda **sin tocar**: sin espejo construido con precios del cliente no hay
        desvío que medir, y recortar contra el IPC castigaría al producto por no seguir a la
        inflación macro. Es también lo que mantiene intacta la garantía de CP-INF-01.
        """
        referencia = pd.DataFrame(
            {
                "id_producto": base["id_producto"],
                "mes_desde": base["mes_hasta"],
                "mes_hasta": self.corte_,
            }
        )
        d_nivel, nivel = self._factor_cascada(referencia, niveles=NIVELES_CONTRASTE)

        juzgable = d_nivel.notna() & (d_nivel > 0) & deflactor.notna() & nivel.notna()
        if not juzgable.any():
            return deflactor

        q = deflactor[juzgable] / d_nivel[juzgable]
        acotado = q.clip(1 / self.limite_desvio, self.limite_desvio) * d_nivel[juzgable]
        return deflactor.mask(juzgable, acotado)

    # ---------------------------------------------------------------- cascada

    def factor_de_nivel(
        self, pares: pd.DataFrame, niveles: tuple[str, ...] = NIVELES_CONTRASTE
    ) -> tuple[pd.Series, pd.Series]:
        """Cuánto se movió el **nivel** de cada producto entre `mes_desde` y `mes_hasta`.

        Es la cara pública de `_factor_cascada`, y existe porque las features de precio de
        M2.2 necesitan exactamente este factor: el movimiento del vecindario de un producto,
        contra el cual se juzga si su propio precio subió más o menos. Sin esto,
        `motor.features` tendría que importar un privado de este módulo o reimplementar la
        cascada, que es la forma habitual de que dos definiciones se separen en silencio.

        El default es `NIVELES_CONTRASTE` y no la cascada completa, porque el caso de uso es
        **contrastar** (validar un precio observado) y no **estimar** uno que falta — la
        misma distinción que documenta `NIVELES_CONTRASTE`.
        """
        return self._factor_cascada(pares, niveles=niveles)

    def _factor_cascada(
        self, pares: pd.DataFrame, niveles: tuple[str, ...] = NIVELES_CASCADA
    ) -> tuple[pd.Series, pd.Series]:
        """`I_nivel(mes_hasta) / I_nivel(mes_desde)` por el primer nivel que responda.

        Args:
            pares: `id_producto`, `mes_desde`, `mes_hasta`.
            niveles: peldaños a probar, en orden. El default es la cascada de ADR-002;
                `_acotar_contra_nivel` pasa `NIVELES_CONTRASTE`, que excluye al IPC.

        Returns:
            `(factor, nivel_usado)`, ambos alineados al índice de `pares`. Un `NaN` en el
            factor significa que **ningún** peldaño pudo responder.
        """
        factor = pd.Series(np.nan, index=pares.index, dtype="float64")
        nivel_usado = pd.Series(None, index=pares.index, dtype="object")

        for nivel in niveles:
            pendientes = factor.isna()
            if not pendientes.any():
                break

            id_nivel = self._id_de_nivel(pares.loc[pendientes], nivel)
            if id_nivel is None:
                continue

            serie = self.indices_[self.indices_["nivel"] == nivel]
            if serie.empty:
                continue
            tabla = serie.set_index(["id_nivel", "anio_mes"])["indice"]

            desde = tabla.reindex(
                pd.MultiIndex.from_arrays([id_nivel, pares.loc[pendientes, "mes_desde"]])
            ).to_numpy()
            hasta = tabla.reindex(
                pd.MultiIndex.from_arrays([id_nivel, pares.loc[pendientes, "mes_hasta"]])
            ).to_numpy()

            with np.errstate(divide="ignore", invalid="ignore"):
                candidato = np.where(desde > 0, hasta / desde, np.nan)

            resuelto = pd.Series(candidato, index=pares.index[pendientes])
            factor[pendientes] = resuelto
            nivel_usado[pendientes & factor.notna()] = nivel

        return factor, nivel_usado

    def _id_de_nivel(self, pares: pd.DataFrame, nivel: str) -> np.ndarray | None:
        if nivel == "ipc":
            return np.full(len(pares), ID_NIVEL_IPC, dtype="object")
        if self.catalogo is None or nivel not in self.catalogo.columns:
            return None
        mapa = self.catalogo.set_index("id_producto")[nivel]
        return mapa.reindex(pares["id_producto"]).to_numpy()

    # -------------------------------------------------------------- aplicación

    def transformar(self, hechos: pd.DataFrame, columna: str = "revenue") -> pd.DataFrame:
        """Agrega `<columna>_real`: el monto llevado a pesos del corte.

        Sirve igual para `hecho_venta_mensual_producto` y para el grano
        cliente×producto — es el mismo deflactor por (producto, mes), y aplicarlo sobre el
        revenue observado del cliente es exactamente lo que preserva su descuento.

        Las filas sin deflactor quedan en `NaN` y **no se descartan**: la cobertura tiene
        que ser visible, no silenciosa (misma lección que el piso de M1.8).
        """
        salida = hechos.merge(self.deflactor_, on=["id_producto", "anio_mes"], how="left")
        salida[f"{columna}_real"] = salida[columna] * salida["deflactor"]
        return salida.drop(columns="deflactor")

    @property
    def cobertura_(self) -> pd.Series:
        """Productos por peldaño que resolvió su ancla. El reporte de M2.1."""
        return self.origen_ancla_.value_counts()
