# Backlog de Producto y Capacidades Verificables

Este backlog registra el estado real de las capacidades de Muse-Me, distinguiendo lo implementado en el corte `2f0b3dd` de las prioridades de desarrollo para la asistencia residente.

---

## Estado Actual de Capacidades

| Prioridad | Capacidad | Criterio de Aceptación | Estado en Corte 2f0b3dd |
| :--- | :--- | :--- | :--- |
| **P0** | Memoria por proyecto | Reabrir conserva misiones y referencias; cambios en disco invalidan exportaciones previas. | **Implementado** en `ProjectMemory` e integrado en `PanelEngine`. |
| **P0** | Recuperación local determinista | Aislamiento por proyecto y permisos; respeto de presupuesto; búsqueda FTS5. | **Implementado** (búsqueda léxica SQLite/FTS5; reporte de evidencia insuficiente). |
| **P0** | Ficha de proyecto y panel web | Visualización unificada de fuentes, permisos, vista previa y compuertas. | **Implementado** en `run_panel.py`. |
| **P0** | Inserción y readback nativo | Escritura en control Windows y verificación inmediata por lectura de retorno. | **Implementado** para controles Win32 `EDIT` de laboratorio. |
| **P0** | Inferencia Meta real | Respuesta real de modelo guardada con uso, latencia y fuentes autorizadas en ledger. | **Pendiente** (adaptador HTTP implementado; ensayo con cuenta real pendiente). |
| **P0** | Cierres de autoridad en demo | Destinos relativos acotados; fuentes borradas excluidas en MCP; aprobación persistente exacta. | **Pendiente** (Hito H1 del roadmap). |
| **P1** | Integración Fuse temporal | Contención de riesgo acumulado en operaciones mutadoras. | **Implementado experimentalmente** (sensor conectado a panel e inserciones; DEGRADE bloquea mutaciones). |
| **P1** | Detección de contradicciones | Exponer fuentes incompatibles sin elegir automáticamente por fecha. | **Implementado** en capacidad local `evidence_comparison`. |
| **P1** | Asistencia residente acotada | Observación de dos aplicaciones reales; memoria temporal de episodios; invocación rápida. | **Pendiente** (Hito H3 del roadmap). |
| **P1** | Evaluación humana medida | Comparación empírica frente a contexto reunido manualmente con tiempos observados. | **Pendiente** (Hito H5 del roadmap; protocolo diseñado). |
| **P2** | Adaptadores UIA generales | Compatibilidad con aplicaciones de escritorio arbitrarias mediante UI Automation. | **Pendiente** (requiere investigación por aplicación). |
| **P2** | Colaboración multiusuario | Aislamiento por usuario y revocación transitiva. | **Futuro** (no contemplado en alcance inmediato). |
