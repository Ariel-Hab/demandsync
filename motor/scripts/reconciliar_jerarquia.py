"""Reconciliación jerárquica sobre la estructura agrupada (M3.1, `roadmap-motor.md` §7.2).

    motor/.venv/Scripts/python motor/scripts/reconciliar_jerarquia.py \\
        --hechos C:/dfv-extract-v2 --etiqueta real --estratificado 0 \\
        --checkpoints-baselines C:/dfv-checkpoints-2026-08-03 \\
        --checkpoints-global    C:/dfv-checkpoints-intervalos \\
        --checkpoints-agregados C:/dfv-checkpoints-agregados

## Qué hace, en orden

1. Construye la estructura agrupada `total → {categoría, laboratorio} → producto` (§7.2).
2. **Corre el backtest de las 296 series agregadas** — es la parte cara y la única que ajusta
   modelos. Con `--checkpoints-agregados` se reanuda.
3. Relee los checkpoints de producto y arma el `champion` con selección prospectiva, igual
   que M2.5.
4. Reconcilia con los cuatro métodos y emite `backtests/reconciliacion-<etiqueta>-<fecha>.md`.

## ⚠️ Dos desvíos que hay que tener a la vista al leer la tabla

**Arriba compiten 6 candidatos y abajo 9.** Faltan dos en los niveles agregados, cada uno por
su motivo, y los dos están medidos:

1. **`GlobalLGBM` (defecto de M2.3).** `predecir_global` con `usar_precio=False` **debería**
   aceptar una serie sin precio —su propio mensaje de error lo ofrece como salida
   (`modelo_global.py:287`)— pero `_armar_entrenamiento` llama igual a `construir_features`,
   que ajusta la deflación y exige `precio_prom` **y** `revenue`. Una serie agregada no tiene
   ninguna: el precio de "la categoría CLINICO" no existe. Arreglarlo es chico, pero toca un
   camino con tablas congeladas y merece su propia verificación, no colarse acá.
2. **`AutoTheta` (costo).** Ver `BASELINES_AGREGADOS`: sobre series agregadas se lleva el
   **89,7%** del tiempo, y con él las 296 series por 18 cortes son **13 horas** contra 1,4.

**Qué implica, dicho antes de mirar los números.** `bottom_up` **no se ve afectado** —no usa
los pronósticos agregados, solo suma los de producto—, así que el piso declarado de la unidad
está limpio. Los que sí quedan con un base más pobre arriba son MinT y la columna
`sin_reconciliar` en los niveles altos. **Si MinT gana, la conclusión vale con más razón; si
pierde, no se puede separar cuánto es del método y cuánto del base recortado** — y en ese caso
la corrida completa (13 h, con los 5 baselines y el global arreglado) es el desempate.

## Cómo se lee la tabla

El piso de esta unidad es **`bottom_up`**, no el champion sin reconciliar: bottom-up sale
gratis de sumar las predicciones de producto que ya están en los checkpoints, así que MinT
tiene que ganarle *a él* para justificar las 296 series agregadas. Y **reconciliar puede
empeorar el grano producto y mejorar los agregados**: es un resultado legítimo y por eso la
tabla va abierta por nivel, no resumida.
"""

import argparse
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from motor.backtesting.arnes import ejecutar_backtest
from motor.backtesting.checkpoints import cargar_desde_checkpoints, cruzar_reportes
from motor.backtesting.metricas import sesgo, wape
from motor.backtesting.reporte import a_markdown
from motor.clasificacion import muestra_estratificada
from motor.datos.archivos import RepositorioArchivos
from motor.modelado.baselines import predecir_baselines
from motor.modelado.intermitentes import predecir_intermitentes
from motor.modelado.modelo_global import NOMBRE_MODELO, nombre_de_cuantil
from motor.modelado.seleccion import (
    CANDIDATOS,
    armar_reporte_con_cascada,
    elegir_mejor_por_corte,
)
from motor.reconciliacion import (
    METODOS,
    construir_estructura,
    reconciliar,
    verificar_coherencia,
)

RAIZ_REPO = Path(__file__).resolve().parents[2]
HECHOS_SINTETICO = RAIZ_REPO / "datasets" / "sintetico" / "salida" / "hechos"
BACKTESTS = RAIZ_REPO / "motor" / "backtests"

COLUMNA_BASE = "champion"
MEDIANA_GLOBAL = nombre_de_cuantil(0.5)
CANDIDATOS_BASE = [*CANDIDATOS, NOMBRE_MODELO, MEDIANA_GLOBAL]

