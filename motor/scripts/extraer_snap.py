"""Extrae los hechos mensuales reales del snap MySQL del cliente (M1.8).

Produce los dos parquets que `RepositorioArchivos` necesita para correr el piso real:

    hecho_venta_mensual_producto.parquet
    catalogo_producto.parquet

y después se corre el mismo camino de M1.7:

    motor/.venv/Scripts/python motor/scripts/extraer_snap.py --salida D:/dfv/extract
    motor/.venv/Scripts/python motor/scripts/congelar_baselines_sintetico.py \
        --hechos D:/dfv/extract --etiqueta real --n-jobs 4 --checkpoint-dir D:/dfv/checkpoints

**Extract ad-hoc, NO el ETL de R1** (roadmap-motor.md §3): esto existe para validar
calidad del motor contra datos reales, no para alimentar producción. El ETL productivo
lo construye Backend en R1 desde el contrato de ingesta, y va a definir "venta mensual"
por su cuenta. Toda diferencia entre ambos es un hallazgo a documentar (§9, riesgos),
no algo a emparchar acá.

## De dónde sale la SQL

La agregación es la de `cotizaciones/backend/src/modules/snap/ventas/repository.py`
(`obtener_ventas_por_periodo`), que ya corre en producción contra esta misma base con
los filtros que el EDA documentó. Se reusa a propósito: es código probado contra el
esquema real. Tres diferencias deliberadas, ver `_SQL_HECHOS`.

Costo del acoplamiento, declarado: un cambio de esquema del ERP rompe dos repos. Es
aceptable porque este extract es ad-hoc y de un solo uso por corrida.

## Credenciales

Las mismas variables de entorno que usa cotizaciones — `DB_SNAP_URL`, o el conjunto
`DB_DFV_PROD_SNAP_HOST / PORT / NAME / USER / PASS`. **Nada de esto se escribe en el
repo**: cargalas en la sesión antes de correr (ver `scripts/README.md`).

## La salida son datos reales del cliente

Filas producto × mes del ERP. Regla de oro de CLAUDE.md §4: no entran al repo. El
script se niega a escribir en una ruta versionada.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

RAIZ_REPO = Path(__file__).resolve().parents[2]

# Referencias del EDA 2026-07-15 (`motor/eda/eda-2026-07-15.md`). El extract se valida
# contra estos números: si no los reproduce, el problema es el extract y conviene
# enterarse en dos minutos y no después de ocho horas de backtest.
EDA_PRIMER_MES = "2018-07"
EDA_PRODUCTOS_ACTIVOS_36M = 2189
EDA_CATEGORIAS = 12
TOLERANCIA_PRODUCTOS = 0.10

# Filtros del ERP, idénticos a los de cotizaciones y a los que el EDA declara en su
# encabezado. `estadistica ∈ {P,N}` son renglones que el propio sistema del cliente
# excluye de estadística; el REGEXP descarta servicios y conceptos, cuyo código no es
# numérico; `precio > 0` saca los renglones rotos.
_FILTROS = """
      {alias_cab}.fecha >= :desde
      AND {alias_cab}.fecha <= :hasta
      AND {alias_det}.producto_id REGEXP '^[0-9]+$'
      AND COALESCE({alias_det}.estadistica, '') NOT IN ('P', 'N')
      AND COALESCE({alias_det}.precio, 0) > 0
"""

# Tres diferencias deliberadas contra la query de cotizaciones:
#
# 1. Agrupa por producto, no por cliente × producto. NO alcanza con sumar la salida de
#    aquélla: su `HAVING cantidad_total != 0` filtra a nivel cliente × producto, así que
#    un cliente con neto cero en el mes desaparece y se lleva su revenue puesto.
# 2. Sin `HAVING`: los meses de neto cero se conservan. Son demanda cero explícita
#    (ADR-010), no ausencia de dato.
# 3. El revenue conserva el signo. Cotizaciones lo anula cuando no es positivo; acá es
#    el numerador del índice implícito de precio (ADR-002) y se necesita con signo.
#
# El mes se arma en pandas desde (anio, mes) en vez de con DATE_FORMAT: evita el
# escapado de `%` entre SQLAlchemy y pymysql, y deja la conversión en código testeable.
_SQL_HECHOS = f"""
SELECT
    src.producto_id,
    YEAR(src.fecha)  AS anio,
    MONTH(src.fecha) AS mes,
    SUM(CASE WHEN src.nota_credito = 1 THEN -src.cantidad ELSE src.cantidad END)
        AS unidades,
    SUM(CASE WHEN src.nota_credito = 1
             THEN -(src.cantidad * COALESCE(src.precio, 0))
             ELSE  (src.cantidad * COALESCE(src.precio, 0)) END)
        AS revenue
