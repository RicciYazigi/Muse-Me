# Backlog con criterios de aceptación

Cada capacidad debe resolver una tarea observada, con resultado verificable.

| Prioridad | Capacidad | Aceptación | Estado |
|---|---|---|---|
| P0 | Memoria por proyecto | Reabrir conserva misión y referencias; cambio importado invalida exportación | Implementado por CLI |
| P0 | Recuperación local | Aislar proyectos y permisos; respetar presupuesto; usar objetivo | Implementado, búsqueda léxica |
| P0 | Inferencia Meta | Respuesta real guardada con modelo, uso, duración y fuentes autorizadas | Adaptador conectado a CLI; ensayo real pendiente |
| P0 | Ficha del proyecto | Usuario encuentra objetivo, evidencia, estado y próximo paso sin abrir logs | Pendiente; panel heredado solo cubre revisión Win32 |
| P0 | Afirmaciones respaldadas | Cada decisión referencia una revisión y distingue observación/inferencia | Pendiente |
| P0 | Primera misión útil | Entregable correcto en tarea inédita; comprobación independiente | Pendiente |
| P0 | Medición humana | Comparación con modelo y recuperación simples, tiempos observados | Protocolo listo; medición pendiente |
| P1 | Contradicciones | Expone fuentes incompatibles sin elegir por fecha automáticamente | Pendiente |
| P1 | Tool calling | Solicitudes validadas; límites de acciones; estados persistentes; resultado comprobado | Pendiente |
| P1 | Documentos | Citas preservan página/sección y tablas necesarias | Evaluar MarkItDown/Docling |
| P1 | Actualización automática | Detectar modificación/borrado; evitar aceptar lecturas parciales | Pendiente |
| P1 | Olvido y retención | Borrado explícito de revisiones, derivados y backups según alcance | Pendiente |
| P1 | Revisión Meta de otra propuesta | Detectar error sembrado frente a evaluador independiente; medir coste | Experimento pendiente |
| P2 | Recuperación híbrida | Superar BM25 en consultas nuevas con sinónimos sin empeorar permisos | Pendiente de evidencia |
| P2 | Varias aplicaciones | Adaptadores probados por aplicación y versión; identidad de destino revalidada | Win32 de prueba heredado; UIA pendiente |
| P2 | Colaboración | Aislamiento por usuario y revocación transitiva en todos los derivados | Pendiente |
| P2 | Agentes especializados | Superar un único agente con mismo presupuesto | No justificado todavía |
| P2 | Fuse temporal | Aportar utilidad frente a políticas simples, con trazas reales | Investigación separada |

Dependencias críticas: inferencia → afirmaciones estructuradas → misión con herramientas → evaluación humana. La ingestión documental y el diseño de interfaz pueden avanzar independientemente. No hace falta completar toda la tabla para participar; sí describir con claridad qué parte se demuestra.

La ruta CLI requiere un operador local confiable. Para producto: convertir la aprobación en un registro persistente ligado a paquete, modelo y destino; revalidar fuentes al momento del envío; definir retención de respuestas y evitar errores de concurrencia. Antes de ejecutar código generado, incorporar aislamiento real del proceso y permisos específicos de herramientas.
