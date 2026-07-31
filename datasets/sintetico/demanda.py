"""Simulación de demanda: serie mensual por producto (con rechazo/resorteo para calibrar
el cuadrante Syntetos-Boylan) y reparto estocástico entre un pool de clientes elegibles.

Es top-down por diseño: el arquetipo fija la serie del producto (y se verifica contra el
mismo clasificador que usa el EDA); recién después esa serie se reparte entre clientes.
Así el cuadrante de producto queda exactamente calibrado, y la intermitencia a nivel
cliente×producto (EDA §5) emerge del reparto sin pelearse con el objetivo del producto.
"""

import numpy as np
import pandas as pd

from . import parametros as P
from .clasificacion import clasificar_serie


def simular_serie_producto(
    rng: np.random.Generator,
    arquetipo: str,
    tamanio_base: float,
    sin_ancla_propia: bool,
    n_meses: int = P.N_MESES,
    ventana: int = P.VENTANA_INTERMITENCIA_MESES,
    mes_alta: int = 0,
    mes_baja: int | None = None,
) -> np.ndarray:
    """Serie de 96 meses cuya ventana de clasificación cae en el cuadrante `arquetipo`
    (rechazo/resorteo hasta MAX_INTENTOS_CALIBRACION_PRODUCTO; si no calibra, se queda
    con el último intento — el efecto agregado sobre ±3 puntos es despreciable).

    El producto solo puede vender en `[mes_alta, mes_baja)` (T0.4 #3). Fuera de ahí la
    serie es cero, pero **son ceros de distinta naturaleza**: los previos al alta son meses
    en que el producto no existía y ADR-010 los excluye; los posteriores a la baja son
    demanda cero de verdad.
    """
    p_min, p_max = P.RANGO_P_OCURRENCIA[arquetipo]
    sigma_min, sigma_max = P.RANGO_SIGMA_TAMANIO[arquetipo]
    estacional = 1 + 0.15 * np.sin(2 * np.pi * (np.arange(n_meses) % 12) / 12)

    fin_vida = n_meses if mes_baja is None else min(int(mes_baja), n_meses)
    inicio, fin = _ventana_de_calibracion(int(mes_alta), fin_vida, ventana)

    serie = None
    for _ in range(P.MAX_INTENTOS_CALIBRACION_PRODUCTO):
        p_occ = rng.uniform(p_min, p_max)
        sigma = rng.uniform(sigma_min, sigma_max)
        ocurre = rng.random(n_meses) < p_occ
        ocurre[:mes_alta] = False
        ocurre[fin_vida:] = False
        if sin_ancla_propia and fin_vida - mes_alta > P.MESES_SIN_ANCLA:
            ocurre[fin_vida - P.MESES_SIN_ANCLA : fin_vida] = False
        ruido = rng.lognormal(mean=-0.5 * sigma**2, sigma=sigma, size=n_meses)
        serie = np.where(ocurre, tamanio_base * estacional * ruido, 0.0)

        cuadrante, _, _ = clasificar_serie(serie[inicio:fin])
        if cuadrante == arquetipo:
            return serie
    return serie


def _ventana_de_calibracion(mes_alta: int, fin_vida: int, ventana: int) -> tuple[int, int]:
    """Tramo sobre el que el bucle de rechazo verifica el cuadrante.

    **No es `serie[-ventana:]`, y la diferencia es el bug que este cambio arregla.** El
    motor clasifica con `clasificar_series`, que aplica la regla de calendario de ADR-010:
    la ventana de una serie arranca en su primera venta, no 36 meses antes del final. Un
    producto nacido hace 10 meses medido sobre `serie[-36:]` arrastra 26 ceros que nunca
    existieron, lo que le infla el ADI y lo calibra como intermitente — mientras el motor,
    midiéndolo sobre 10 meses, lo vería suave. **El generador y el motor dirían cosas
    distintas sobre la misma serie**, que es justo lo que el clasificador compartido existe
    para impedir (ver `clasificacion.py`). Compartir el código no alcanza si se lo llama con
    la ventana equivocada.

    Por el mismo motivo la ventana termina en la baja y no en el final del calendario: una
    serie muerta hace 30 meses es todo ceros en los últimos 36 y clasificaría
    `sin_actividad`, así que el bucle nunca acertaría el arquetipo y quemaría los 40
    intentos para devolver una serie sin calibrar.
    """
    return max(mes_alta, fin_vida - ventana), fin_vida


def repartir_entre_clientes(
    rng: np.random.Generator,
    serie_producto: np.ndarray,
    clientes_df: pd.DataFrame,
    arquetipo: str,
) -> pd.DataFrame:
    """Reparte cada mes de `serie_producto` entre un subconjunto de un pool de clientes
    elegibles para ese producto (tamaño de pool correlacionado con el arquetipo — EDA §5:
    productos lumpy los compran pocos clientes; suaves, muchos)."""
    pool_min, pool_max = P.RANGO_POOL_CLIENTES[arquetipo]
    n_pool = min(int(rng.integers(pool_min, pool_max + 1)), len(clientes_df))

    pesos = clientes_df["peso"].to_numpy()
    idx_pool = rng.choice(len(clientes_df), size=n_pool, replace=False, p=pesos / pesos.sum())
    ids_pool = clientes_df["id_cliente"].to_numpy()[idx_pool]
    pesos_pool = pesos[idx_pool]

    # Probabilidad mensual de participar por cliente — lognormal de cola larga: la mayoría
    # de los pares cliente×producto compran casi nunca, unos pocos compran regularmente
    # (EDA §5: 53,5% de los pares con ≤2 meses en 36; solo ~12% con ≥12 meses de señal).
    # mu/sigma calibrados por barrido de grilla contra la distribución real (ver manifiesto).
    p_cliente = np.clip(rng.lognormal(mean=-4.0, sigma=2.0, size=n_pool), 1e-4, 0.97)

    filas = []
    for mes_idx, unidades_mes in enumerate(serie_producto):
        if unidades_mes <= 0:
            continue
        participa = rng.random(n_pool) < p_cliente
        if not participa.any():
            participa[rng.integers(n_pool)] = True  # el producto vendió: alguien compró

        pesos_participantes = pesos_pool[participa]
        n_participantes = int(participa.sum())
        shares = rng.dirichlet(np.full(n_participantes, 2.0)) if n_participantes > 1 else np.array([1.0])
        shares = shares * pesos_participantes
        shares = shares / shares.sum()

        unidades_cliente = unidades_mes * shares
        for id_cliente, unidades in zip(ids_pool[participa], unidades_cliente):
            filas.append({"id_cliente": int(id_cliente), "mes_idx": mes_idx, "unidades": float(unidades)})

    return pd.DataFrame(filas, columns=["id_cliente", "mes_idx", "unidades"])