FROM (
    SELECT r.fecha, r.nota_credito, pr.producto_id, pr.cantidad, pr.precio
    FROM producto_remito pr
    INNER JOIN remito r
        ON pr.remito_tipo = r.tipo AND pr.remito_numero = r.numero
    WHERE {_FILTROS.format(alias_cab="r", alias_det="pr")}
    UNION ALL
    SELECT f.fecha, f.nota_credito, pf.producto_id, pf.cantidad, pf.precio
    FROM producto_factura pf
    INNER JOIN factura f
        ON pf.factura_tipo = f.tipo AND pf.factura_numero = f.numero
    WHERE {_FILTROS.format(alias_cab="f", alias_det="pf")}
) AS src
GROUP BY src.producto_id, YEAR(src.fecha), MONTH(src.fecha)
"""

# Renglones crudos de un mes, para el cross-check pandas vs SQL (--verificar-mes).
_SQL_RENGLONES_MES = f"""
SELECT r.fecha, r.nota_credito, pr.producto_id, pr.cantidad, pr.precio
FROM producto_remito pr
INNER JOIN remito r ON pr.remito_tipo = r.tipo AND pr.remito_numero = r.numero
WHERE {_FILTROS.format(alias_cab="r", alias_det="pr")}
UNION ALL
SELECT f.fecha, f.nota_credito, pf.producto_id, pf.cantidad, pf.precio
FROM producto_factura pf
INNER JOIN factura f ON pf.factura_tipo = f.tipo AND pf.factura_numero = f.numero
WHERE {_FILTROS.format(alias_cab="f", alias_det="pf")}
"""


# ---------------------------------------------------------------------------
# Transformación — funciones puras, testeables sin base (test_scripts_extraer.py)
# ---------------------------------------------------------------------------


def _es_nota_credito(valor) -> bool:
    """`nota_credito` es un `BIT(1)` en MySQL y pymysql lo devuelve como **bytes**.

    Verificado contra la base: llega `b'\\x01'`, no `1`. Un `astype(int)` sobre eso
    explota, y —peor— cualquier comparación laxa con `== 1` daría `False` para TODA
    nota de crédito, o sea que las devoluciones sumarían en vez de restar y nadie se
    enteraría. Del lado SQL no pasa: MySQL evalúa `nota_credito = 1` sobre el BIT sin
    problema; el desajuste es solo de esta réplica en pandas.
    """
    if isinstance(valor, bytes):
        return any(valor)
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return False
    return bool(int(valor))


def netear_renglones(renglones: pd.DataFrame) -> pd.DataFrame:
    """Neteo mensual por producto en pandas: la misma cuenta que hace `_SQL_HECHOS`.

    Existe por dos motivos. Uno, es la única forma de tener la regla de neteo bajo test
    sin una base MySQL. Dos, `--verificar-mes` la corre sobre los renglones crudos de un
    mes y compara contra lo que devolvió la SQL: si difieren, el join o el signo están
    mal, y eso es exactamente el error que produciría un piso equivocado sin avisar.

    Espera las columnas `fecha`, `nota_credito`, `producto_id`, `cantidad`, `precio`.
    """
    df = renglones.copy()
    signo = df["nota_credito"].map(_es_nota_credito).map(lambda nc: -1 if nc else 1)
    df["unidades"] = signo * df["cantidad"].astype("float64")
    df["revenue"] = df["unidades"] * df["precio"].fillna(0).astype("float64")

    fechas = pd.to_datetime(df["fecha"])
    agregado = (
        df.assign(anio=fechas.dt.year, mes=fechas.dt.month)
        .groupby(["producto_id", "anio", "mes"], as_index=False)[["unidades", "revenue"]]
        .sum()
    )
    return agregado


def armar_hechos_producto(agregado: pd.DataFrame) -> pd.DataFrame:
    """`(producto_id, anio, mes, unidades, revenue)` → `hecho_venta_mensual_producto`.

    `precio_prom` es el índice implícito de ADR-002 (`revenue / unidades`), y con cero
    unidades **queda NaN, no infinito**: un mes de neto cero no tiene precio, y no
    declararlo faltante metería un infinito en la cadena de deflación de M2. Es el caso
    real de un mes cuya venta se canceló entera con nota de crédito.
    """
    df = agregado.copy()
    df["id_producto"] = df["producto_id"].astype("int64")
    df["anio_mes"] = pd.to_datetime(
        dict(year=df["anio"].astype(int), month=df["mes"].astype(int), day=1)
    )
    df["unidades"] = df["unidades"].astype("float64")
    df["revenue"] = df["revenue"].astype("float64")

    unidades = df["unidades"]
    df["precio_prom"] = (df["revenue"] / unidades.where(unidades != 0)).astype("float64")

    columnas = ["id_producto", "anio_mes", "unidades", "revenue", "precio_prom"]
    return df[columnas].sort_values(["id_producto", "anio_mes"]).reset_index(drop=True)


def resolver_variantes(agregado: pd.DataFrame) -> pd.DataFrame:
    """Mapea cada `id_producto` entero al código de texto que efectivamente vendió.

    **`producto.id` es `varchar(255)`, no un entero** (verificado contra la base): en el
    catálogo conviven `'2'`, `'02'` y `'0002'` como tres productos DISTINTOS, con
    proveedor y estado distintos, que colapsan al mismo `int64` que exige el diccionario.
    Son 23 colisiones sobre 9.486 entradas.

    Sin esto, filtrar el catálogo por el id entero deja las tres filas, y el `merge` que
    arma el reporte —un left join— **multiplica cada fila de predicción de ese producto
    por tres**. No falla: infla `n` y corrompe todos los WAPE y sesgos de la tabla.

    Devuelve `(id_producto, id_texto)`. Corta si dos variantes de texto del mismo número
    tienen ventas: ahí colapsarlas fusionaría dos productos reales en una serie, y eso
    no se arregla eligiendo una.
    """
    variantes = agregado[["producto_id"]].drop_duplicates().copy()
    variantes["id_texto"] = variantes["producto_id"].astype(str)
    variantes["id_producto"] = variantes["producto_id"].astype("int64")

    chocan = variantes[variantes["id_producto"].duplicated(keep=False)]
    if not chocan.empty:
        detalle = chocan.sort_values("id_producto").head(20).to_dict("records")
        raise SystemExit(
            "Dos códigos de texto distintos del mismo número tienen ventas, así que "
            "castear a int64 fusionaría dos productos reales en una serie: "
            f"{detalle}\nHay que decidir con el dueño del ERP cuál es cuál antes de "
            "correr el piso."
        )
    return variantes[["id_producto", "id_texto"]]


def filtrar_universo(hechos: pd.DataFrame, meses_actividad: int) -> pd.DataFrame:
    """Deja los productos con alguna venta en los últimos `meses_actividad` meses.

    El catálogo tiene ~10.500 entradas pero solo ~2.200 con venta reciente (EDA §1).
    Correr el backtest sobre las 8.000 restantes multiplicaría el cómputo por cuatro y
    metería series todo-ceros que **bajan el WAPE del piso sin que nadie prediga mejor**.
    La ventana es la misma con la que el EDA definió "producto activo".
    """
    if meses_actividad <= 0:
        return hechos

    ultimo = hechos["anio_mes"].max()
    desde = ultimo - pd.DateOffset(months=meses_actividad - 1)
    con_venta = hechos[(hechos["anio_mes"] >= desde) & (hechos["unidades"] > 0)]
    activos = con_venta["id_producto"].unique()
    return hechos[hechos["id_producto"].isin(activos)].reset_index(drop=True)


def validar_contra_eda(
    hechos: pd.DataFrame, catalogo: pd.DataFrame, meses_actividad: int
) -> list[tuple[bool, str, str]]:
    """Contrasta el extract contra el perfil del EDA. `(es_fatal, ok, detalle)`.

    Fatal es lo estructural (no hay datos, la historia no arranca donde debe, no están
    las 12 categorías): significa que la query o el join están mal. Lo cuantitativo va
    como aviso, porque el EDA se corrió en otra fecha y los conteos se mueven.
    """
    controles: list[tuple[bool, bool, str]] = []

    controles.append((True, not hechos.empty, f"filas devueltas: {len(hechos):,}"))
    if hechos.empty:
        return [(fatal, "FALLA" if not ok else "ok", txt) for fatal, ok, txt in controles]

    primer_mes = hechos["anio_mes"].min().strftime("%Y-%m")
    controles.append(
        (
            True,
            primer_mes == EDA_PRIMER_MES,
            f"primer mes: {primer_mes} (EDA: {EDA_PRIMER_MES})",
        )
    )

    meses = hechos["anio_mes"].nunique()
    esperados = (
        (hechos["anio_mes"].max().to_period("M") - hechos["anio_mes"].min().to_period("M")).n + 1
    )
    controles.append((True, meses == esperados, f"meses sin huecos: {meses} de {esperados}"))

    n_categorias = catalogo["categoria"].nunique()
    controles.append(
        (
            True,
            n_categorias == EDA_CATEGORIAS,
            f"categorías distintas: {n_categorias} (esperadas: {EDA_CATEGORIAS})",
        )
    )

    n_productos = hechos["id_producto"].nunique()
    piso = EDA_PRODUCTOS_ACTIVOS_36M * (1 - TOLERANCIA_PRODUCTOS)
    techo = EDA_PRODUCTOS_ACTIVOS_36M * (1 + TOLERANCIA_PRODUCTOS)
    controles.append(
        (
            False,
            piso <= n_productos <= techo,
            f"productos con venta en {meses_actividad}m: {n_productos:,} "
            f"(EDA: ~{EDA_PRODUCTOS_ACTIVOS_36M:,} ±{TOLERANCIA_PRODUCTOS:.0%})",
        )
    )

    negativos = int((hechos["unidades"] < 0).sum())
    controles.append(
        (False, True, f"meses con neto negativo (devoluciones): {negativos:,}")
    )
    ceros = int((hechos["unidades"] == 0).sum())
    controles.append((False, True, f"meses con neto exactamente cero: {ceros:,}"))
    sin_precio = int(hechos["precio_prom"].isna().sum())
    controles.append((False, True, f"meses sin precio_prom (neto cero): {sin_precio:,}"))

    return [(fatal, "ok" if ok else "FALLA", txt) for fatal, ok, txt in controles]


# ---------------------------------------------------------------------------
# Acceso a la base
# ---------------------------------------------------------------------------


def construir_url() -> str:
    """URL de conexión al snap desde las MISMAS variables que usa cotizaciones.

    No se inventa un mecanismo nuevo ni se guarda el secreto en otro lado: si la
    conexión ya existe en esa máquina, este script la reusa.
    """
    url = os.getenv("DB_SNAP_URL", "")
    if not url:
        host = os.getenv("DB_DFV_PROD_SNAP_HOST", "")
        port = os.getenv("DB_DFV_PROD_SNAP_PORT", "3306")
        name = os.getenv("DB_DFV_PROD_SNAP_NAME", "")
        user = os.getenv("DB_DFV_PROD_SNAP_USER", "")
        password = os.getenv("DB_DFV_PROD_SNAP_PASS", "")
        if not (host and name and user):
            raise SystemExit(
                "DB snap no configurada. Definí DB_SNAP_URL, o "
                "DB_DFV_PROD_SNAP_HOST / PORT / NAME / USER / PASS.\n"
                "Son las mismas variables que usa cotizaciones "
                "(backend/src/core/database_snap.py); cargalas en la sesión, no las "
                "escribas en el repo."
            )
        url = f"mysql://{user}:{password}@{host}:{port}/{name}"

    # `host.docker.internal` solo resuelve DENTRO de un contenedor. Cotizaciones corre
    # dockerizada y llega así al túnel SSH; este script corre nativo, y para él el mismo
    # túnel está en 127.0.0.1 (docker-compose.override.yml publica 3306 en el host).
    # Sin este remapeo la corrida muere recién a los ~60 s con un timeout opaco.
    if "host.docker.internal" in url:
        url = url.replace("host.docker.internal", "127.0.0.1")
        print(
            "  host.docker.internal -> 127.0.0.1 (el tunel SSH de cotizaciones esta "
            "publicado en el host; requiere `docker compose --profile dev up`)",
            flush=True,
        )

    # pymysql (sync) en vez del aiomysql de cotizaciones: esto es un batch de una
    # corrida, no un servicio; async no compra nada y complica el script.
    if url.startswith("mysql://"):
        url = url.replace("mysql://", "mysql+pymysql://", 1)
    return url


def _columnas_de_producto(conn) -> set[str]:
    from sqlalchemy import text

    filas = conn.execute(
        text(
            "SELECT COLUMN_NAME FROM information_schema.columns "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'producto'"
        )
    )
    return {fila[0] for fila in filas}


def leer_catalogo(conn) -> pd.DataFrame:
    """Catálogo con categoría y laboratorio, resolviendo los nombres de columna.

    La FK `producto` → `categoria_producto` no aparece en cotizaciones (usa su propio
    Postgres para categorizar), y el esquema es Grails, así que el nombre se descubre
    contra `information_schema` en vez de adivinarse. Es el mismo método que ese repo
    documenta haber usado para `categoria_producto_subcategoria_producto`.
    """
    from sqlalchemy import text

    columnas = _columnas_de_producto(conn)

    fk_categoria = next(
        (c for c in ("categoria_producto_id", "categoria_id") if c in columnas), None
    )
    if fk_categoria is None:
        raise SystemExit(
            "No encontré la FK de `producto` hacia `categoria_producto`. Columnas de "
            f"`producto`: {sorted(columnas)}\n"
            "Agregá la correcta a la lista de candidatas en leer_catalogo()."
        )

    laboratorio = (
        "CAST(p.proveedor_id AS CHAR)" if "proveedor_id" in columnas else "NULL"
    )
    activo = "NOT COALESCE(p.disabled, 0)" if "disabled" in columnas else "TRUE"

    # Mismo `REGEXP` que la query de ventas, y por el mismo motivo: el catálogo tiene
    # 10.533 entradas que incluyen servicios y conceptos, cuyo código no es numérico
    # (EDA §1). Verificado contra la base: hay ids vacíos. Sin este filtro el catálogo
    # no castea a int64 y el extract muere después de traerse todas las ventas.
    sql = f"""
        SELECT p.id                                   AS id_texto,
               p.id                                   AS id_producto,
               COALESCE(cp.nombre, 'SIN CATEGORIA')   AS categoria,
               COALESCE({laboratorio}, 'SIN LABORATORIO') AS laboratorio,
               {activo}                               AS activo
        FROM producto p
        LEFT JOIN categoria_producto cp ON cp.id = p.{fk_categoria}
        WHERE p.id REGEXP '^[0-9]+$'
    """
    catalogo = pd.read_sql(text(sql), conn)
    catalogo["id_texto"] = catalogo["id_texto"].astype(str)
    catalogo["id_producto"] = catalogo["id_producto"].astype("int64")
    catalogo["categoria"] = catalogo["categoria"].astype("object")
    catalogo["laboratorio"] = catalogo["laboratorio"].astype("object")
    catalogo["activo"] = catalogo["activo"].astype("bool")
    return catalogo


def verificar_mes(conn, mes: str) -> tuple[bool, str]:
    """Cross-check: netea en pandas los renglones crudos de un mes y compara con la SQL.

    Cubre lo que el test unitario no puede: que la SQL del servidor calcule lo mismo
    que la regla que sí está testeada. Un join mal escrito o un signo invertido cambia
    el piso entero sin producir ningún error.
    """
    from sqlalchemy import text

    periodo = pd.Period(mes, freq="M")
    limites = {
        "desde": periodo.start_time.strftime("%Y-%m-%d 00:00:00"),
        "hasta": periodo.end_time.strftime("%Y-%m-%d 23:59:59"),
    }

    renglones = pd.read_sql(text(_SQL_RENGLONES_MES), conn, params=limites)
    if renglones.empty:
        return False, f"{mes}: la base no devolvió renglones, no hay nada que verificar"

    esperado = armar_hechos_producto(netear_renglones(renglones))
    obtenido = armar_hechos_producto(pd.read_sql(text(_SQL_HECHOS), conn, params=limites))

    comparacion = esperado.merge(
        obtenido, on=["id_producto", "anio_mes"], how="outer", suffixes=("_pandas", "_sql")
    )
    difieren = comparacion[
        ~comparacion["unidades_pandas"].fillna(0).sub(
            comparacion["unidades_sql"].fillna(0)
        ).abs().le(1e-6)
        | ~comparacion["revenue_pandas"].fillna(0).sub(
            comparacion["revenue_sql"].fillna(0)
        ).abs().le(1e-2)
    ]
    if not difieren.empty:
        return False, (
            f"{mes}: pandas y SQL diferen en {len(difieren)} de {len(comparacion)} series. "
            "El join o el signo del neteo están mal — NO uses este extract."
        )
    return True, f"{mes}: pandas y SQL coinciden en {len(comparacion)} series"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _esta_versionado(destino: Path) -> bool:
    """True si `destino` cae dentro del repo y NO está gitignoreado.

    La salida son filas producto x mes del ERP real. Es la regla de oro de CLAUDE.md §4
    y no admite excepción por comodidad, así que el chequeo lo hace el script y no la
    memoria de quien lo corre.

    `resolve()` no es cosmético: con una ruta relativa como `motor/backtests`,
    `relative_to` tira `ValueError` y el destino pasaría por "fuera del repo" — que es
    exactamente el falso negativo que esta función existe para no tener.
    """
    try:
        destino.resolve().relative_to(RAIZ_REPO)
    except ValueError:
        return False

    sonda = destino.resolve() / "hecho_venta_mensual_producto.parquet"
    resultado = subprocess.run(
        ["git", "check-ignore", "-q", str(sonda)],
        cwd=RAIZ_REPO,
        capture_output=True,
    )
    return resultado.returncode != 0


def parsear_argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--salida",
        type=Path,
        required=True,
        help="Directorio donde escribir los parquets. Son datos reales del cliente: "
        "fuera del repo.",
    )
    parser.add_argument(
        "--desde",
        default=EDA_PRIMER_MES,
        help=f"Primer mes a extraer, AAAA-MM (default: {EDA_PRIMER_MES}, el primer "
        "comprobante según el EDA).",
    )
    parser.add_argument(
        "--hasta",
        default=None,
        help="Último mes a extraer, AAAA-MM. Default: el último mes COMPLETO. El mes "
        "en curso se excluye siempre: está contablemente abierto y su caída aparecería "
        "como demanda real.",
    )
    parser.add_argument(
        "--meses-actividad",
        type=int,
        default=36,
        help="Ventana para definir 'producto activo'. 0 extrae el catálogo entero "
        "(cuadruplica el cómputo del backtest, ver filtrar_universo).",
    )
    parser.add_argument(
        "--verificar-mes",
        default=None,
        help="Mes AAAA-MM para el cross-check pandas vs SQL. Default: el último "
        "extraído. `ninguno` lo saltea.",
    )
    return parser.parse_args(argv)


def _ultimo_mes_completo() -> str:
    return (pd.Timestamp.today().to_period("M") - 1).strftime("%Y-%m")


def main(argv: list[str] | None = None) -> int:
    args = parsear_argumentos(argv)

    try:
        from sqlalchemy import create_engine, text
    except ImportError:
        print("Falta SQLAlchemy en el venv.", file=sys.stderr)
        return 1

    if _esta_versionado(args.salida):
        print(
            f"{args.salida} está dentro del repo y NO está gitignoreada.\n"
            "La salida son filas producto × mes del ERP real: no puede quedar en una "
            "ruta versionada (CLAUDE.md §4). Elegí un directorio fuera del repo.",
            file=sys.stderr,
        )
        return 1

    hasta = args.hasta or _ultimo_mes_completo()
    limites = {
        "desde": pd.Period(args.desde, freq="M").start_time.strftime("%Y-%m-%d 00:00:00"),
        "hasta": pd.Period(hasta, freq="M").end_time.strftime("%Y-%m-%d 23:59:59"),
    }
    # Sin flechas ni `×` en lo que se imprime: la consola de Windows es cp1252 y un
    # U+2192 la hace crashear con UnicodeEncodeError a mitad de la corrida.
    print(f"Extrayendo {args.desde} -> {hasta} del snap...", flush=True)

    engine = create_engine(construir_url(), pool_pre_ping=True)
    with engine.connect() as conn:
        agregado = pd.read_sql(text(_SQL_HECHOS), conn, params=limites)
        print(f"  {len(agregado):,} filas producto-mes crudas", flush=True)

        hechos = armar_hechos_producto(agregado)
        catalogo = leer_catalogo(conn)
        print(f"  catálogo: {len(catalogo):,} productos", flush=True)

        mes_verificar = args.verificar_mes or hasta
        if mes_verificar != "ninguno":
            ok, detalle = verificar_mes(conn, mes_verificar)
            print(f"\nCross-check pandas vs SQL — {detalle}", flush=True)
            if not ok:
                return 1

    antes = hechos["id_producto"].nunique()
    hechos = filtrar_universo(hechos, args.meses_actividad)
    despues = hechos["id_producto"].nunique()
    if args.meses_actividad > 0:
        print(
            f"\nUniverso: {despues:,} productos con venta en {args.meses_actividad}m "
            f"(de {antes:,} con venta en la ventana completa)",
            flush=True,
        )

    # El catálogo se recorta por el código de TEXTO que vendió, no por el entero: ver
    # resolver_variantes(). Filtrar por el entero dejaría las variantes con ceros a la
    # izquierda y el merge del reporte multiplicaría filas en silencio.
    variantes = resolver_variantes(agregado)
    variantes = variantes[variantes["id_producto"].isin(hechos["id_producto"])]
    catalogo = catalogo.merge(variantes[["id_texto"]], on="id_texto", how="inner")
    catalogo = catalogo.drop(columns="id_texto")

    if catalogo["id_producto"].duplicated().any():
        print(
            "El catálogo quedó con id_producto repetidos: el merge del reporte "
            "multiplicaría filas y corrompería las métricas. No uses este extract.",
            file=sys.stderr,
        )
        return 1

    sin_catalogo = set(hechos["id_producto"]) - set(catalogo["id_producto"])
    if sin_catalogo:
        print(
            f"  OJO: {len(sin_catalogo):,} productos con ventas no están en `producto`. "
            "Sus filas quedan sin categoría en el reporte.",
            flush=True,
        )

    print("\nValidación contra el EDA:")
    hay_fatal = False
    for fatal, estado, detalle in validar_contra_eda(hechos, catalogo, args.meses_actividad):
        marca = "OK  " if estado == "ok" else ("FALLA" if fatal else "aviso")
        print(f"  [{marca}] {detalle}")
        hay_fatal = hay_fatal or (estado != "ok" and fatal)
    if hay_fatal:
        print(
            "\nHay controles estructurales en falla: la query o el join están mal. "
            "No uses este extract.",
            file=sys.stderr,
        )
        return 1

    args.salida.mkdir(parents=True, exist_ok=True)
    hechos.to_parquet(args.salida / "hecho_venta_mensual_producto.parquet", index=False)
    catalogo.to_parquet(args.salida / "catalogo_producto.parquet", index=False)
    print(f"\nEscrito en {args.salida}")
    print(
        f"  hecho_venta_mensual_producto.parquet — {len(hechos):,} filas, "
        f"{hechos['id_producto'].nunique():,} series"
    )
    print(f"  catalogo_producto.parquet — {len(catalogo):,} productos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