BASELINES_AGREGADOS = ["SeasonalNaive", "WindowAverage", "AutoETS", "AutoARIMA"]
"""Los baselines que corren sobre las series agregadas: **los 5 menos `AutoTheta`**.

Medido, no elegido (§7.2). Sobre una serie agregada —densa, 95 meses sin huecos— `AutoTheta`
cuesta **7,97 s/serie/corte contra 0,81 de `AutoARIMA`**: el **89,7%** del tiempo total. Con
los 5, las 296 series por 18 cortes son **13 horas**; sin él, **1,4**. Es exactamente al revés
que a grano producto, donde §6.5 midió que el caro era `AutoARIMA` — el modelo caro depende de
la forma de la serie, no del modelo.

Los intermitentes (`CrostonSBA`, `TSB`) sí corren: cuestan 0,4 s para las 6 series de la
medición, o sea nada."""
CANDIDATOS_AGREGADOS = [*BASELINES_AGREGADOS, "CrostonSBA", "TSB"]


def parsear_argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--hechos", type=Path, default=HECHOS_SINTETICO)
    parser.add_argument("--etiqueta", default="sintetico")
    parser.add_argument("--checkpoints-baselines", type=Path, required=True)
    parser.add_argument("--checkpoints-global", type=Path, required=True)
    parser.add_argument(
        "--checkpoints-agregados",
        type=Path,
        required=True,
        help="Directorio PROPIO para el backtest de las series agregadas. Son otros datos, "
        "así que el `id` de corrida no puede chocar con el de producto — pero el "
        "directorio separado es igual la práctica de §12.2.",
    )
    parser.add_argument("--n-cortes", type=int, default=18)
    parser.add_argument("--horizonte-max", type=int, default=12)
    parser.add_argument("--n-jobs", type=int, default=4)
    parser.add_argument("--estratificado", type=int, default=100)
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--salida-dir", type=Path, default=BACKTESTS)
    return parser.parse_args(argv)


def _predecir_agregados(
    historia: pd.DataFrame,
    corte: pd.Timestamp,
    horizonte_max: int,
    columna_id: str = "id_producto",
    columna_fecha: str = "anio_mes",
    columna_objetivo: str = "unidades",
    n_jobs: int = 1,
) -> pd.DataFrame:
    """Los candidatos que corren sobre una serie agregada — ver `BASELINES_AGREGADOS`."""
    baselines = predecir_baselines(
        historia, corte, horizonte_max, columna_id, columna_fecha, columna_objetivo,
        n_jobs=n_jobs, modelos=BASELINES_AGREGADOS,
    )
    intermitentes = predecir_intermitentes(
        historia, corte, horizonte_max, columna_id, columna_fecha, columna_objetivo,
        n_jobs=n_jobs,
    )
    return baselines.merge(intermitentes, on=[columna_id, columna_fecha])


def _champion(reporte: pd.DataFrame, hechos: pd.DataFrame, modelos: list[str]) -> pd.DataFrame:
    """Selección prospectiva + cascada (ADR-016) sobre los candidatos que se le pasen."""
    ranking = elegir_mejor_por_corte(reporte, hechos, modelos=modelos)
    return armar_reporte_con_cascada(
        reporte, ranking, modelos=modelos, columna_pred=COLUMNA_BASE
    )


def _hechos_de_agregados(estructura, series: list[str]) -> pd.DataFrame:
    """Las series agregadas en el formato que consume el arnés (`id_producto`/`anio_mes`).

    **`precio_prom` va en `NaN` a propósito, y esquiva un bug latente de M2.3.** Una serie
    agregada no tiene precio: el precio de "la categoría CLINICO" no existe. `predecir_global`
    con `usar_precio=False` debería aceptar eso —su propio mensaje de error lo ofrece como
    salida (`modelo_global.py:287`)— pero `_armar_entrenamiento` llama igual a
    `construir_features`, que ajusta la deflación y **exige la columna**. La promesa del
    mensaje no se cumple.

    Se resuelve acá y no en `modelo_global` porque tocar el camino de M2.3 tiene tablas
    congeladas colgando y merece su propia verificación. Queda anotado como defecto en §7.2.
    Con la columna en `NaN` la deflación no encuentra precios utilizables, las features salen
    nulas y `usar_precio=False` las descarta antes de entrenar: el modelo queda con lags,
    calendario y estáticas, que es exactamente lo que se quiere arriba.
    """
    Y = estructura.Y_df.reset_index()
    de_interes = Y[Y["unique_id"].isin(series)]
    return de_interes.rename(
        columns={"unique_id": "id_producto", "ds": "anio_mes", "y": "unidades"}
    )[["id_producto", "anio_mes", "unidades"]].assign(precio_prom=float("nan"))


