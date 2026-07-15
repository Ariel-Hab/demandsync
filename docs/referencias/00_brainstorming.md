# Brainstorming — Módulo Predictor de Ventas

> Creado: 2026-06-03. Etapa: diseño conceptual / brainstorming.
> Consolidado desde sesión cross-repo + notas de diseño de módulo analytics.

---

## Visión

Módulo separado (propio contenedor o módulo extraíble) que genera predicciones de venta
mes a mes para los próximos 12 meses por cliente, con probabilidad.

El output es exportable para consumo por otros sistemas y visualizable en un dashboard propio.
No es un dashboard operacional del sistema DFV — es un sistema de predicción con su propia UI.

---

## Escala Real del Dataset

- ~1.500 clientes en el sistema (no 229 — ese era solo activos últimos 12 meses)
- Casi todos con historial de los últimos 2 años
- Facturas históricas desde septiembre 2018 (~96 meses disponibles)
- **Dataset de entrenamiento potencial:** ~1.500 × 96 = ~144.000 filas

Esta escala cambia significativamente la arquitectura viable:
- Modelos individuales por cliente son posibles (96 puntos de datos por cliente)
- Modelo global tiene suficiente volumen para ser robusto
- Clustering para pooling es opcional, no obligatorio por escasez de datos

---

## Output del Módulo

Por cliente: predicción mes a mes para t+1 a t+12, con probabilidad/confianza.

- **Mes 1**: mayor confianza → útil para decisiones de corto plazo
- **Mes 12**: menor confianza → útil para planificación anual

El consumidor del output elige el horizonte según su necesidad. El módulo expone todos.

### Usos del output

| Uso | Horizonte recomendado |
|-----|----------------------|
| Compras de stock inmediatas | t+1 |
| Planificación de compras | t+3 a t+6 |
| Priorización de llamadas de ventas | t+1 |
| Input para credit score | t+6 a t+12 |
| Planificación anual | t+12 |

---

## Arquitectura en 3 Capas (propuesta)

```
[1] Feature Pipeline  ← Módulo Analytics DFV
    segmentacion_service, rentabilidad_service, dm_ventas_mensual
    → produce features actualizados en tabla `clientes`
         ↓
[2] Training Pipeline  ← Predictor (offline, periódico)
    extrae features + historial snap 2018-presente
    entrena modelo ML
    guarda modelo + metadata
         ↓
[3] Inference Pipeline  ← Predictor (periódico)
    carga modelo
    genera predicciones t+1..t+12 para todos los clientes
    escribe en tabla `predicciones`
    sirve vía Export API + Dashboard
```

---

## Componentes que necesita de DFV

### Features del módulo Analytics (prerequisito antes de implementar)

| Feature | Estado en DFV | Plan que lo produce |
|---------|--------------|---------------------|
| `segmento_volumen` | ✅ disponible | segmentacion_service |
| `categoria_principal` | ✅ disponible | segmentacion_service |
| `frecuencia_compra` | ✅ disponible | segmentacion_service |
| `volumen_anual` | ✅ disponible | segmentacion_service |
| `revenue_mensual` | ⬜ pendiente | analytics/01_rentabilidad_fase1 |
| `margen_pct` | ⬜ pendiente | analytics/01_rentabilidad_fase1 |
| `tendencia_volumen_3m` | ⬜ pendiente | analytics/03_segmentacion_enriquecida |
| `valor_anual_estimado` | ⬜ pendiente | analytics/03_segmentacion_enriquecida |
| `recency_dias` | ⬜ pendiente | analytics/03_segmentacion_enriquecida |

### Datos históricos del snap MySQL

- `producto_factura` + `factura` desde septiembre 2018
- `producto_remito` + `remito` desde septiembre 2018

**Gap crítico:** `dm_ventas_mensual` solo tiene 25 meses. El training necesita los 96 meses
completos. Ver decisión abierta #4 sobre cómo resolverlo.

### Lo que NO necesita de DFV

- Lógica de negocio de cotizaciones, presupuestos, alertas comerciales
- Módulo de competencia
- Auth (JWT, api_keys) — tendrá su propio mecanismo de acceso si es contenedor separado

---

## Componentes propios del Predictor

| Componente | Descripción |
|-----------|-------------|
| Training pipeline | Proceso offline (semanal/mensual) que entrena el modelo |
| Model storage | Archivo del modelo entrenado (pickle / ONNX / MLflow) |
| Feature extraction | Queries al snap histórico 2018-presente para armar el training set |
| `predicciones` table | Tabla propia en PG: 12 filas por cliente por corrida |
| Export API | Endpoint para filtrar y exportar predicciones por horizonte/cliente/categoría |
| Dashboard | Vista propia — pantalla Flutter adicional o contenedor separado |

