"""Calibración de los intervalos del modelo global (M2.4): ¿el P10–P90 cubre el 80%?

Corre el global con `cuantiles=(0.1, 0.5, 0.9)` dentro del arnés y congela la tabla de
calibración en `motor/backtests/`. El gate de la unidad es **reportar la cobertura empírica**
del P10–P90 contra su 80% nominal, desagregada por horizonte y por cuadrante; ADR-015 punto 2
convierte ese número en el compromiso del producto para h=6/h=12, donde el pronóstico puntual
tiene demasiada varianza para prometerse como número.

    motor/.venv/Scripts/python motor/scripts/intervalos_global.py --estratificado 100
    motor/.venv/Scripts/python motor/scripts/intervalos_global.py \
        --hechos C:/dfv-extract-v2 --etiqueta real --estratificado 0 \
        --checkpoint-dir C:/dfv-checkpoints-intervalos

⚠️ **Directorio de checkpoints propio, no el de las ablaciones.** El `id` de corrida es hash
de configuración + datos y **no incluye el predictor** (`corrida.py`), así que esta corrida
tiene el mismo `id` que las de M2.3 y reusaría sus checkpoints — que no tienen las columnas de
cuantil— sin avisar. Es la misma trampa que documenta `ablaciones_global.py`.

**Costo:** tres cuantiles son tres modelos más **por horizonte**, o sea 48 ajustes por corte
contra los 12 de M2.3.

**Control cruzado que conviene mirar:** la tabla trae también el WAPE del pronóstico puntual.
Tiene que dar **idéntico** al de la corrida de M2.3 (`ablaciones-global-real-2026-08-06.md`,
variante `precio+crudo`): los cuantiles se agregan al mismo `MLForecast` y no tocan el modelo
de media. Si difiere, algo cambió en los datos o en las features y la comparación con el piso
dejó de ser válida.
"""

import argparse
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from motor.backtesting.arnes import ejecutar_backtest
from motor.backtesting.intervalos import COBERTURA_NOMINAL
from motor.backtesting.reporte import a_markdown, construir_reporte
from motor.clasificacion import clasificar_series, etiquetar, muestra_estratificada
from motor.datos.archivos import RepositorioArchivos
from motor.modelado.modelo_global import (
    CUANTILES_ESTANDAR,
    NOMBRE_MODELO,
    cobertura_esperada,
    nombre_de_cuantil,
    predecir_global,
)

RAIZ_REPO = Path(__file__).resolve().parents[2]
HECHOS_SINTETICO = RAIZ_REPO / "datasets" / "sintetico" / "salida" / "hechos"
BACKTESTS = RAIZ_REPO / "motor" / "backtests"


def parsear_argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--hechos", type=Path, default=HECHOS_SINTETICO)
    parser.add_argument("--etiqueta", default="sintetico")
    parser.add_argument("--n-cortes", type=int, default=18)
    parser.add_argument("--horizonte-max", type=int, default=12)
    parser.add_argument(
        "--estratificado",
        type=int,
        default=100,
        help="Productos POR CUADRANTE. 0 corre el catálogo completo, que es lo que "
        "corresponde para la tabla real.",
    )
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument(
        "--usar-dispersion",
        action="store_true",
        help="M3.0: agrega desvio movil y CV. Exige --checkpoint-dir PROPIO, porque el "
        "`id` de corrida no incluye las features y reanudaria checkpoints sin ellas.",
    )
    parser.add_argument("--checkpoint-dir", type=Path, default=None)
    parser.add_argument("--salida-dir", type=Path, default=BACKTESTS)
    return parser.parse_args(argv)


def _columnas_cuantil() -> dict[float, str]:
    return {q: nombre_de_cuantil(q) for q in CUANTILES_ESTANDAR}


def main(argv: list[str] | None = None) -> int:
    args = parsear_argumentos(argv)
    if not args.hechos.exists():
        print(
            f"No hay hechos en {args.hechos}. Si es el sintético, regeneralo por semilla "
            "(ver motor/README.md §Arranque desde cero).",
            file=sys.stderr,
        )
        return 1

    repo = RepositorioArchivos(args.hechos)
    hechos = repo.hecho_venta_mensual_producto()
    catalogo = repo.catalogo_producto()

    productos_totales = hechos["id_producto"].nunique()
    conteo_cuadrantes: dict[str, int] = {}
    if args.estratificado:
        hechos, conteo_cuadrantes = muestra_estratificada(hechos, args.estratificado, args.semilla)

    print(
        f"Global con cuantiles {CUANTILES_ESTANDAR} sobre "
        f"{hechos['id_producto'].nunique()} productos x {args.n_cortes} cortes "
        f"(h={args.horizonte_max})",
        flush=True,
    )

    inicio = time.perf_counter()
    reporte = ejecutar_backtest(
        hechos,
        lambda h, c, hm, aux: predecir_global(
            h, c, hm, aux, cuantiles=CUANTILES_ESTANDAR, usar_dispersion=args.usar_dispersion
        ),
        n_cortes=args.n_cortes,
        horizonte_max=args.horizonte_max,
        tablas_auxiliares={"catalogo": catalogo},
        directorio_checkpoint=args.checkpoint_dir,
    )
    duracion = time.perf_counter() - inicio
    print(f"  {duracion / 60:.1f} min", flush=True)

    # `.attrs` se pierde en merge/rename (§12.2): se toma antes de transformar, o la tabla
    # sale sin `id` de corrida y deja de ser congelable.
    corrida = reporte.attrs.get("corrida")
    reporte = etiquetar(reporte, clasificar_series(hechos))
    if "categoria" in catalogo.columns:
        reporte = reporte.merge(
            catalogo[["id_producto", "categoria"]].drop_duplicates("id_producto"),
            on="id_producto",
            how="left",
        )
    reporte.attrs["corrida"] = corrida

    tablas = construir_reporte(
        reporte, columna_pred=NOMBRE_MODELO, columnas_cuantil=_columnas_cuantil()
    )

    fecha = datetime.now(tz=UTC).date().isoformat()
    md = a_markdown(
        tablas,
        titulo=f"Calibración de intervalos del modelo global — {args.etiqueta} ({fecha})",
        notas=_notas(args, hechos, productos_totales, conteo_cuadrantes, duracion),
    )
    args.salida_dir.mkdir(parents=True, exist_ok=True)
    destino = args.salida_dir / f"intervalos-global-{args.etiqueta}-{fecha}.md"
    destino.write_text(md, encoding="utf-8")
    print(f"\nEscrito: {destino}")
    return 0


