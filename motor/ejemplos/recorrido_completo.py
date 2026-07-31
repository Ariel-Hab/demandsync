"""Corre los 7 casos en orden, uno atrás del otro.

Para explorar un caso a la vez (parar, cambiar un parámetro en `_comun.py` o en el
script, volver a correr solo ese) usá el script individual (`caso_0N_*.py`) en vez
de este — ver `README.md` de esta carpeta.
"""

import caso_01_datos
import caso_02_clasificacion
import caso_03_arnes
import caso_04_metricas
import caso_05_reporte
import caso_06_antileakage
import caso_07_seleccion

CASOS = [
    ("1 — Datos (T0.3)", caso_01_datos),
    ("2 — Clasificación de cuadrantes (M1.4)", caso_02_clasificacion),
    ("3 — Arnés de backtesting (M1.1)", caso_03_arnes),
    ("4 — Métricas por nivel (M1.2)", caso_04_metricas),
    ("5 — Reporte completo (M1.0(g)/M1.2)", caso_05_reporte),
    ("6 — Red anti-leakage (M1.3)", caso_06_antileakage),
    ("7 — Selección por serie (M1.7)", caso_07_seleccion),
]


def main() -> None:
    for titulo, modulo in CASOS:
        print(f"\n{'=' * 78}\nCASO {titulo}\n{'=' * 78}\n")
        modulo.main()


if __name__ == "__main__":
    main()
