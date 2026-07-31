"""Deflación read-time (ADR-002) — lleva ocho años de pesos nominales a pesos comparables.

En la ventana del extract la inflación acumulada es **×79,2**: sin esto, cualquier feature
o derivado monetario mide el calendario y no la demanda.

Lo único que el resto del motor necesita importar es `TransformadorDeflacion`. Los otros
módulos son su maquinaria, expuesta porque se testea sola:

- `precios` — qué precio implícito es utilizable y qué relativos mensuales salen de él.
- `indices` — cómo se construye el índice de un nivel a partir de esos relativos.
- `transformador` — la cascada, el ancla y la matriz de deflactores.

Nada de esto persiste (ADR-001: los hechos mensuales son inmutables y nominales). Las dos
tablas de salida respetan el esquema C2 del diccionario para que M4 pueda materializarlas.
"""

__all__ = ["TransformadorDeflacion"]


def __getattr__(nombre: str):
    """Re-export perezoso.

    Importar el transformador en el `__init__` obligaría a que exista para poder testear
    `precios` o `indices` por separado, que es justamente lo que este paquete evita.
    """
    if nombre == "TransformadorDeflacion":
        from motor.deflacion.transformador import TransformadorDeflacion

        return TransformadorDeflacion
    raise AttributeError(f"module {__name__!r} has no attribute {nombre!r}")
