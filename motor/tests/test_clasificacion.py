"""Tests del clasificador Syntetos-Boylan (M1.4).

Este código no tenía ni un test cuando vivía en `datasets/sintetico/`, y decidía el gate
de calibración del generador. Su corrección se había verificado a mano; acá queda fijada.
"""

import numpy as np
import pandas as pd
import pytest

from motor.backtesting.cortes import generar_cortes
from motor.backtesting.leakage import verificar_sin_leakage
from motor.clasificacion import (
    ADI_UMBRAL,
    CV2_UMBRAL,
    SIN_ACTIVIDAD,
    clasificar_serie,
    clasificar_series,
    distribucion_cuadrantes,
    etiquetar,
)

# ---------------------------------------------------------------------------------
# El núcleo: los cuatro cuadrantes, calculados a mano
# ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("nombre", "serie", "cuadrante"),
    [
        # vende todos los meses, cantidad estable -> ADI 1, CV2 0
        ("densa estable", [10.0, 10.0, 10.0, 10.0], "suave"),
        # vende todos los meses, cantidad muy variable -> ADI 1, CV2 alto
        ("densa variable", [1.0, 50.0, 1.0, 50.0], "erratica"),
        # una venta cada 4 meses, cantidad estable -> ADI 4, CV2 0
        ("rala estable", [10.0, 0, 0, 0, 10.0, 0, 0, 0], "intermitente"),
        # rala Y variable -> el cuadrante más difícil de predecir
        ("rala variable", [1.0, 0, 0, 0, 90.0, 0, 0, 0], "lumpy"),
    ],
)
def test_los_cuatro_cuadrantes(nombre, serie, cuadrante):
    assert clasificar_serie(np.array(serie))[0] == cuadrante, nombre


def test_adi_y_cv2_coinciden_con_el_calculo_a_mano():
    serie = np.array([1.0, 0, 0, 0, 90.0, 0, 0, 0])
    no_cero = serie[serie > 0]

    _, adi, cv2 = clasificar_serie(serie)

    assert adi == pytest.approx(8 / 2)  # 8 periodos / 2 demandas
    assert cv2 == pytest.approx((no_cero.std(ddof=0) / no_cero.mean()) ** 2)


def test_serie_sin_demanda(nombre="todo cero"):
    cuadrante, adi, cv2 = clasificar_serie(np.zeros(6))

    assert cuadrante == SIN_ACTIVIDAD
    assert np.isinf(adi)
    assert np.isnan(cv2)


def test_una_sola_demanda_cae_en_intermitente_no_en_lumpy():
    """Propiedad conocida de la taxonomía con muestras mínimas: una observación no tiene
    dispersión, así que CV²=0. Se fija acá para que no se lea como un bug más adelante,
    sobre todo a nivel cliente×producto donde es el caso más común (EDA §5)."""
    cuadrante, adi, cv2 = clasificar_serie(np.array([0.0, 0.0, 7.0, 0.0]))

    assert cv2 == 0.0
    assert cuadrante == "intermitente"
    assert adi == pytest.approx(4.0)


@pytest.mark.parametrize(
    ("adi_alto", "cv2_alto", "cuadrante"),
    [(False, False, "suave"), (True, False, "intermitente"), (False, True, "erratica"),
     (True, True, "lumpy")],
)
def test_los_umbrales_parten_los_cuadrantes_donde_se_espera(adi_alto, cv2_alto, cuadrante):
    """Construye series que caen justo a cada lado de los umbrales, para que un cambio
    accidental de `ADI_UMBRAL`/`CV2_UMBRAL` rompa acá y no en silencio."""
    # ADI: 12 periodos con 12 demandas -> 1.0 (< 1.32) | con 8 demandas -> 1.5 (>= 1.32)
    n_demandas = 8 if adi_alto else 12
    # CV2: valores iguales -> 0 | mezcla 1/9 -> 0.64
    valores = [1.0, 9.0] * (n_demandas // 2) if cv2_alto else [5.0] * n_demandas
    serie = np.array(valores + [0.0] * (12 - n_demandas))

    resultado, adi, cv2 = clasificar_serie(serie)

    # `bool()` explícito: numpy devuelve np.True_, que no es idéntico a True
    assert bool(adi >= ADI_UMBRAL) is adi_alto
    assert bool(cv2 >= CV2_UMBRAL) is cv2_alto
    assert resultado == cuadrante


# ---------------------------------------------------------------------------------
# Sobre una tabla: densificación, ventana y regla de ADR-010
# ---------------------------------------------------------------------------------


def _tabla(filas: list[tuple]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"id_producto": p, "anio_mes": pd.Timestamp(m), "unidades": u} for p, m, u in filas]
    )


