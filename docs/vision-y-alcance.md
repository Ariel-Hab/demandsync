# Visión y Alcance

> Condensado del *Acta de Proyecto — UTN 2026*. El acta es el documento formal; este resumen es la referencia operativa del equipo. Última actualización: 2026-07-15.

## Problema

La distribución veterinaria combina compras reactivas, alta estacionalidad (climática y de campañas sanitarias) y fármacos con vencimiento estricto. El resultado: pérdidas por medicamentos vencidos, quiebres de stock y capital inmovilizado.

## Objetivo

Transformar el modelo reactivo en proactivo: una aplicación web que predice la demanda por producto y segmento a 1, 6 y 12 meses, y traduce esas predicciones en decisiones operativas (compras, rotación de lotes, venta cruzada), con explicabilidad vía asistente RAG.

## Los 4 módulos del producto

1. **Ingesta y Preprocesamiento** — integra periódicamente ventas históricas, catálogo (vademécum, lotes, vencimientos) y padrón de clientes desde el ERP del cliente; más fuentes externas (clima, macroeconomía).
2. **Inteligencia y Modelado (core predictivo)** — clustering de clientes (RFM + K-Means), modelos de series temporales / ML multivariable por producto y segmento, detección de patrones para venta cruzada.
3. **Reglas de Negocio y Abastecimiento** — cruza demanda predicha con stock actual, lead time y stock de seguridad; genera borradores de orden de compra; prioriza rotación de lotes próximos a vencer.
4. **Interfaz y Explicabilidad** — dashboard DSS + asistente en lenguaje natural (RAG sobre pgvector) que justifica cada sugerencia.

## Límites explícitos (qué NO hace)

- No reemplaza al ERP: no factura, no cobra, no registra ventas.
- No ejecuta compras: solo genera **borradores** que un humano aprueba en el ERP.
- No organiza logística de entregas ni almacenamiento físico.
- Alcance sectorial: distribución veterinaria.

## Restricciones estructurales (del acta)

- **Ingesta por archivos JSON** (servicio mock que simula servicios externos): el cliente debe exportar la data respetando el esquema acordado. El esquema se congela antes del Release 1.
- **Procesamiento batch nocturno**: los modelos no se recalculan en tiempo real; el dashboard muestra el último batch.
- **Solo lectura y sugerencia**: ninguna acción impacta el ERP.
- Consultas de la aplicación en **< 2 segundos** (validado contra la vista mensual agregada, no contra el grano crudo — ver corrección T2 en `referencias/03_correccion_casos_prueba_demandsync.md`).

## Releases

| Release | Contenido | Hito de validación |
|---|---|---|
| **R1 — Fundamentos e Ingesta** | Setup FastAPI + SQLModel + Alembic, PostgreSQL + pgvector, pipelines ETL del histórico, hechos mensuales | Base poblada, endpoints < 2s, batch nocturno sin interrumpir la API |
| **R2 — Core Predictivo** | Entrenamiento y evaluación de modelos (horizontes 1/6/12 meses), clustering RFM+K-Means, endpoints de predicción | Métricas de error documentadas; segmentos coherentes (contrastados con la segmentación operacional de DFV como oráculo) |
| **R3 — Reglas de Negocio** | Motor de rentabilidad, cálculo de necesidad de stock (lead time + stock de seguridad), prevención de caducidad, borradores de OC | Sugerencia de OC coherente que prioriza flujo de caja y alerta vencimientos |
| **R4 — Presentación y RAG** | Dashboard DSS, motor RAG (pgvector), chat de explicabilidad, paneles de métricas | Usuario final consulta y obtiene justificación técnica de una recomendación |

## Riesgos de alto nivel (del acta, ampliados por las correcciones DFV)

1. Inadecuación tecnológica (rendimiento < 2s, base vectorial) → PoCs en R1.
2. Dificultades de integración entre módulos → arquitectura desacoplada, contratos REST desde fase 1, mocking.
3. Calidad de datos históricos (ruido, outliers, faltantes) → prioridad crítica al preprocesamiento.
4. Ausencia de un integrante → documentación rigurosa + holgura en ruta crítica.
5. Precisión insuficiente en horizontes largos (6/12m) → evaluación progresiva; si es insalvable, el peso operativo va al horizonte de 1 mes.
6. **R6 (nuevo)** — Deflación ausente o mal hecha (IPC macro en vez de índice implícito) → distorsiona RFM y predicciones de valor. Contingencia: MVP predice **unidades**, no montos.
7. **R7 (nuevo)** — Doble conteo factura/remito → serie inflada. Contingencia: ingerir solo facturas en el MVP.
8. **R8 (nuevo)** — Sin histórico de stock → rotación/redistribución solo sobre stock actual.