---

## Predicción individual vs predicción de cluster

El módulo debe producir dos niveles de predicción:

**Obligatorio — individual por cliente:**
Para cada cliente, P(compra en mes t) y/o E[volumen en mes t], para t+1..t+12.

**Opcional — por cluster/segmento:**
Agregado de las predicciones individuales agrupadas por `categoria_principal` o cluster.
Útil para: "¿cuánto va a comprar el segmento de biológicos en Q3?"
Para stock purchasing y planificación de proveedores.

---

## Clustering: rol en el predictor vs segmentación operacional

Son dos cosas distintas con propósitos distintos:

### Segmentación operacional (módulo Analytics, ya implementada, no cambia)
- Propósito: describir clientes para el equipo comercial
- Método: percentiles P33/P67, reglas determinísticas
- Output: etiquetas legibles (`alto`, `BIOLOGICO`, `frecuente`)
- Responde: "¿qué tipo de cliente es este?"

### Clustering para el predictor (opcional, a evaluar empíricamente)
- Propósito: agrupar clientes con patrones temporales similares para compartir fuerza estadística
- Con 1.500 × 96 meses, el modelo global puede hacer pooling implícitamente sin clustering explícito
- El clustering explícito agrega valor si los segmentos operacionales son demasiado gruesos
  o si se quieren predicciones a nivel cluster con agrupaciones basadas en comportamiento temporal

**K-means:**
- Si se usa como *feature* del modelo (cluster_id como input): **rechazado** — los IDs cambian
  de significado entre corridas → corrupción del historial de training (ADR-014)
- Si se usa solo para *agrupación interna* sin persistir como feature: viable a esta escala
- **Hierarchical Ward** sigue siendo preferido por ser determinístico (mismos datos → mismos clusters)

---

## Decisiones de Diseño Abiertas

| # | Pregunta | Opciones | Estado |
|---|---------|----------|--------|
| 1 | Variable objetivo | P(compra en mes t) / E[revenue] / ambas | ⬜ Abierto |
| 2 | Modelo global o por segmento | Un modelo / uno por `categoria_principal` | ⬜ Abierto |
| 3 | Tech stack ML | LightGBM con lags / Prophet / LSTM | ⬜ Abierto |
| 4 | Historial de training | Backfill dm_ventas_mensual a 2018 / extract propio | ⬜ Abierto |
| 5 | Separación física | Contenedor propio / módulo en el backend actual | ⬜ Abierto |
| 6 | Dashboard | Pantalla Flutter adicional / frontend separado | ⬜ Abierto |
| 7 | Frecuencia de reentrenamiento | Semanal / mensual | ⬜ Abierto |
| 8 | Clustering explícito | Sí (Ward) / No (modelo global) | ⬜ Abierto — evaluar post-features |

---

## Notas técnicas para sesión de diseño

**Lag features:** el training set necesita columnas `ventas_t-1`, `ventas_t-3`, `ventas_t-6`,
`ventas_t-12`, `mismo_mes_anio_anterior`. Estas se construyen desde el historial snap.

**Predicción probabilística:** LightGBM puede producir distribuciones (quantile regression)
en lugar de un punto único — da intervalos de confianza sin cambiar el framework.

**Multi-horizonte:** opciones para producir t+1..t+12:
- Direct: un modelo por horizonte (12 modelos, independientes, no acumula error)
- Recursive: un modelo, usa su propia predicción como lag para el siguiente mes (acumula error)
- Multi-output: un modelo con 12 outputs (más complejo, pero más eficiente)

**Clientes nuevos (< 6 meses de historial):** sin lags usables. Usar el promedio del segmento
más cercano como prior — exactamente lo que la segmentación operacional ya produce.

---

## Estado

- [x] Visión y objetivo definidos (2026-06-03)
- [x] Escala real documentada: 1.500 clientes × 96 meses
- [x] Distinción clustering operacional vs clustering ML documentada
- [x] Gap crítico identificado: dm_ventas_mensual tiene solo 25 meses
- [x] Arquitectura en 3 capas propuesta
- [x] Componentes DFV vs componentes propios mapeados
- [ ] Resolver 8 decisiones de diseño abiertas — sesión dedicada
- [ ] Diseñar feature extraction pipeline para training
- [ ] Elegir tech stack ML y arquitectura del modelo
- [ ] Decidir separación física (contenedor vs módulo)
- [ ] Implementar
