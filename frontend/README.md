# frontend/ — Dashboard DSS y Asistente RAG

**Responsable:** Frontend Developer. **Estado:** placeholder — el código entra en Release 4; la decisión de stack no bloquea R1–R3.

Alcance (Release 4):
- Dashboard principal (CU-02): alertas de quiebre, top predicciones, lotes críticos, KPI de inventario inmovilizado.
- Pantallas: predicción de demanda (CU-03), segmentación (CU-04), recomendaciones (CU-05), alertas de vencimiento (CU-06), borradores de OC (CU-07), administración (CU-08/CU-10).
- Chat del asistente de explicabilidad (CU-09) contra el motor RAG del backend.

Requisitos no funcionales clave: paneles < 2s (leen materializado del último batch), etiquetas de segmento legibles para usuarios no técnicos, indicadores de confianza junto a cada predicción.