def _tabla_por_nivel(base: pd.DataFrame, columnas: dict[str, str]) -> pd.DataFrame:
    """WAPE, sesgo y cobertura por (nivel, horizonte) para cada contendiente."""
    filas = []
    for nombre, columna in columnas.items():
        comun = {
            "columnas_grupo": ["nivel", "horizonte"],
            "columna_real": "y",
            "columna_pred": columna,
            "columnas_nivel": ["unique_id"],
            "columna_fecha": "ds",
        }
        tabla = wape(base, **comun)
        tabla["sesgo"] = sesgo(base, **comun)["sesgo"]
        tabla.insert(0, "contendiente", nombre)
        filas.append(tabla)
    resultado = pd.concat(filas, ignore_index=True)
    orden = pd.CategoricalDtype(list(columnas), ordered=True)
    resultado["contendiente"] = resultado["contendiente"].astype(orden)
    return resultado.sort_values(["nivel", "horizonte", "contendiente"]).reset_index(drop=True)


def main(argv: list[str] | None = None) -> int:  # noqa: PLR0915
    args = parsear_argumentos(argv)
    if not args.hechos.exists():
        print(f"No hay hechos en {args.hechos}.", file=sys.stderr)
        return 1

    repo = RepositorioArchivos(args.hechos)
    hechos = repo.hecho_venta_mensual_producto()
    catalogo = repo.catalogo_producto()
    if args.estratificado:
        hechos, _ = muestra_estratificada(hechos, args.estratificado, args.semilla)

    inicio = time.perf_counter()
    print("Construyendo la estructura agrupada...", flush=True)
    estructura = construir_estructura(hechos, catalogo)
    agregadas = [s for s in estructura.S.index if s not in set(estructura.series_base)]
    print(
        f"  {len(estructura)} series: {len(agregadas)} agregadas + "
        f"{len(estructura.series_base)} producto",
        flush=True,
    )

    comun = {"n_cortes": args.n_cortes, "horizonte_max": args.horizonte_max}

    print(f"\nBacktest de las {len(agregadas)} series agregadas (la parte cara)...", flush=True)
    t_agg = time.perf_counter()
    reporte_agg = ejecutar_backtest(
        _hechos_de_agregados(estructura, agregadas),
        lambda h, c, hm, **kw: _predecir_agregados(h, c, hm, n_jobs=args.n_jobs, **kw),
        directorio_checkpoint=args.checkpoints_agregados,
        **comun,
    )
    print(f"  {(time.perf_counter() - t_agg) / 60:.1f} min · {len(reporte_agg)} filas", flush=True)

    print("\nReleyendo los checkpoints de producto...", flush=True)
    baselines = cargar_desde_checkpoints(hechos, args.checkpoints_baselines, **comun)
    global_ = cargar_desde_checkpoints(hechos, args.checkpoints_global, **comun)
    reporte_prod = cruzar_reportes({"baselines": baselines, "global": global_})

    print("Armando el champion en los dos lados...", flush=True)
    prod = _champion(reporte_prod, hechos, CANDIDATOS_BASE)
    # 6 y no 9 arriba: ver los dos desvíos declarados en el encabezado del módulo.
    agg = _champion(
        reporte_agg, _hechos_de_agregados(estructura, agregadas), CANDIDATOS_AGREGADOS
    )

    # El `unique_id` de producto es la ruta completa; el de las agregadas ya lo es.
    ruta = dict(zip(estructura.series_base, estructura.series_base))
    de_producto = {int(s.split("/")[-1]): s for s in estructura.series_base}
    prod = prod.assign(unique_id=prod["id_producto"].map(de_producto))
    agg = agg.rename(columns={"id_producto": "unique_id"})
    del ruta

    columnas = ["unique_id", "anio_mes", "corte", "horizonte", "real", COLUMNA_BASE]
    base = pd.concat([prod[columnas], agg[columnas]], ignore_index=True).rename(
        columns={"anio_mes": "ds", "real": "y"}
    )
    base = base[base["unique_id"].notna()]
    print(f"  base combinado: {len(base)} filas · {base['unique_id'].nunique()} series")

    print("\nReconciliando...", flush=True)
    t_rec = time.perf_counter()
    reconciliado = reconciliar(base, estructura, columna_modelo=COLUMNA_BASE)
    print(f"  {(time.perf_counter() - t_rec) / 60:.1f} min", flush=True)

    reconciliado["nivel"] = reconciliado["unique_id"].map(estructura.niveles)
    contendientes = {"sin_reconciliar": COLUMNA_BASE}
    contendientes.update({metodo: f"pred_{metodo}" for metodo in METODOS})

    tablas = {"por_nivel": _tabla_por_nivel(reconciliado, contendientes)}

    coherencia = []
    for metodo in METODOS:
        for corte in sorted(reconciliado["corte"].dropna().unique()):
            del_corte = reconciliado[
                (reconciliado["corte"] == corte) & (reconciliado["ds"] > corte)
            ]
            incoherentes = verificar_coherencia(
                del_corte[["unique_id", "ds", f"pred_{metodo}"]],
                estructura,
                columna_valor=f"pred_{metodo}",
            )
            coherencia.append(
                {"metodo": metodo, "corte": corte, "celdas_incoherentes": len(incoherentes)}
            )
    tablas["coherencia"] = (
        pd.DataFrame(coherencia)
        .groupby("metodo", as_index=False)["celdas_incoherentes"]
        .sum()
    )

    duracion = time.perf_counter() - inicio
    fecha = datetime.now(tz=UTC).date().isoformat()
    md = a_markdown(
        tablas,
        titulo=f"Reconciliación jerárquica sobre estructura agrupada — "
        f"{args.etiqueta} ({fecha})",
        notas=_notas(args, estructura, agregadas, base, duracion),
    )
    args.salida_dir.mkdir(parents=True, exist_ok=True)
    destino = args.salida_dir / f"reconciliacion-{args.etiqueta}-{fecha}.md"
    destino.write_text(md, encoding="utf-8")
    print(f"\n{duracion / 60:.1f} min · Escrito: {destino}")
    return 0


