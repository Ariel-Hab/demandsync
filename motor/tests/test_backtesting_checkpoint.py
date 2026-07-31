"""Tests del checkpointing del arnés (M1.7a).

Existe porque las corridas de M1.7/M1.8 son de horas con el pool de procesos al límite de
memoria: si mueren a mitad de camino, sin checkpoint no queda nada. Los tres focos son
(1) que cada corte quede persistido, (2) que reanudar **no vuelva a llamar al predictor**
para los cortes ya hechos y devuelva el mismo reporte, y (3) que reanudar con otra
configuración **falle** en vez de mezclar checkpoints ajenos — que es la forma en que este
tipo de caché arruina un resultado sin avisar.
"""

import json

import pandas as pd
import pytest

from motor.backtesting.arnes import MANIFIESTO_CHECKPOINT, ejecutar_backtest


@pytest.fixture
def datos_un_producto():
    return pd.DataFrame(
        {
            "id_producto": [1] * 10,
            "anio_mes": pd.date_range("2025-01-01", periods=10, freq="MS"),
            "unidades": [float(10 + i) for i in range(10)],
        }
    )


def predictor_naive(
    historia: pd.DataFrame, corte: pd.Timestamp, horizonte_max: int
) -> pd.DataFrame:
    ultimo = (
        historia.sort_values("anio_mes")
        .groupby("id_producto", as_index=False)
        .tail(1)[["id_producto", "unidades"]]
        .rename(columns={"unidades": "pred_naive"})
    )
    fechas = pd.date_range(corte + pd.DateOffset(months=1), periods=horizonte_max, freq="MS")
    return ultimo.merge(pd.DataFrame({"anio_mes": fechas}), how="cross")


def test_escribe_un_parquet_por_corte_y_el_manifiesto(datos_un_producto, tmp_path):
    reporte = ejecutar_backtest(
        datos_un_producto, predictor_naive, n_cortes=3, horizonte_max=2,
        directorio_checkpoint=tmp_path,
    )

    parquets = sorted(p.name for p in tmp_path.glob("*.parquet"))
    assert len(parquets) == 3, f"un parquet por corte, se encontraron: {parquets}"

    manifiesto = json.loads((tmp_path / MANIFIESTO_CHECKPOINT).read_text(encoding="utf-8"))
    assert manifiesto["id"] == reporte.attrs["corrida"].id


def test_reanudar_no_vuelve_a_predecir_y_da_el_mismo_reporte(datos_un_producto, tmp_path):
    primera = ejecutar_backtest(
        datos_un_producto, predictor_naive, n_cortes=3, horizonte_max=2,
        directorio_checkpoint=tmp_path,
    )

    def predictor_que_no_debe_correr(historia, corte, horizonte_max):
        raise AssertionError(f"el corte {corte.date()} ya tenía checkpoint: no se repredice")

    segunda = ejecutar_backtest(
        datos_un_producto, predictor_que_no_debe_correr, n_cortes=3, horizonte_max=2,
        directorio_checkpoint=tmp_path,
    )

    pd.testing.assert_frame_equal(primera, segunda)


def test_reanudar_a_medias_solo_predice_los_cortes_que_faltan(datos_un_producto, tmp_path):
    """El caso real: la corrida murió después de algunos cortes. Se simula corriendo
    primero con menos cortes y después con todos, sobre el mismo directorio."""
    completa = ejecutar_backtest(
        datos_un_producto, predictor_naive, n_cortes=3, horizonte_max=2,
        directorio_checkpoint=tmp_path / "completa",
    )

    parcial_dir = tmp_path / "parcial"
    ejecutar_backtest(
        datos_un_producto, predictor_naive, n_cortes=3, horizonte_max=2,
        directorio_checkpoint=parcial_dir,
    )
    # se borra el checkpoint del último corte, como si la corrida hubiese muerto ahí
    ultimo = sorted(parcial_dir.glob("*.parquet"))[-1]
    ultimo.unlink()

    cortes_predichos = []

    def predictor_contador(historia, corte, horizonte_max):
        cortes_predichos.append(corte)
        return predictor_naive(historia, corte, horizonte_max)

    reanudada = ejecutar_backtest(
        datos_un_producto, predictor_contador, n_cortes=3, horizonte_max=2,
        directorio_checkpoint=parcial_dir,
    )

    assert len(cortes_predichos) == 1, "solo debía recalcularse el corte borrado"
    pd.testing.assert_frame_equal(completa, reanudada)


def test_checkpoint_de_otra_configuracion_es_rechazado(datos_un_producto, tmp_path):
    """La guarda que hace seguro el resto: sin ella, reanudar con otro horizonte leería
    checkpoints ajenos y devolvería un reporte mezclado con cara de válido."""
    ejecutar_backtest(
        datos_un_producto, predictor_naive, n_cortes=3, horizonte_max=2,
        directorio_checkpoint=tmp_path,
    )

    with pytest.raises(ValueError, match="cambió la configuración o los datos"):
        ejecutar_backtest(
            datos_un_producto, predictor_naive, n_cortes=3, horizonte_max=4,
            directorio_checkpoint=tmp_path,
        )


def test_checkpoint_de_otros_datos_es_rechazado(datos_un_producto, tmp_path):
    """Misma configuración pero datos distintos: el `id` de corrida es hash de config
    **más huella de datos**, así que también tiene que rechazarse."""
    ejecutar_backtest(
        datos_un_producto, predictor_naive, n_cortes=3, horizonte_max=2,
        directorio_checkpoint=tmp_path,
    )
    otros_datos = datos_un_producto.assign(unidades=datos_un_producto["unidades"] * 2)

    with pytest.raises(ValueError, match="cambió la configuración o los datos"):
        ejecutar_backtest(
            otros_datos, predictor_naive, n_cortes=3, horizonte_max=2,
            directorio_checkpoint=tmp_path,
        )


def test_sin_directorio_no_escribe_nada(datos_un_producto, tmp_path):
    """El default está apagado: el comportamiento de M1.1 no cambia."""
    ejecutar_backtest(datos_un_producto, predictor_naive, n_cortes=3, horizonte_max=2)

    assert list(tmp_path.iterdir()) == []
