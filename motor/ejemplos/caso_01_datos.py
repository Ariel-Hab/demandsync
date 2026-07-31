"""Caso 1 — La capa de datos (T0.3): los hechos mensuales tal cual los ve el motor.

Corré esto primero: es la tabla que alimenta todo lo demás (clasificador, arnés,
métricas). Si esto no corre, nada de lo que sigue puede correr.
"""

from _comun import repositorio


def main() -> None:
    repo = repositorio()
    hechos = repo.hecho_venta_mensual_producto()
    catalogo = repo.catalogo_producto()

    print(
        f"hecho_venta_mensual_producto: {len(hechos):,} filas, "
        f"{hechos['id_producto'].nunique():,} productos"
    )
    desde, hasta = hechos["anio_mes"].min().date(), hechos["anio_mes"].max().date()
    print(f"rango de fechas: {desde} .. {hasta}")
    print()
    print("dtypes (tienen que matchear motor/src/motor/datos/diccionario.py):")
    print(hechos.dtypes)

    print()
    print("Es una tabla DISPERSA: un producto-mes sin venta no tiene fila.")
    un_producto = hechos["id_producto"].iloc[0]
    serie = hechos[hechos["id_producto"] == un_producto].sort_values("anio_mes")
    meses_ventana = (serie["anio_mes"].max().year - serie["anio_mes"].min().year) * 12 + (
        serie["anio_mes"].max().month - serie["anio_mes"].min().month
    ) + 1
    print(
        f"  producto {un_producto}: {len(serie)} filas de venta en una ventana "
        f"de {meses_ventana} meses"
    )
    print(serie[["anio_mes", "unidades", "precio_prom"]].head(10).to_string(index=False))

    print()
    print(f"catalogo_producto: {len(catalogo):,} filas")
    print(f"  categorías: {sorted(catalogo['categoria'].unique())}")
    print(f"  laboratorios: {catalogo['laboratorio'].nunique()} distintos")


if __name__ == "__main__":
    main()
