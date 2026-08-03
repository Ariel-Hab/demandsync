"""Genera la tabla de referencia de baselines sobre el dataset sintético (M1.7).

Entregable de M1.7: `motor/backtests/baselines-sintetico-<AAAA-MM-DD>.md`, con las
cuatro condiciones que `motor/backtests/README.md` exige para que una tabla sea
congelable (id de corrida, desagregado por horizonte × nivel, por cuadrante, y la
columna `cobertura`).

    # corrida completa (lenta — ver --n-jobs y la nota de costo del README de modelado)
    motor/.venv/Scripts/python motor/scripts/congelar_baselines_sintetico.py --n-jobs 14

    # smoke test rápido antes de largar la de verdad
    motor/.venv/Scripts/python motor/scripts/congelar_baselines_sintetico.py \
        --n-productos 40 --n-cortes 13 --n-jobs 14

Esta carpeta **no** es parte del paquete `motor` (igual que `ejemplos/`): son scripts de
operación del track, no código que importe el job batch. Lo que sí vive en el paquete es
toda la lógica — este archivo solo orquesta `motor.modelado.seleccion` +
`motor.backtesting`, para que M1.8 corra exactamente el mismo camino sobre el extract
real cambiando únicamente la ruta de los datos.

**Sobre M1.8:** este script es el ensayo del piso real. Cuando se corra en la máquina
autorizada, la única diferencia debe ser `--hechos` apuntando al extract y el nombre del
archivo de salida (`baselines-real-<fecha>.md`). Si hiciera falta cambiar algo más, eso
mismo es un hallazgo que va al roadmap.
"""

import argparse
import functools
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from motor.backtesting.arnes import ejecutar_backtest
from motor.backtesting.reporte import a_markdown, construir_reporte
from motor.clasificacion import SIN_ACTIVIDAD, clasificar_series, etiquetar
from motor.datos.archivos import RepositorioArchivos
from motor.modelado.seleccion import (
    CANDIDATOS,
    armar_reporte_seleccionado,
    elegir_mejor_por_serie,
    predecir_todos_los_candidatos,
    resumen_de_ganadores,
)

RAIZ_REPO = Path(__file__).resolve().parents[2]
HECHOS_SINTETICO = RAIZ_REPO / "datasets" / "sintetico" / "salida" / "hechos"
BACKTESTS = RAIZ_REPO / "motor" / "backtests"


def parsear_argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--hechos",
        type=Path,
        default=HECHOS_SINTETICO,
        help="Directorio de parquets de hechos. Cambialo para M1.8 (extract real).",
    )
    parser.add_argument(
        "--etiqueta",
        default="sintetico",
        help="Va en el nombre del archivo: baselines-<etiqueta>-<fecha>.md",
    )
    parser.add_argument("--n-cortes", type=int, default=18)
    parser.add_argument("--horizonte-max", type=int, default=12)
    parser.add_argument(
        "--n-jobs",
        type=int,
        default=1,
        help="Paralelismo de statsforecast. OJO: el overhead de spawn se paga por corte, "
        "así que con pocos productos n_jobs>1 EMPEORA el tiempo (medido). Ver README.",
    )
    parser.add_argument(
        "--n-productos",
        type=int,
        default=None,
        help="Limita la corrida a los primeros N productos (smoke test). El recorte queda "
        "escrito en la tabla: una tabla así recortada no es congelable como referencia.",
    )
    parser.add_argument(
        "--estratificado",
        type=int,
        default=None,
        help="N productos POR CUADRANTE, muestreados con semilla fija. Es el modo con el "
        "que se genera la tabla de M1.7 (ver roadmap-motor.md §5.2): da mejores "
        "estadísticas por cuadrante que la distribución natural, donde lumpy es ~11%%.",
    )
    parser.add_argument(
        "--semilla",
        type=int,
        default=42,
        help="Semilla del muestreo estratificado, para que la corrida sea reproducible.",
    )
    parser.add_argument(
        "--checkpoint-dir",
        type=Path,
        default=None,
        help="Persiste cada corte y permite reanudar si la corrida muere (M1.7a). "
        "Recomendado para cualquier corrida de más de unos minutos.",
    )
    parser.add_argument(
        "--salida-dir",
        type=Path,
        default=BACKTESTS,
        help="Dónde escribir el markdown.",
    )
    return parser.parse_args(argv)