def test_densifica_los_meses_sin_fila():
    """La tabla de hechos es dispersa: si el clasificador no densifica, toda serie da
    ADI=1 y la intermitencia se vuelve indetectable."""
    datos = _tabla([(1, "2025-01-01", 10.0), (1, "2025-05-01", 10.0), (1, "2025-09-01", 10.0)])

    resultado = clasificar_series(datos, ventana_meses=9)

    assert resultado["adi"].iloc[0] == pytest.approx(3.0)  # 9 meses / 3 demandas
    assert resultado["cuadrante"].iloc[0] == "intermitente"


def test_producto_nuevo_se_clasifica_desde_su_primera_venta(caplog):
    """Regla de ADR-010. El producto vende **todos** los meses desde que existe (3 de 3),
    así que es suave. Contar los 33 meses previos de la ventana como ceros le daría
    ADI=12 y lo etiquetaría intermitente — el error que esta regla evita, y que pega
    justo en los productos nuevos, los que más incertidumbre tienen."""
    datos = _tabla(
        [(1, "2026-04-01", 10.0), (1, "2026-05-01", 11.0), (1, "2026-06-01", 12.0)]
    )

    resultado = clasificar_series(datos, hasta=pd.Timestamp("2026-06-01"), ventana_meses=36)

    assert resultado["adi"].iloc[0] == pytest.approx(1.0)
    assert resultado["cuadrante"].iloc[0] == "suave"


def test_los_ceros_de_cola_si_cuentan():
    """Simétrico al anterior: un producto que dejó de venderse **sí** acumula ceros hasta
    el final de la ventana. Es lo que permite detectar obsolescencia (para eso existe TSB
    en M1.6); recortar en la última venta la esconde."""
    datos = _tabla([(1, "2024-01-01", 10.0), (1, "2024-02-01", 10.0), (1, "2024-03-01", 10.0)])

    resultado = clasificar_series(datos, hasta=pd.Timestamp("2024-12-01"), ventana_meses=12)

    assert resultado["adi"].iloc[0] == pytest.approx(12 / 3)
    assert resultado["cuadrante"].iloc[0] == "intermitente"


def test_un_producto_viejo_sin_ventas_al_inicio_de_la_ventana_cuenta_esos_ceros():
    """La distinción fina de ADR-010: la primera venta se busca en **toda la historia**,
    no dentro de la ventana. Este producto existe desde 2020, y su silencio en los
    primeros meses de la ventana es demanda cero real — no "todavía no existía".

    Salió de validar a escala: buscando la primera venta dentro de la ventana, 4 de 2.300
    productos del sintético se reclasificaban mal.
    """
    datos = _tabla(
        [(1, "2020-01-01", 10.0)]  # existe desde mucho antes de la ventana
        + [(1, f"2026-{m:02d}-01", 10.0) for m in (4, 5, 6)]
    )

    resultado = clasificar_series(datos, hasta=pd.Timestamp("2026-06-01"), ventana_meses=12)

    # 12 meses de ventana / 3 demandas -> intermitente, no suave
    assert resultado["adi"].iloc[0] == pytest.approx(4.0)
    assert resultado["cuadrante"].iloc[0] == "intermitente"


def test_solo_mira_la_ventana_pedida():
    datos = _tabla(
        [(1, "2020-01-01", 999.0)] + [(1, f"2026-{m:02d}-01", 10.0) for m in (4, 5, 6)]
    )

    resultado = clasificar_series(datos, hasta=pd.Timestamp("2026-06-01"), ventana_meses=3)

    assert resultado["adi"].iloc[0] == pytest.approx(1.0)


