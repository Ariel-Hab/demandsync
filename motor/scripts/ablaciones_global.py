"""Ablaciones del modelo global (M2.3): qué configuración se lleva al champion/challenger.

M2.3 no pide ganarle al piso —eso es M2.5— pero sí pide llegar a M2.5 con una configuración
**medida** y no elegida a ojo. Se miden dos cosas, en cruz:

- **`usar_precio`** aísla **qué compró M2.2**. Sin este interruptor, si el global gana o
  pierde no se sabe si fue por las features de precio o a pesar de ellas.
- **`escalar_target`**: las escalas por producto van de jeringas a vacunas y el modelo es
  **uno solo**, así que sin escalar las series grandes dominan el ajuste.
  `LocalStandardScaler` normaliza por serie.

    motor/.venv/Scripts/python motor/scripts/ablaciones_global.py --estratificado 100

**Corre sobre la misma muestra estratificada que la tabla de M1.7** (400 productos, semilla
42 — `roadmap-motor.md` §5.2), usando `motor.clasificacion.muestra_estratificada`, que es la
misma función que usa `congelar_baselines_sintetico.py`. Si se muestreara distinto, las dos
tablas parecerían comparables sin serlo.

⚠️ **Cada configuración necesita su propio directorio de checkpoints.** El `id` de corrida
es hash de configuración + datos y **no incluye el predictor** (`corrida.py`), así que las
cuatro variantes producen el mismo `id` y compartir directorio haría que la segunda
"reanudara" los checkpoints de la primera — devolviendo el reporte de otra configuración sin
avisar. El script arma un subdirectorio por variante; no lo unifiques.
"""

import argparse
import functools
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from motor.backtesting.arnes import ejecutar_backtest
from motor.backtesting.metricas import sesgo, wape
from motor.backtesting.reporte import a_markdown
from motor.clasificacion import clasificar_series, etiquetar, muestra_estratificada
from motor.datos.archivos import RepositorioArchivos
from motor.modelado.modelo_global import NOMBRE_MODELO, cobertura_esperada, predecir_global

RAIZ_REPO = Path(__file__).resolve().parents[2]
HECHOS_SINTETICO = RAIZ_REPO / "datasets" / "sintetico" / "salida" / "hechos"
BACKTESTS = RAIZ_REPO / "motor" / "backtests"

VARIANTES = {
    "precio+crudo": {"usar_precio": True, "escalar_target": False},
    "precio+escalado": {"usar_precio": True, "escalar_target": True},
    "sin_precio+crudo": {"usar_precio": False, "escalar_target": False},
    "sin_precio+escalado": {"usar_precio": False, "escalar_target": True},
}

HORIZONTES = (1, 3, 6, 12)


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
        help="Productos POR CUADRANTE. 100 reproduce la muestra de la tabla de M1.7 (§5.2). "
        "0 corre el catálogo completo, que NO es comparable contra esa tabla.",
    )
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument(
        "--variantes",
        nargs="*",
        choices=sorted(VARIANTES),
        default=sorted(VARIANTES),
        help="Cuáles correr. Por defecto las cuatro.",
    )
    parser.add_argument("--checkpoint-dir", type=Path, default=None)
    parser.add_argument("--salida-dir", type=Path, default=BACKTESTS)
    return parser.parse_args(argv)


def _metricas(reporte: pd.DataFrame, nivel: list[str] | None, etiqueta: str) -> pd.DataFrame:
    """WAPE + sesgo + cobertura por horizonte, en el formato de siempre."""
    del_horizonte = reporte[reporte["horizonte"].isin(HORIZONTES)]
    w = wape(del_horizonte, ["horizonte"], columna_pred="pred", columnas_nivel=nivel)
    s = sesgo(del_horizonte, ["horizonte"], columna_pred="pred", columnas_nivel=nivel)
    tabla = w.merge(s[["horizonte", "sesgo"]], on="horizonte")
    tabla.insert(0, "nivel", etiqueta)
    return tabla


def _metricas_por_cuadrante(reporte: pd.DataFrame) -> pd.DataFrame:
    del_horizonte = reporte[reporte["horizonte"].isin(HORIZONTES)]
    grupo = ["cuadrante", "horizonte"]
    w = wape(del_horizonte, grupo, columna_pred="pred")
    s = sesgo(del_horizonte, grupo, columna_pred="pred")
    return w.merge(s[[*grupo, "sesgo"]], on=grupo)


