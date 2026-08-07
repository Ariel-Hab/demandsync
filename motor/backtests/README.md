# `motor/backtests/` — Tablas de error congeladas

Acá viven las tablas de referencia de cada corrida de backtest, generadas con
`motor.backtesting.reporte.a_markdown()`.

> **El piso a batir es [`baselines-real-prospectivo-2026-08-05.md`]** (M1.9, ADR-016).
> `baselines-real-2026-08-03.md` y `baselines-real-2026-07-31.md` quedan como registro
> histórico: se armaron con selección retrospectiva y por lo tanto están **inflados**.
> Ninguna de las dos se borra ni se corrige — se comparan con la vigente en §5.6.1 y
> §5.6.2 del roadmap, y varios hallazgos siguen apoyados en ellas.

## Regla de datos, sin excepciones

**Solo métricas agregadas** (ADR-006 y regla de oro de CLAUDE.md §4): conteos, ratios y
porcentajes. Nunca renglones, nombres de cliente, precios ni identificadores que
permitan reconstruirlos. Por eso una tabla de una corrida sobre datos **reales** del
cliente sí es publicable al repo: lo que entra es el error por horizonte y por nivel,
no los datos.

Antes de commitear una tabla generada en la máquina autorizada, leela.

## Convención de nombres

```
baselines-sintetico-<AAAA-MM-DD>.md          # M1.7 — piso sobre el dataset sintético
baselines-real-<AAAA-MM-DD>.md               # M1.8 — snap real, selección retrospectiva
baselines-real-prospectivo-<AAAA-MM-DD>.md   # M1.9 — snap real, prospectiva. EL piso a batir
ablaciones-global-<fuente>-<AAAA-MM-DD>.md   # M2.3 — qué configuración lleva el global a M2.5
intervalos-global-<fuente>-<AAAA-MM-DD>.md   # M2.4 — calibración del P10–P90
global-vs-baselines-<fuente>-<AAAA-MM-DD>.md # M2.5 — champion/challenger contra el piso
```

## Qué tiene que traer cada tabla para ser congelable

1. **La sección `## Corrida`**, con el `id` de corrida. Es hash de configuración +
   huella de los datos: sin eso no se sabe qué produjo el número y la tabla no sirve
   como referencia. Si el reporte se generó desde un DataFrame que perdió
   `.attrs["corrida"]` (pandas lo descarta en varias operaciones), `a_markdown()` lo
   avisa arriba con una advertencia — **si esa advertencia está, no la commitees**:
   regenerá el reporte reponiendo los metadatos.
2. **Desagregado por horizonte (1/3/6/12) y por nivel** (producto / categoría / total).
   Regla del gate de M1.2: ningún número global suelto sin desagregar.
3. **Desagregado por cuadrante de intermitencia.** Lo produce `motor.clasificacion`:
   `etiquetar(reporte, clasificar_series(hechos))` antes de armar las tablas. Es el corte
   que más aporta —en el sintético el WAPE va de 0,51 en las series suaves a 1,63 en las
   lumpy— y si falta, `a_markdown()` lo deja escrito para que su ausencia no se lea como
   cumplida.
4. **La columna `cobertura`**, y que sea 1,0 o esté explicado por qué no. Una tabla con
   cobertura baja tiene mejor WAPE por omitir series difíciles, no por predecir mejor.
5. **El criterio de selección declarado en el encabezado** (condición agregada por M1.9 /
   ADR-016). Retrospectiva y prospectiva son dos convenciones defendibles que producen
   números **distintos sobre los mismos datos** — a grano producto, WAPE 0,287 contra
   0,331 en h=1 con las mismas predicciones. Una tabla que no dice con cuál se armó no se
   puede comparar contra ninguna otra. Lo escribe `congelar_baselines_sintetico.py` según
   `--seleccion`, y el aviso **cambia con el flag**: dejar la advertencia de hindsight en
   una tabla prospectiva sería afirmar algo falso sobre el propio resultado.

## Cómo se usa una tabla congelada

Es el piso de la disciplina **baselines-first** (CLAUDE.md §6): ningún modelo se
promociona si no le gana en backtest al piso vigente. Una vez commiteada **no se pisa**:
una corrida nueva es un archivo nuevo con su propia fecha e `id`, así la comparación entre
corridas queda auditable.

**Y no se compara contra una tabla armada con otro criterio de selección.** Es el error que
M1.9 vino a evitar: medir el modelo global prospectivamente contra un piso retrospectivo
inclina la cancha en contra del global, y al revés la inclina a favor.

### Una tabla sobre el sintético caduca; una sobre datos reales no

El dataset sintético se regenera por semilla, así que **si cambia el generador, la tabla
describe un dataset que ya no se puede reproducir** — aunque la semilla y la muestra sean las
mismas. Pasó con `baselines-sintetico-2026-07-30.md`: T0.4 reescribió el generador al día
siguiente de congelarla (`roadmap-motor.md` §6.4). El extract real, en cambio, es una foto
fija: sus tablas siguen siendo comparables mientras no se re-extraiga.

El `id` de corrida lo detecta —cambia la huella de datos, cambia el `id`— **pero solo si
alguien lo mira**. Por eso una tabla sintética que caducó lleva el aviso **en su encabezado**
y no solo en el roadmap: quien la abra tiene que enterarse ahí, no tres documentos después.