def _muestra_estratificada(
    hechos: pd.DataFrame, n_por_cuadrante: int, semilla: int
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Toma hasta `n_por_cuadrante` productos de cada cuadrante de intermitencia.

    Devuelve los hechos recortados y cuántos productos quedaron por cuadrante — el
    conteo va a la tabla: si algún cuadrante tenía menos de N y se tomaron todos, eso
    tiene que verse, no quedar como un recorte silencioso.

    `sin_actividad` se excluye: no es un cuadrante sino la ausencia de señal, y es el
    mismo criterio con el que `distribucion_cuadrantes` compara contra el EDA.
    """
    clasificacion = clasificar_series(hechos)
    activos = clasificacion[clasificacion["cuadrante"] != SIN_ACTIVIDAD]

    # Barajar y tomar los primeros N de cada grupo, en vez de `groupby().apply(sample)`:
    # da lo mismo, no usa el `include_groups` que pandas deprecó, y un cuadrante con
    # menos de N productos devuelve todos los que tenga sin caso especial.
    barajado = activos.sample(frac=1, random_state=semilla)
    elegidos = barajado.groupby("cuadrante", observed=True).head(n_por_cuadrante)

    conteo = elegidos["cuadrante"].value_counts().to_dict()
    return hechos[hechos["id_producto"].isin(elegidos["id_producto"])], conteo


def main(argv: list[str] | None = None) -> int:
    args = parsear_argumentos(argv)

    if not args.hechos.exists():
        print(
            f"No hay hechos en {args.hechos}.\nSi es el sintético, generalo desde la raíz "
            "del repo (ver motor/README.md §Arranque desde cero):\n\n"
            "  motor/.venv/Scripts/python -m datasets.sintetico.generar_sintetico "
            "--semilla 42 --sin-contrato",
            file=sys.stderr,
        )
        return 1

    if args.n_cortes <= args.horizonte_max:
        # Trampa documentada en roadmap-motor.md §12.2: con n_cortes = N el horizonte
        # máximo medible es N, así que una tabla con n_cortes <= 12 no llega al h=12 que
        # exige el gate de M1.2 — y no avisaría sola.
        print(
            f"--n-cortes ({args.n_cortes}) tiene que ser MAYOR que --horizonte-max "
            f"({args.horizonte_max}): con N cortes el horizonte máximo medible es N, así "
            "que la tabla no llegaría al h=12 que exige el gate de M1.2.",
            file=sys.stderr,
        )
        return 1

    repo = RepositorioArchivos(args.hechos)
    hechos = repo.hecho_venta_mensual_producto()
    catalogo = repo.catalogo_producto()

    if args.n_productos is not None and args.estratificado is not None:
        print("--n-productos y --estratificado son excluyentes: elegí uno.", file=sys.stderr)
        return 1

    productos_totales = hechos["id_producto"].nunique()
    conteo_cuadrantes: dict[str, int] = {}
    if args.estratificado is not None:
        hechos, conteo_cuadrantes = _muestra_estratificada(
            hechos, args.estratificado, args.semilla
        )
    elif args.n_productos is not None:
        muestra = hechos["id_producto"].drop_duplicates().head(args.n_productos)
        hechos = hechos[hechos["id_producto"].isin(muestra)]

    productos_corridos = hechos["id_producto"].nunique()
    print(
        f"Corriendo {len(CANDIDATOS)} candidatos sobre {productos_corridos} productos "
        f"× {args.n_cortes} cortes (n_jobs={args.n_jobs})...",
        flush=True,
    )
    if conteo_cuadrantes:
        print(f"  muestra estratificada (semilla {args.semilla}): {conteo_cuadrantes}", flush=True)
    if productos_corridos < 180 and args.n_jobs > 1:
        # Medido en M1.7: el overhead de spawn se paga por corte, así que con pocos
        # productos n_jobs>1 es más lento que serie. Avisar, no corregir por su cuenta.
        print(
            f"  OJO: con {productos_corridos} productos, n_jobs={args.n_jobs} probablemente "
            "sea MÁS LENTO que n_jobs=1 (ver modelado/README.md §Costo y paralelismo).",
            flush=True,
        )

    inicio = time.perf_counter()
    predictor = functools.partial(predecir_todos_los_candidatos, n_jobs=args.n_jobs)
    reporte = ejecutar_backtest(
        hechos,
        predictor,
        n_cortes=args.n_cortes,
        horizonte_max=args.horizonte_max,
        directorio_checkpoint=args.checkpoint_dir,
    )
    duracion_backtest = time.perf_counter() - inicio
    print(f"  backtest: {duracion_backtest / 60:.1f} min", flush=True)

    # El merge de más abajo descarta .attrs (pandas) y ahí viaja la Corrida — sin ella
    # a_markdown marca la tabla como no congelable. Ver roadmap-motor.md §12.2.
    corrida = reporte.attrs["corrida"]

    ganadores = elegir_mejor_por_serie(reporte, train_df=hechos)
    seleccionado = armar_reporte_seleccionado(reporte, ganadores)

    # Clasificación para DESAGREGAR el reporte (uso 2 de clasificacion.py), no para
    # enrutar: por eso acá `hasta` es el default (toda la historia) y no el corte. La
    # advertencia de roadmap-motor.md §12.2 aplica al enrutamiento, y esta selección no
    # enruta por cuadrante — los 7 candidatos compiten libres en toda serie.
    clasificacion = clasificar_series(hechos)

    seleccionado = seleccionado.merge(
        catalogo[["id_producto", "categoria"]], on="id_producto", how="left"
    )
    seleccionado = etiquetar(seleccionado, clasificacion)
    seleccionado.attrs["corrida"] = corrida

    tablas = construir_reporte(seleccionado, columna_pred="pred", train_df=hechos)
    tablas["ganadores_por_cuadrante"] = resumen_de_ganadores(ganadores, clasificacion)

    fecha = datetime.now(tz=UTC).date().isoformat()
    md = a_markdown(
        tablas,
        titulo=f"Piso de baselines — {args.etiqueta} ({fecha})",
        notas=_notas(
            args,
            productos_corridos,
            productos_totales,
            duracion_backtest,
            ganadores,
            conteo_cuadrantes,
            tablas,
        ),
    )

    args.salida_dir.mkdir(parents=True, exist_ok=True)
    destino = args.salida_dir / f"baselines-{args.etiqueta}-{fecha}.md"
    destino.write_text(md, encoding="utf-8")
    print(f"\nEscrito: {destino}")
    print(f"Corrida: {corrida.id}")
    return 0


def _nota_de_cobertura(tablas: dict[str, pd.DataFrame] | None) -> list[str]:
    """Si la cobertura no es 1,0, la tabla lo tiene que decir en su encabezado.

    `backtests/README.md` lo exige como condición 4 para congelar: una tabla con
    cobertura baja tiene mejor WAPE **por omitir series difíciles**, no por predecir
    mejor. Dejar el dato solo en una columna al medio de la tabla es dejarlo donde nadie
    lo mira. La causa concreta no la puede deducir el script; lo que sí puede es negarse
    a que el número pase desapercibido.
    """
    if not tablas or "por_horizonte" not in tablas:
        return []
    por_horizonte = tablas["por_horizonte"]
    if "cobertura" not in por_horizonte.columns:
        return []

    minima = float(por_horizonte["cobertura"].min())
    if minima >= 0.9999:
        return []

    peor = por_horizonte.loc[por_horizonte["cobertura"].idxmin()]
    return [
        "",
        f"> ⚠️ **La cobertura NO es 1,0: baja hasta {minima:.4f} a h={int(peor['horizonte'])} "
        "(grano producto).** Son filas con valor real y **sin predicción del modelo "
        "seleccionado**, y **bajan el WAPE de la tabla porque omiten series, no porque el "
        "método acierte más**. Antes de usar esta tabla como piso hay que explicar de "
        "dónde salen esas filas — `backtests/README.md` §Qué tiene que traer cada tabla, "
        "condición 4. **Ojo al diagnosticarlas:** que el modelo seleccionado no haya "
        "predicho NO implica que ningún candidato pudiera. Contar solo las filas donde "
        "ninguno predijo subestima la brecha y da un falso 100% explicado — pasó con la "
        "tabla del 2026-07-31 (ver `roadmap-motor.md` §5.6.1).",
    ]


def _notas(
    args: argparse.Namespace,
    productos_corridos: int,
    productos_totales: int,
    duracion_backtest: float,
    ganadores: pd.DataFrame,
    conteo_cuadrantes: dict[str, int],
    tablas: dict[str, pd.DataFrame] | None = None,
) -> str:
    """Las notas que encabezan el markdown. Incluyen los avisos que hacen honesta a la
    tabla: sobre qué universo se corrió, y que la selección por serie es retrospectiva."""
    lineas = [
        f"Selección por serie (M1.7) entre {len(CANDIDATOS)} candidatos: "
        f"`{'`, `'.join(CANDIDATOS)}`.",
        "",
        f"- **Productos:** {productos_corridos} · **cortes:** {args.n_cortes} · "
        f"**horizonte:** {args.horizonte_max} · **n_jobs:** {args.n_jobs}",
        f"- **Tiempo de backtest:** {duracion_backtest / 60:.1f} min",
        f"- **Series con ganador asignado:** {len(ganadores)}",
    ]

    if conteo_cuadrantes:
        detalle = " · ".join(f"{c}: {n}" for c, n in sorted(conteo_cuadrantes.items()))
        lineas += [
            f"- **Muestreo:** estratificado, hasta {args.estratificado} productos por "
            f"cuadrante, semilla {args.semilla} → {detalle}",
            "",
            f"> **Muestra estratificada de {productos_corridos} de {productos_totales} "
            "productos, no el catálogo completo** — decisión registrada en "
            "`roadmap-motor.md` §5.2. El sintético no valida calidad predictiva (reproduce "
            "propiedades, no la señal), así que esta tabla acredita que el pipeline de "
            "selección corre reproducible de punta a punta; **no es el piso a batir**. El "
            "piso es el de M1.8, sobre datos reales. Estratificar además da mejores "
            "estadísticas por cuadrante que la distribución natural, donde `lumpy` es ~11%.",
        ]
    elif productos_corridos < productos_totales:
        lineas += [
            "",
            f"> ⚠️ **CORRIDA RECORTADA — no congelable como referencia.** Se corrieron los "
            f"primeros {productos_corridos} de {productos_totales} productos "
            "(`--n-productos`), que no es un muestreo sino un recorte arbitrario. Para una "
            "tabla defendible usá `--estratificado` o el catálogo completo.",
        ]

    lineas += _nota_de_cobertura(tablas)

    lineas += [
        "",
        "> **La selección por serie es retrospectiva, así que este piso es optimista.** "
        "El ganador de cada serie se eligió con el MASE de todos los cortes y se aplicó "
        "también a los más viejos, es decir con información posterior a las filas donde "
        "se mide. Es lo que especifica `plan-diseno.md` §M1 y la convención para fijar "
        "una referencia fuerte, pero **no es un procedimiento prospectivo** y por lo "
        "tanto este piso está más alto que el de un pipeline que eligiera el método en "
        "cada corte con datos ≤ corte. Antes del champion/challenger de M2.5 hay que "
        "nivelar la comparación — ver `roadmap-motor.md` §12.5.",
        "",
        "> Las predicciones individuales **sí** son limpias: el arnés garantiza historia "
        "≤ corte en cada una (M1.3). Lo retrospectivo es la elección de *qué modelo* "
        "mirar, no lo que cada modelo vio.",
    ]
    return "\n".join(lineas)


if __name__ == "__main__":
    raise SystemExit(main())
