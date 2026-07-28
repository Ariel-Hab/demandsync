# `motor/backtests/` — Tablas de error congeladas

Acá viven las tablas de referencia de cada corrida de backtest, generadas con
`motor.backtesting.reporte.a_markdown()`. **Todavía no hay ninguna:** la primera es el
piso de baselines de M1.7 (sintético) y M1.8 (real).

## Regla de datos, sin excepciones

**Solo métricas agregadas** (ADR-006 y regla de oro de CLAUDE.md §4): conteos, ratios y
porcentajes. Nunca renglones, nombres de cliente, precios ni identificadores que
permitan reconstruirlos. Por eso una tabla de una corrida sobre datos **reales** del
cliente sí es publicable al repo: lo que entra es el error por horizonte y por nivel,
no los datos.

Antes de commitear una tabla generada en la máquina autorizada, leela.

## Convención de nombres

```
baselines-sintetico-<AAAA-MM-DD>.md      # M1.7 — piso sobre el dataset sintético
baselines-real-<AAAA-MM-DD>.md           # M1.8 — piso sobre el snap real. EL piso a batir
global-vs-baselines-<AAAA-MM-DD>.md      # M2.5 — champion/challenger contra el piso
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

## Cómo se usa una tabla congelada

Es el piso de la disciplina **baselines-first** (CLAUDE.md §6): ningún modelo se
promociona si no le gana en backtest a la tabla de M1.8. Una vez commiteada **no se
pisa**: una corrida nueva es un archivo nuevo con su propia fecha e `id`, así la
comparación entre corridas queda auditable.