def _correr_variante(
    nombre: str,
    configuracion: dict,
    hechos: pd.DataFrame,
    catalogo: pd.DataFrame,
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, float]:
    predictor = functools.partial(predecir_global, **configuracion)
    checkpoint = args.checkpoint_dir / nombre if args.checkpoint_dir else None

    inicio = time.perf_counter()
    reporte = ejecutar_backtest(
        hechos,
        lambda h, c, hm, aux: predictor(h, c, hm, aux),
        n_cortes=args.n_cortes,
        horizonte_max=args.horizonte_max,
        tablas_auxiliares={"catalogo": catalogo},
        directorio_checkpoint=checkpoint,
    )
    duracion = time.perf_counter() - inicio
    # `.attrs` se pierde en rename/merge (trampa de roadmap-motor.md §12.2) y sin la
    # corrida `a_markdown` marca la tabla como no congelable. Se toma antes de transformar.
    corrida = reporte.attrs.get("corrida")
    reporte = reporte.rename(columns={NOMBRE_MODELO: "pred"})
    reporte = etiquetar(reporte, clasificar_series(hechos))
    if "categoria" in catalogo.columns:
        reporte = reporte.merge(
            catalogo[["id_producto", "categoria"]].drop_duplicates("id_producto"),
            on="id_producto",
            how="left",
        )
    reporte.attrs["corrida"] = corrida
    return reporte, duracion


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

    conteo_cuadrantes: dict[str, int] = {}
    productos_totales = hechos["id_producto"].nunique()
    if args.estratificado:
        hechos, conteo_cuadrantes = muestra_estratificada(
            hechos, args.estratificado, args.semilla
        )

    print(
        f"{len(args.variantes)} variantes sobre {hechos['id_producto'].nunique()} productos "
        f"x {args.n_cortes} cortes (h={args.horizonte_max})",
        flush=True,
    )

    filas, por_cuadrante, tiempos, corrida = [], [], {}, None
    for nombre in args.variantes:
        reporte, duracion = _correr_variante(nombre, VARIANTES[nombre], hechos, catalogo, args)
        tiempos[nombre] = duracion
        corrida = corrida or reporte.attrs.get("corrida")
        print(f"  {nombre:20s} {duracion / 60:5.1f} min", flush=True)
        # Los tres niveles de ADR-008. El gate de M2 se decide en producto y categoría; el
        # total es el que usa el criterio de sesgo de ±5%.
        niveles: list[tuple[list[str] | None, str]] = [(None, "producto"), ([], "total")]
        if "categoria" in reporte.columns:
            niveles.insert(1, (["categoria"], "categoria"))
        for nivel, etiqueta in niveles:
            tabla = _metricas(reporte, nivel, etiqueta)
            tabla.insert(0, "variante", nombre)
            filas.append(tabla)
        # El corte por cuadrante lo exige el gate de M1.2, y acá es el que más importa:
        # el 42% de series intermitentes es donde el global tiene más para ganar o perder.
        cuadrantes = _metricas_por_cuadrante(reporte)
        cuadrantes.insert(0, "variante", nombre)
        por_cuadrante.append(cuadrantes)

    tablas = {
        "por_variante": pd.concat(filas, ignore_index=True),
        "por_cuadrante": pd.concat(por_cuadrante, ignore_index=True),
        "costo": pd.DataFrame(
            {"variante": list(tiempos), "minutos": [round(t / 60, 1) for t in tiempos.values()]}
        ),
    }
    if corrida is not None:
        # Todas las variantes comparten `id`: el hash no incluye el predictor. Justamente
        # por eso los checkpoints van en directorios separados (ver el encabezado).
        tablas["corrida"] = corrida.como_fila()

    fecha = datetime.now(tz=UTC).date().isoformat()
    md = a_markdown(
        tablas,
        titulo=f"Ablaciones del modelo global — {args.etiqueta} ({fecha})",
        notas=_notas(args, hechos, productos_totales, conteo_cuadrantes),
    )
    args.salida_dir.mkdir(parents=True, exist_ok=True)
    destino = args.salida_dir / f"ablaciones-global-{args.etiqueta}-{fecha}.md"
    destino.write_text(md, encoding="utf-8")
    print(f"\nEscrito: {destino}")
    return 0


def _notas(
    args: argparse.Namespace,
    hechos: pd.DataFrame,
    productos_totales: int,
    conteo_cuadrantes: dict[str, int],
) -> str:
    lineas = [
        f"Modelo global LightGBM (`{NOMBRE_MODELO}`), multi-horizonte directo con "
        f"`max_horizon={args.horizonte_max}`.",
        "",
        f"- **Productos:** {hechos['id_producto'].nunique()} de {productos_totales} · "
        f"**cortes:** {args.n_cortes} · **horizonte:** {args.horizonte_max}",
        f"- **Cobertura esperada por longitud de serie:** {cobertura_esperada(hechos):.4f} — "
        "fracción de series con historia suficiente para que `mlforecast` genere los lags. "
        "Es la **cota superior** de la cobertura del global, así que una cobertura baja en "
        "la tabla no necesariamente es del modelo.",
    ]
    if conteo_cuadrantes:
        detalle = " · ".join(f"{c}: {n}" for c, n in sorted(conteo_cuadrantes.items()))
        lineas += [
            f"- **Muestreo:** estratificado, hasta {args.estratificado} por cuadrante, "
            f"semilla {args.semilla} → {detalle}",
        ]
    lineas += [
        "",
        "> **Esto NO es el piso ni un champion/challenger.** El gate de M2.3 es que el "
        "modelo corra dentro del arnés y sea comparable; elegir dónde reemplaza al baseline "
        "es M2.5, y ahí rige la selección prospectiva de ADR-016. Esta tabla solo decide "
        "**con qué configuración** el global llega a esa comparación.",
        "",
        "> **El sintético no valida calidad predictiva** — reproduce propiedades "
        "estadísticas, no la señal del negocio. Sirve para comparar variantes entre sí "
        "(mismo dataset, misma muestra), no para anticipar el número real.",
    ]
    return "\n".join(lineas)


if __name__ == "__main__":
    raise SystemExit(main())
