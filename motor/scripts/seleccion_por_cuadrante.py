"""¿Conviene elegir el modelo por cuadrante en vez de por serie? (M3.1a)

Cruza las mismas dos corridas **ya ejecutadas** que M2.5 —los 7 baselines de M1.8 y el
global de M2.3/M2.4— y agrega un cuarto contendiente: el champion elegido por
`(cuadrante, corte)` en lugar de por `(serie, corte)`.

    motor/.venv/Scripts/python motor/scripts/seleccion_por_cuadrante.py \\
        --hechos C:/dfv-extract-v2 --etiqueta real --estratificado 0 \\
        --checkpoints-baselines C:/dfv-checkpoints-2026-08-03 \\
        --checkpoints-global    C:/dfv-checkpoints-intervalos

**No reajusta un solo modelo.** El `id` de corrida no incluye el predictor, así que las dos
corridas tienen las mismas filas y se cruzan por `(producto, mes, corte, horizonte)`
(`backtesting.checkpoints`). Lo único que cambia entre contendientes es con qué criterio se
elige, sobre predicciones ya calculadas.

## Por qué recalcula el `champion` de M2.5 en vez de leer sus números

El gate de M3.1a (`roadmap-motor.md` §7.1 punto 4) compara contra el champion por serie.
Podría leerse de `global-vs-baselines-real-2026-08-06.md`, pero entonces la comparación
sería contra un markdown congelado en vez de fila a fila dentro de una misma corrida. Es la
disciplina de §5.6.2, donde los tres escenarios de selección se compararon **dentro** de la
misma corrida justamente para que la diferencia fuera atribuible al criterio y a nada más.
De paso queda un control: si el `champion` recalculado no reprodujera los números de M2.5,
algo cambió y la tabla no sirve.

## Los cuatro contendientes

| contendiente | qué es |
|---|---|
| `piso` | los 7 baselines con selección prospectiva por serie + cascada (ADR-016) |
| `global` | `GlobalLGBM` en todas las series, sin selección |
| `champion` | los 9 candidatos por **(serie, corte)** — lo promocionado en M2.5 (ADR-017) |
| `champion_cuadrante` | los mismos 9 por **(cuadrante, corte)** — lo que M3.1a mide |

## Un resultado posible que no hay que maquillar

Que `champion_cuadrante` gane en unos horizontes y pierda en otros. El gate pide **los
cuatro**, y se declaró así antes de medir a propósito: elegir el criterio de selección por
horizonte mirando la tabla final es el hindsight que ADR-016 le sacó al piso. Si pasa, la
conclusión es "no se adopta" y se cierra en negativo, como M3.0.
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
from motor.clasificacion import (
    clasificar_por_corte,
    clasificar_series,
    etiquetar,
    muestra_estratificada,
)
from motor.datos.archivos import RepositorioArchivos
from motor.modelado.modelo_global import NOMBRE_MODELO, nombre_de_cuantil
from motor.modelado.seleccion import (
    CANDIDATOS,
    armar_reporte_con_cascada,
    elegir_mejor_por_corte,
    elegir_mejor_por_cuadrante,
    estabilidad_de_la_seleccion,
    ganadores_de_cuadrante,
    resumen_de_cascada,
    resumen_de_ganadores,
)

RAIZ_REPO = Path(__file__).resolve().parents[2]
HECHOS_SINTETICO = RAIZ_REPO / "datasets" / "sintetico" / "salida" / "hechos"
BACKTESTS = RAIZ_REPO / "motor" / "backtests"

COLUMNA_PISO = "piso"
COLUMNA_CHAMPION = "champion"
COLUMNA_CUADRANTE = "champion_cuadrante"
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
    parser.add_argument("--salida-dir", type=Path, default=BACKTESTS)
    return parser.parse_args(argv)


def _con_cascada(
    cruzado: pd.DataFrame, ranking: pd.DataFrame, modelos: list[str], columna_pred: str
) -> pd.DataFrame:
    """Aplica un ranking al reporte, renombrando las columnas de diagnóstico.

    Sin el sufijo, la segunda selección pisa las de la primera y el reparto de un
    contendiente se leería como el de otro.
    """
    con_cascada = armar_reporte_con_cascada(
        cruzado, ranking, modelos=modelos, columna_pred=columna_pred
    )
    return con_cascada.rename(
        columns={
            "modelo_usado": f"modelo_usado_{columna_pred}",
            "rango_usado": f"rango_usado_{columna_pred}",
        }
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

    candidatos = [*CANDIDATOS, NOMBRE_MODELO, MEDIANA_GLOBAL]
    cortes = sorted(cruzado["corte"].dropna().unique())

    # Una sola vez para los 18 cortes: es la parte cara de la unidad (~72 s a escala real),
    # y la usan tanto la selección como la tabla de ganadores por cuadrante.
    print(f"Clasificando por corte ({len(cortes)} cortes, hasta=corte)...", flush=True)
    t_clasif = time.perf_counter()
    cuadrantes_por_corte = clasificar_por_corte(hechos, cortes, columnas_id=["id_producto"])
    print(f"  {time.perf_counter() - t_clasif:.1f} s", flush=True)

    print("Selección prospectiva del piso (7 baselines, por serie)...", flush=True)
    ranking_piso = elegir_mejor_por_corte(cruzado, hechos, modelos=list(CANDIDATOS))
    cruzado = _con_cascada(cruzado, ranking_piso, list(CANDIDATOS), COLUMNA_PISO)

    print(f"Champion por serie ({len(candidatos)} candidatos)...", flush=True)
    ranking_champion = elegir_mejor_por_corte(cruzado, hechos, modelos=candidatos)
    cruzado = _con_cascada(cruzado, ranking_champion, candidatos, COLUMNA_CHAMPION)

    print(f"Champion por cuadrante ({len(candidatos)} candidatos)...", flush=True)
    ranking_cuadrante = elegir_mejor_por_cuadrante(
        cruzado, hechos, modelos=candidatos, cuadrantes=cuadrantes_por_corte
    )
    cruzado = _con_cascada(cruzado, ranking_cuadrante, candidatos, COLUMNA_CUADRANTE)
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
        "champion": COLUMNA_CHAMPION,
        "champion_cuadrante": COLUMNA_CUADRANTE,
    }
    duracion = time.perf_counter() - inicio

    # Las tablas estándar describen al candidato de esta unidad.
    tablas = construir_reporte(cruzado, columna_pred=COLUMNA_CUADRANTE)
    tablas["veredicto"] = cabeza_a_cabeza(cruzado, contendientes)
    tablas["veredicto_por_cuadrante"] = cabeza_a_cabeza_desagregado(cruzado, contendientes)

    por_serie = wape_por_serie(cruzado, list(contendientes.values()))
    tablas["mejora_cuadrante_vs_champion"] = distribucion_de_mejora(
        por_serie, campeon=COLUMNA_CHAMPION, retador=COLUMNA_CUADRANTE, clasificacion=clasificacion
    )
    tablas["mejora_cuadrante_vs_global"] = distribucion_de_mejora(
        por_serie, campeon=NOMBRE_MODELO, retador=COLUMNA_CUADRANTE, clasificacion=clasificacion
    )
    tablas["ganador_por_cuadrante_y_corte"] = ganadores_de_cuadrante(
        ranking_cuadrante, cuadrantes_por_corte
    )
    tablas["reparto_champion_cuadrante"] = resumen_de_ganadores(
        ranking_cuadrante[ranking_cuadrante["rango"] == 0].rename(
            columns={"modelo": "modelo_ganador"}
        ),
        clasificacion,
    )
    tablas["reparto_champion_serie"] = resumen_de_ganadores(
        ranking_champion[ranking_champion["rango"] == 0].rename(
            columns={"modelo": "modelo_ganador"}
        ),
        clasificacion,
    )
    tablas["estabilidad_champion_cuadrante"] = estabilidad_de_la_seleccion(ranking_cuadrante)
    tablas["origen_champion_cuadrante"] = resumen_de_cascada(
        cruzado.rename(columns={f"rango_usado_{COLUMNA_CUADRANTE}": "rango_usado"})
    )

    fecha = datetime.now(tz=UTC).date().isoformat()
    md = a_markdown(
        tablas,
        titulo=f"Selección por (cuadrante, corte) contra por (serie, corte) — "
        f"{args.etiqueta} ({fecha})",
        notas=_notas(args, hechos, productos_totales, conteo_cuadrantes, duracion, cruzado),
    )
    args.salida_dir.mkdir(parents=True, exist_ok=True)
    destino = args.salida_dir / f"seleccion-por-cuadrante-{args.etiqueta}-{fecha}.md"
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
    lineas = [
        "M3.1a (`roadmap-motor.md` §7.1). **Ningún modelo se reajustó**: la tabla sale de "
        "cruzar los checkpoints de dos corridas que comparten `id` y de reelegir sobre "
        "predicciones ya calculadas.",
        "",
        f"- **Productos:** {hechos['id_producto'].nunique()} de {productos_totales} · "
        f"**cortes:** {args.n_cortes} · **horizonte:** {args.horizonte_max} · "
        f"**filas cruzadas:** {len(cruzado)} · **{duracion:.1f} s**",
        f"- **Candidatos:** {len(CANDIDATOS)} baselines + `{NOMBRE_MODELO}` + "
        f"`{MEDIANA_GLOBAL}`, los mismos 9 de M2.5.",
        "- **Los cuatro contendientes usan la misma regla de observabilidad** (ADR-016): en "
        "el corte `t` solo entra el error de las filas cuyo mes ya ocurrió. Lo único que "
        "cambia entre `champion` y `champion_cuadrante` es **con cuánta evidencia se "
        "rankea**: ~2.100 decisiones por corte contra ~5.",
        "- **El cuadrante se calcula con `hasta=corte`** (`clasificacion.clasificar_por_corte`). "
        "Con el default —último mes de los datos— la decisión miraría el futuro (§12.2).",
        "- **`sin_actividad` es un grupo más**, con su propio ranking aprendido: mandarlo a "
        "una regla fija sería el enrutamiento por teoría que M1.7 midió peor.",
        "- **El `champion` se recalcula acá**, no se lee de "
        "`global-vs-baselines-real-2026-08-06.md`: el gate compara fila a fila dentro de "
        "una misma corrida, que es la disciplina de §5.6.2.",
    ]
    if conteo_cuadrantes:
        detalle = " · ".join(f"{c}: {n}" for c, n in sorted(conteo_cuadrantes.items()))
        lineas.append(
            f"- **Muestreo:** estratificado, hasta {args.estratificado} por cuadrante, "
            f"semilla {args.semilla} → {detalle}"
        )
    lineas += [
        "",
        "> **El gate de M3.1a pide los cuatro horizontes.** `champion_cuadrante` se adopta "
        "solo si le gana al `champion` en WAPE producto a h=1/3/6/12 **y** mantiene el "
        "sesgo total dentro del ±5% (ADR-008). Ganar en algunos y perder en otros es "
        "resultado negativo: elegir el criterio por horizonte mirando esta tabla es el "
        "hindsight que ADR-016 sacó del piso.",
        "",
        "> **Ninguna decisión se toma con el agregado.** El WAPE total es 86% del cuadrante "
        "`suave` (M2.5, §6.7), así que la tabla que manda es *Veredicto por cuadrante*, con "
        "su columna `peso_%`.",
        "",
        "> **Solo se comparan las celdas donde los contendientes tienen la misma cobertura.** "
        "Una serie no predicha puntúa WAPE 0,0 —perfecto— y solo `cobertura` lo delata.",
    ]
    if args.etiqueta == "sintetico":
        lineas += [
            "",
            "> ⚠️ **El sintético no decide.** No reproduce las ráfagas de `lumpy`/"
            "`intermitente` y en M2.5 habría promocionado el global, que en real no era "
            "promocionable (§6.7 punto 6). Vale como smoke del pipeline, no como árbitro.",
        ]
    return "\n".join(lineas)


if __name__ == "__main__":
    raise SystemExit(main())
