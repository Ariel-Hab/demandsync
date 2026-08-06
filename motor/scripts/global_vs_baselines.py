"""Champion/challenger: ¿en qué series le gana el global al piso de baselines? (M2.5)

Cruza dos corridas **ya ejecutadas** —los 7 baselines de M1.8 y el global de M2.3/M2.4—
y emite el reporte comparativo de `motor/backtests/global-vs-baselines-<etiqueta>-<fecha>.md`.

    motor/.venv/Scripts/python motor/scripts/global_vs_baselines.py \\
        --hechos C:/dfv-extract-v2 --etiqueta real --estratificado 0 \\
        --checkpoints-baselines C:/dfv-checkpoints-2026-08-03 \\
        --checkpoints-global    C:/dfv-checkpoints-intervalos

**No reajusta un solo modelo, y no puede hacerlo aunque falte algo.** El `id` de corrida
es hash de configuración + datos y no incluye el predictor, así que las dos corridas tienen
las mismas filas y se cruzan por `(producto, mes, corte, horizonte)`
(`backtesting.checkpoints`). Si a un directorio le falta un corte, el script corta: es la
diferencia entre un reporte completo y uno mitad checkpoint mitad recalculado.

## Los tres contendientes, y por qué el tercero existe

| contendiente | qué es |
|---|---|
| `piso` | los 7 baselines con selección **prospectiva** + cascada (ADR-016) |
| `global` | `GlobalLGBM` en todas las series, sin selección |
| `champion` | los 9 candidatos compitiendo: 7 baselines + `GlobalLGBM` + `GlobalLGBM_P50` |

El `champion` es lo que pide `plan-diseno.md` §M2: *"el global ML reemplaza al baseline
solo en las series/niveles donde le gana en backtest"*. Se elige con **la misma regla que
el piso** —por corte, solo con error ya observado, y cascada por disponibilidad— porque
darle al global trato retrospectivo inclinaría la cancha a su favor, que es el problema de
ADR-016 punto 4 al revés.

`GlobalLGBM_P50` entra como candidato por §6.6 punto 4: la mediana le gana a la media a
h=12, justo en la única celda que M2.3 perdía contra el piso. Adoptarla mirando esa tabla
sería hindsight; hacerla competir por corte con lo ya observado, no. `--sin-p50` corre la
variante sin ella, que es como se mide cuánto aporta.

## Un resultado posible que no hay que maquillar

Que el `champion` **pierda** contra el `global` solo. Nueve candidatos reelegidos por corte
agregan varianza de selección, y en los primeros cortes se elige casi sin evidencia. Si
pasa, la conclusión es "seleccionar por serie no paga" y se documenta — igual que el
resultado simétrico, "el baseline se queda con el N% de las series", que el plan de diseño
ya declara legítimo.
"""

import argparse
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from motor.backtesting.checkpoints import cargar_desde_checkpoints, cruzar_reportes
from motor.backtesting.comparacion import (
    cabeza_a_cabeza,
    cabeza_a_cabeza_desagregado,
    distribucion_de_mejora,
    wape_por_serie,
)
from motor.backtesting.reporte import a_markdown, construir_reporte
from motor.clasificacion import clasificar_series, etiquetar, muestra_estratificada
from motor.datos.archivos import RepositorioArchivos
from motor.modelado.modelo_global import NOMBRE_MODELO, nombre_de_cuantil
from motor.modelado.seleccion import (
    CANDIDATOS,
    armar_reporte_con_cascada,
    elegir_mejor_por_corte,
    estabilidad_de_la_seleccion,
    resumen_de_cascada,
    resumen_de_ganadores,
)

RAIZ_REPO = Path(__file__).resolve().parents[2]
HECHOS_SINTETICO = RAIZ_REPO / "datasets" / "sintetico" / "salida" / "hechos"
BACKTESTS = RAIZ_REPO / "motor" / "backtests"

COLUMNA_PISO = "piso"
COLUMNA_CHAMPION = "champion"
MEDIANA_GLOBAL = nombre_de_cuantil(0.5)


def parsear_argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--hechos", type=Path, default=HECHOS_SINTETICO)
    parser.add_argument("--etiqueta", default="sintetico")
    parser.add_argument("--checkpoints-baselines", type=Path, required=True)
    parser.add_argument("--checkpoints-global", type=Path, required=True)
    parser.add_argument("--n-cortes", type=int, default=18)
    parser.add_argument("--horizonte-max", type=int, default=12)
    parser.add_argument(
        "--estratificado",
        type=int,
        default=100,
        help="Productos POR CUADRANTE. Tiene que ser EL MISMO valor con el que se "
        "corrieron los checkpoints: cambia la huella de datos y por lo tanto el `id`.",
    )
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument(
        "--sin-p50",
        action="store_true",
        help="Saca GlobalLGBM_P50 de los candidatos del champion, para medir su aporte.",
    )
    parser.add_argument("--salida-dir", type=Path, default=BACKTESTS)
    return parser.parse_args(argv)