def _notas(args, estructura, agregadas, base, duracion) -> str:
    return "\n".join(
        [
            "M3.1 (`roadmap-motor.md` §7.2). **Estructura agrupada, no árbol:** 47 de 77 "
            "laboratorios venden en más de una categoría y cubren el 89% de los productos, "
            "así que `laboratorio` no está anidado en `categoria`.",
            "",
            f"- **Series:** {len(estructura)} = {len(agregadas)} agregadas + "
            f"{len(estructura.series_base)} producto · **cortes:** {args.n_cortes} · "
            f"**horizonte:** {args.horizonte_max} · **filas:** {len(base)} · "
            f"**{duracion / 60:.1f} min**",
            "- **Base:** selección prospectiva + cascada (ADR-016) en los cinco niveles, "
            "con **9 candidatos a grano producto y 7 en los agregados**.",
            "- ⚠️ **El desvío:** las series agregadas **no llevan `GlobalLGBM`**. Una serie "
            "agregada no tiene `precio_prom` ni `revenue` —el precio de \"la categoría "
            "CLINICO\" no existe— y `construir_features` los exige aunque el modelo corra "
            "con `usar_precio=False`. Es un defecto de M2.3 anotado en §7.2. **`bottom_up` "
            "no se ve afectado** (solo suma producto), así que el piso de la unidad está "
            "limpio; MinT y `sin_reconciliar` sí quedan con un base más pobre arriba. Si "
            "MinT gana, vale con más razón; si pierde, el resultado está confundido.",
            "- **La covarianza de `mint_shrink` se estima prospectivamente:** en el corte "
            "`t`, solo residuos de meses ya ocurridos. Sin eso el hindsight quedaría adentro "
            "de la matriz de pesos, donde no lo ve nadie.",
            "",
            "> **El piso de esta unidad es `bottom_up`, no `sin_reconciliar`.** Bottom-up "
            "sale gratis de sumar las predicciones de producto que ya estaban en los "
            "checkpoints; MinT tiene que ganarle **a él** para justificar predecir las "
            f"{len(agregadas)} series agregadas.",
            "",
            "> **Reconciliar puede empeorar producto y mejorar los agregados.** Es un "
            "resultado legítimo, y por eso la tabla va abierta por nivel. ADR-018 puso el "
            "criterio de aceptación de R2 en total y categoría, así que hay incentivo a "
            "leerla por donde conviene: no se hace.",
            "",
            "> **Coherencia:** `S · base` reproduce los niveles agregados. La tabla de abajo "
            "cuenta celdas fuera de tolerancia; tiene que dar **0** para todos los métodos. "
            "La tolerancia es relativa porque `hierarchicalforecast` castea `S` a `float32`.",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