def _notas(
    args: argparse.Namespace,
    hechos: pd.DataFrame,
    productos_totales: int,
    conteo_cuadrantes: dict[str, int],
    duracion: float,
) -> str:
    cuantiles = ", ".join(nombre_de_cuantil(q) for q in CUANTILES_ESTANDAR)
    lineas = [
        f"Modelo global LightGBM (`{NOMBRE_MODELO}`) con regresión cuantílica: {cuantiles}. "
        f"Configuración `precio+crudo`, la que eligió la ablación de M2.3"
        + (" **+ features de dispersión (M3.0)**." if args.usar_dispersion else "."),
        "",
        f"- **Productos:** {hechos['id_producto'].nunique()} de {productos_totales} · "
        f"**cortes:** {args.n_cortes} · **horizonte:** {args.horizonte_max} · "
        f"**{duracion / 60:.1f} min**",
        f"- **Cobertura nominal del P10–P90:** {COBERTURA_NOMINAL:.2f}. `desvio_vs_nominal` "
        "es la empírica menos ese valor, **con signo**: negativo es sub-cobertura (el "
        "intervalo promete menos riesgo del que hay) y positivo es un intervalo más ancho "
        "de lo necesario. No son el mismo error.",
        f"- **Cobertura esperada por longitud de serie:** {cobertura_esperada(hechos):.4f} — "
        "cota superior de la cobertura del global (`mlforecast` descarta las series sin lags "
        "completos), así que una `cobertura` baja en la tabla no es necesariamente del modelo.",
        "- **Por qué la `cobertura` no es 1,0** (regla 4 de `backtests/README.md`): son las "
        "**altas de catálogo** de `roadmap-motor.md` §5.6.1 — productos cuya primera venta es "
        "posterior al corte, que ni los baselines ni el global pueden predecir porque no "
        "existen al momento de entrenar. Son **las mismas filas** que en el piso prospectivo "
        "y en las ablaciones de M2.3 (§6.5 punto 4 lo verificó fila a fila), así que las tres "
        "tablas se comparan a igual cobertura.",
    ]
    if conteo_cuadrantes:
        detalle = " · ".join(f"{c}: {n}" for c, n in sorted(conteo_cuadrantes.items()))
        lineas += [
            f"- **Muestreo:** estratificado, hasta {args.estratificado} por cuadrante, "
            f"semilla {args.semilla} → {detalle}",
        ]
    lineas += [
        "",
        "> **El intervalo se mide a grano producto, que es donde se predice.** No hay "
        "cobertura por categoría ni total: **la suma de cuantiles no es el cuantil de la "
        "suma** — sumar los P90 de todo el catálogo supone que a todos los productos les va "
        "bien el mismo mes y da un rango absurdamente ancho. Un intervalo agregado hay que "
        "predecirlo a esa altura de la jerarquía (M3.1). Los cortes por cuadrante y por "
        "categoría de abajo son desagregados del **mismo** grano producto, que es otra cosa.",
        "",
        "> **El intervalo se evalúa cerrado** (`P10 <= real <= P90`). Con 42% de series "
        "intermitentes y el panel densificado a ceros (ADR-010), la fila más frecuente es "
        "`real == 0` con `P10 == 0`, y ese es un acierto: el modelo dijo que bien podía no "
        "venderse nada.",
    ]
    if args.etiqueta == "sintetico":
        lineas += [
            "",
            "> **El sintético no valida calibración.** La dispersión de estas series la puso "
            "el generador, así que la cobertura empírica de acá mide contra el ruido "
            "sintético, no contra la incertidumbre del negocio. Sirve para verificar que el "
            "pipeline corre y que las métricas se calculan; el número que vale es el de la "
            "corrida real.",
        ]
    return "\n".join(lineas)


if __name__ == "__main__":
    raise SystemExit(main())
