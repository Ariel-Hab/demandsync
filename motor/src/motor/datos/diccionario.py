"""Diccionario de columnas del motor — espejo de docs/referencias/02_correccion_der_demandsync.md.

C1 (hechos mensuales), C2 (entidades de deflación — salida del motor, se pueblan en M2)
y C3 (`cliente_feature`), más `catalogo_producto` (mínimo necesario para el fallback
categoría→laboratorio de la deflación). Cualquier rename acá es cambio de contrato:
se acuerda con el Backend Dev (ADR-009), no se decide unilateralmente.
"""

ESQUEMAS = {
    # C1 — HECHO_VENTA_MENSUAL_PRODUCTO
    "hecho_venta_mensual_producto": {
        "id_producto": "int64",
        "anio_mes": "datetime64[ns]",
        "unidades": "float64",
        "revenue": "float64",
        "precio_prom": "float64",
    },
    # C1 — HECHO_VENTA_MENSUAL_CLIENTE_PRODUCTO
    "hecho_venta_mensual_cliente_producto": {
        "id_cliente": "int64",
        "id_producto": "int64",
        "anio_mes": "datetime64[ns]",
        "unidades": "float64",
        "revenue": "float64",
    },
    # Catálogo mínimo — no es C1/C2/C3, pero el fallback de deflación (C2) lo necesita
    "catalogo_producto": {
        "id_producto": "int64",
        "categoria": "object",
        "laboratorio": "object",
        "activo": "bool",
    },
    # C3 — CLIENTE_FEATURE
    "cliente_feature": {
        "id_cliente": "int64",
        "categoria_principal": "object",
        "frecuencia_compra": "object",
        "volumen_anual": "float64",
        "valor_anual_estimado": "float64",
        "tendencia_volumen_3m": "float64",
        "recency_dias": "int64",
        "fecha_calculo": "datetime64[ns]",
    },
    # C2 — ANCLA_PRECIO_PRODUCTO (salida del motor, M2)
    "ancla_precio_producto": {
        "id_producto": "int64",
        "precio_prom_hoy": "float64",
        "fecha_calculo": "datetime64[ns]",
    },
    # C2 — INDICE_PRECIO_NIVEL (salida del motor, M2)
    "indice_precio_nivel": {
        "nivel": "object",
        "id_nivel": "object",
        "anio_mes": "datetime64[ns]",
        "indice": "float64",
    },
}

TABLAS_LECTURA = (
    "hecho_venta_mensual_producto",
    "hecho_venta_mensual_cliente_producto",
    "catalogo_producto",
    "cliente_feature",
)

TABLAS_ESCRITURA = (
    "ancla_precio_producto",
    "indice_precio_nivel",
)