def test_clasifica_cada_serie_por_separado():
    datos = _tabla(
        [(1, f"2026-{m:02d}-01", 10.0) for m in (1, 2, 3, 4, 5, 6)]
        + [(2, "2026-01-01", 1.0), (2, "2026-06-01", 90.0)]
    )

    resultado = clasificar_series(datos, hasta=pd.Timestamp("2026-06-01"), ventana_meses=6)

    por_producto = resultado.set_index("id_producto")["cuadrante"]
    assert por_producto[1] == "suave"
    assert por_producto[2] == "lumpy"


def test_admite_series_de_clave_compuesta():
    """Nivel cliente×producto, que es lo que necesita M3.2."""
    datos = pd.DataFrame(
        [
            {"id_cliente": c, "id_producto": 1, "anio_mes": pd.Timestamp(m), "unidades": 10.0}
            for c in (1, 2)
            for m in ("2026-01-01", "2026-02-01", "2026-03-01")
        ]
    )

    resultado = clasificar_series(datos, columnas_id=["id_cliente", "id_producto"])

    assert set(resultado.columns) >= {"id_cliente", "id_producto", "cuadrante"}
    assert len(resultado) == 2


# ---------------------------------------------------------------------------------
# Distribución y etiquetado del reporte
# ---------------------------------------------------------------------------------


def test_la_distribucion_excluye_sin_actividad():
    """`sin_actividad` no es un cuadrante: es ausencia de señal. Si entrara al
    denominador, los porcentajes no serían comparables con los del EDA, que se calcularon
    sobre productos activos."""
    clasificacion = pd.DataFrame(
        {"id_producto": [1, 2, 3, 4], "cuadrante": ["suave", "suave", "lumpy", SIN_ACTIVIDAD]}
    )

    distribucion = distribucion_cuadrantes(clasificacion)

    assert SIN_ACTIVIDAD not in distribucion
    assert distribucion["suave"] == pytest.approx(200 / 3)


def test_etiquetar_no_deja_nulos_que_rompan_las_metricas():
    """Las métricas cortan ante nulos en una columna de agrupación (defecto 6). Una serie
    sin clasificar tiene que quedar visible como `sin_actividad`, no como NaN."""
    reporte = pd.DataFrame({"id_producto": [1, 2], "real": [1.0, 2.0], "pred": [1.0, 2.0]})
    clasificacion = pd.DataFrame({"id_producto": [1], "cuadrante": ["suave"], "adi": [1.0],
                                  "cv2": [0.0]})

    etiquetado = etiquetar(reporte, clasificacion)

    assert etiquetado["cuadrante"].notna().all()
    assert set(etiquetado["cuadrante"]) == {"suave", SIN_ACTIVIDAD}


def test_etiquetar_conserva_la_trazabilidad_de_la_corrida():
    """El merge descarta `.attrs`, y ahí viaja la `Corrida`. Si se perdiera, el reporte
    saldría anónimo y `a_markdown()` lo marcaría como no congelable."""
    reporte = pd.DataFrame({"id_producto": [1], "real": [1.0], "pred": [1.0]})
    reporte.attrs["corrida"] = "sentinela"

    etiquetado = etiquetar(reporte, pd.DataFrame({"id_producto": [1], "cuadrante": ["suave"]}))

    assert etiquetado.attrs["corrida"] == "sentinela"


# ---------------------------------------------------------------------------------
# Integración con la red anti-leakage (M1.3)
# ---------------------------------------------------------------------------------


@pytest.mark.innegociable
def test_clasificar_con_corte_no_mira_el_futuro():
    """El cuadrante decide **qué método de forecast** se le aplica a la serie (M1.5/M1.6).
    Si se clasificara con datos posteriores al corte, el modelo elegiría su método con
    información del futuro. Se verifica con la red de M1.3, que es justo para esto."""
    meses = pd.date_range("2023-01-01", periods=42, freq="MS")
    datos = pd.DataFrame(
        [
            {"id_producto": p, "anio_mes": m, "unidades": float((i % (p + 1) == 0) * (10 + i))}
            for p in (1, 2, 3)
            for i, m in enumerate(meses)
        ]
    )
    datos = datos[datos["unidades"] > 0]  # dispersa, como la tabla real

    verificar_sin_leakage(
        lambda d, corte: clasificar_series(d, hasta=corte),
        datos=datos,
        cortes=generar_cortes(datos["anio_mes"], n_cortes=3),
    )