def _seleccionar(
    cruzado: pd.DataFrame,
    hechos: pd.DataFrame,
    modelos: list[str],
    columna_pred: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Selección prospectiva + cascada sobre `modelos`, dejando el resultado en `columna_pred`.

    Devuelve `(reporte, ranking)`. Las columnas de diagnóstico (`modelo_usado`,
    `rango_usado`) se renombran con el sufijo del contendiente: sin eso, la segunda
    selección pisaría las de la primera y el reparto del champion se leería como el del
    piso.
    """
    ranking = elegir_mejor_por_corte(cruzado, hechos, modelos=modelos)
    con_cascada = armar_reporte_con_cascada(
        cruzado, ranking, modelos=modelos, columna_pred=columna_pred
    )
    return (
        con_cascada.rename(
            columns={
                "modelo_usado": f"modelo_usado_{columna_pred}",
                "rango_usado": f"rango_usado_{columna_pred}",
            }
        ),
        ranking,
    )


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

    inicio = time.perf_counter()
    comun = {"n_cortes": args.n_cortes, "horizonte_max": args.horizonte_max}
    print("Releyendo checkpoints (no se ajusta ningún modelo)...", flush=True)
    baselines = cargar_desde_checkpoints(hechos, args.checkpoints_baselines, **comun)
    global_ = cargar_desde_checkpoints(hechos, args.checkpoints_global, **comun)

    corrida = baselines.attrs.get("corrida")
    cruzado = cruzar_reportes({"baselines": baselines, "global": global_})
    cruzado.attrs["corrida"] = corrida
    print(f"  cruzado: {len(cruzado)} filas · corrida {corrida.id}", flush=True)

    candidatos_champion = [*CANDIDATOS, NOMBRE_MODELO]
    if not args.sin_p50:
        candidatos_champion.append(MEDIANA_GLOBAL)

    print("Selección prospectiva del piso (7 baselines)...", flush=True)
    cruzado, ranking_piso = _seleccionar(cruzado, hechos, list(CANDIDATOS), COLUMNA_PISO)
    print(f"Selección prospectiva del champion ({len(candidatos_champion)})...", flush=True)
    cruzado, ranking_champion = _seleccionar(
        cruzado, hechos, candidatos_champion, COLUMNA_CHAMPION
    )
    cruzado.attrs["corrida"] = corrida

    clasificacion = clasificar_series(hechos)
    cruzado = etiquetar(cruzado, clasificacion)
    if "categoria" in catalogo.columns:
        cruzado = cruzado.merge(
            catalogo[["id_producto", "categoria"]].drop_duplicates("id_producto"),
            on="id_producto",
            how="left",
        )
    cruzado.attrs["corrida"] = corrida

    contendientes = {
        "piso": COLUMNA_PISO,
        "global": NOMBRE_MODELO,
        "global_P50": MEDIANA_GLOBAL,
        "champion": COLUMNA_CHAMPION,
    }
    duracion = time.perf_counter() - inicio

    # Las tablas estándar describen al CHAMPION: es el candidato a promover, y el gate de
    # M1.2 exige el desagregado por cuadrante en cualquier tabla congelable.
    tablas = construir_reporte(cruzado, columna_pred=COLUMNA_CHAMPION)
    tablas["veredicto"] = cabeza_a_cabeza(cruzado, contendientes)
    tablas["veredicto_por_cuadrante"] = cabeza_a_cabeza_desagregado(cruzado, contendientes)

    por_serie = wape_por_serie(cruzado, list(contendientes.values()))
    tablas["mejora_global_vs_piso"] = distribucion_de_mejora(
        por_serie, campeon=COLUMNA_PISO, retador=NOMBRE_MODELO, clasificacion=clasificacion
    )
    tablas["mejora_champion_vs_global"] = distribucion_de_mejora(
        por_serie, campeon=NOMBRE_MODELO, retador=COLUMNA_CHAMPION, clasificacion=clasificacion
    )
    tablas["reparto_champion"] = resumen_de_ganadores(
        ranking_champion[ranking_champion["rango"] == 0].rename(
            columns={"modelo": "modelo_ganador"}
        ),
        clasificacion,
    )
    tablas["reparto_piso"] = resumen_de_ganadores(
        ranking_piso[ranking_piso["rango"] == 0].rename(columns={"modelo": "modelo_ganador"}),
        clasificacion,
    )
    tablas["estabilidad_champion"] = estabilidad_de_la_seleccion(ranking_champion)
    tablas["origen_champion"] = resumen_de_cascada(
        cruzado.rename(columns={f"rango_usado_{COLUMNA_CHAMPION}": "rango_usado"})
    )

    fecha = datetime.now(tz=UTC).date().isoformat()
    md = a_markdown(
        tablas,
        titulo=f"Champion/challenger: global contra el piso de baselines — "
        f"{args.etiqueta} ({fecha})",
        notas=_notas(args, hechos, productos_totales, conteo_cuadrantes, duracion, cruzado),
    )
    args.salida_dir.mkdir(parents=True, exist_ok=True)
    destino = args.salida_dir / f"global-vs-baselines-{args.etiqueta}-{fecha}.md"
    destino.write_text(md, encoding="utf-8")
    print(f"\n{duracion:.1f} s · Escrito: {destino}")
    return 0


def _notas(
    args: argparse.Namespace,
    hechos: pd.DataFrame,
    productos_totales: int,
    conteo_cuadrantes: dict[str, int],
    duracion: float,
    cruzado: pd.DataFrame,
) -> str:
    candidatos = f"{len(CANDIDATOS)} baselines + `{NOMBRE_MODELO}`"
    if not args.sin_p50:
        candidatos += f" + `{MEDIANA_GLOBAL}`"

    lineas = [
        "Champion/challenger de M2.5. **Ningún modelo se reajustó**: la tabla sale de "
        "cruzar los checkpoints de dos corridas que comparten `id` — el hash de corrida "
        "es de configuración + datos y no incluye el predictor.",
        "",
        f"- **Productos:** {hechos['id_producto'].nunique()} de {productos_totales} · "
        f"**cortes:** {args.n_cortes} · **horizonte:** {args.horizonte_max} · "
        f"**filas cruzadas:** {len(cruzado)} · **{duracion:.1f} s**",
        f"- **Candidatos del champion:** {candidatos}, elegidos con **selección "
        "prospectiva + cascada** (ADR-016) — por (serie, corte), y en cada corte solo con "
        "el error de las filas cuyo mes ya ocurrió.",
        "- **El piso usa exactamente la misma regla**, y eso es el punto: si el champion "
        "eligiera con hindsight y el piso no, la comparación estaría inclinada a favor del "
        "global, que es ADR-016 punto 4 al revés.",
        "- **`global` y `global_P50` no seleccionan nada**: son la columna del modelo "
        "aplicada a todas las series. Sirven para separar cuánto del resultado es el "
        "modelo y cuánto es elegir por serie.",
        "- **Las tablas estándar de abajo (por nivel, categoría, cuadrante, MASE) son del "
        "`champion`**, que es el candidato a promover. La comparación entre los cuatro "
        "está en *Cabeza a cabeza*.",
    ]
    if conteo_cuadrantes:
        detalle = " · ".join(f"{c}: {n}" for c, n in sorted(conteo_cuadrantes.items()))
        lineas.append(
            f"- **Muestreo:** estratificado, hasta {args.estratificado} por cuadrante, "
            f"semilla {args.semilla} → {detalle}"
        )
    lineas += [
        "",
        "> **`mejora` es `wape(campeon) - wape(retador)`: positivo favorece al retador.** "
        "Se reporta la mediana y los cuartiles, no la media: la distribución tiene colas "
        "largas y una serie con WAPE de 40 corre el promedio entero.",
        "",
        "> **Solo se comparan las celdas donde los dos contendientes tienen la misma "
        "cobertura.** En `metricas.wape` una predicción nula aporta 0 al numerador, así "
        "que una serie **no predicha** puntúa WAPE 0,0 —perfecto— y solo la columna "
        "`cobertura` lo delata. La columna `no_comparable` cuenta lo que queda afuera.",
        "",
        "> **Por qué la `cobertura` no es 1,0:** son las **altas de catálogo** de "
        "`roadmap-motor.md` §5.6.1 — productos cuya primera venta es posterior al corte. "
        "§6.5 verificó fila a fila que son **las mismas** en las dos corridas, así que la "
        "comparación es a igual cobertura por construcción, no por suerte.",
    ]
    if args.etiqueta == "sintetico":
        lineas += [
            "",
            "> ⚠️ **El sintético no decide el gate de M2.** El generador no tiene la "
            "irregularidad del mundo real y haría ver al modelo mejor de lo que es "
            "(`roadmap-motor.md` §6, *Riesgo específico*). Vale para verificar que el "
            "pipeline corre; el número que manda es el de la corrida real. Y **no se "
            "compara contra `baselines-sintetico-2026-07-30.md`**: esa tabla se congeló "
            "antes de que T0.4 reescribiera el generador (§6.4).",
        ]
    return "\n".join(lineas)


if __name__ == "__main__":
    raise SystemExit(main())
