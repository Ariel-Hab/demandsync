"""Red contra el crash de LightGBM con `pyarrow` cargado (M2.3, 2026-08-05).

Con `lightgbm==4.7.0` en Windows, `LGBMRegressor.fit` muere con
`OSError: exception: access violation reading 0x0000000000000000` si `pyarrow` se importó
antes. En este repo eso es *siempre*: la capa de datos (`motor.datos.archivos`) lee parquet,
y `pandas` arrastra `pyarrow` por su cuenta.

**Es un crash del binding C, no una excepción de Python**, así que no se puede atrapar con
un `try` en el mismo proceso de forma confiable — de ahí el subproceso. Y por la misma razón
no alcanza con testear `import motor`: hay que llegar a hacer un `fit`.

Aislado hasta la causa antes de fijar el pin:

| primero se importa | `LGBMRegressor().fit()` |
|---|---|
| `pyarrow` | **FALLA** |
| `pandas` (arrastra pyarrow) | **FALLA** |
| `scipy` / `sklearn` / `numpy` | OK |
| `lightgbm` antes que todo | OK |

No es la contigüidad del array de labels, ni el tamaño, ni las columnas `category`, ni el
paralelismo: los cuatro se probaron por separado y fallan igual. `KMP_DUPLICATE_LIB_OK=TRUE`
tampoco lo arregla. La mitigación por orden de import funciona pero es frágil —cualquier
módulo que importe pandas primero la rompe—, así que se resolvió con el tope de versión en
`pyproject.toml`.

Este test es lo que hace que subir ese tope no pase inadvertido.
"""

import subprocess
import sys
import textwrap

GUION = textwrap.dedent(
    """
    import motor.datos.archivos  # arrastra pandas -> pyarrow, que es el orden que rompe
    import numpy as np
    import lightgbm as lgb

    X = np.random.default_rng(0).normal(size=(270, 4))
    y = np.random.default_rng(1).normal(size=270)
    lgb.LGBMRegressor(n_estimators=3, verbose=-1).fit(X, y)
    print("OK", lgb.__version__)
    """
)


def test_lightgbm_entrena_con_pyarrow_ya_cargado():
    """El orden de import real del motor tiene que poder entrenar.

    Si esto falla con `returncode` negativo o `access violation`, la versión de LightGBM
    instalada reintrodujo el conflicto: revisá el tope de `pyproject.toml` antes de tocar
    `modelado/modelo_global.py`, que no tiene nada que ver.
    """
    proc = subprocess.run(
        [sys.executable, "-c", GUION], capture_output=True, text=True, timeout=300
    )

    assert proc.returncode == 0, (
        "LightGBM no pudo entrenar con pyarrow ya cargado. Es el conflicto de DLLs de la "
        f"4.7.0 (ver el docstring de este módulo y el pin de pyproject.toml).\n"
        f"returncode={proc.returncode}\nstdout={proc.stdout}\nstderr={proc.stderr[-800:]}"
    )
    assert proc.stdout.startswith("OK")
