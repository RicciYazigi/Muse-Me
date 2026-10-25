> [!NOTE]
> **Documento Histórico de Visión Estratégica (23 de octubre de 2026).**  
> Para el estado técnico vigente del corte verificado, consultar [docs/STATUS.md](STATUS.md) y [README.md](../README.md).

# MUSE Environment: evidencia, continuidad y trabajo verificable

23 de octubre de 2026. Dirección propuesta y primera ampliación implementada.
Este documento distingue hipótesis de producto, mecanismos comprobables y trabajo pendiente.

## Problema y potencial real

La oportunidad es reducir el coste de reconstruir un trabajo disperso y de actuar sobre decisiones caducadas. Un proyecto combina documentos, conversaciones, archivos, personas y resultados. Un chat puede redactar una buena respuesta y aun así perder la relación entre una decisión, su evidencia, la acción ejecutada y un cambio posterior.

MUSE puede mantener esa relación fuera de cualquier proveedor de modelos. Su unidad de trabajo es una misión: objetivo, evidencia versionada, alcance autorizado, entregable y criterio de aceptación. El usuario debería poder preguntar qué está pendiente, por qué, qué cambió y qué trabajo puede retomar.

La demanda comercial no está validada. Las conversaciones del usuario son evidencia de su problema personal; no representan una muestra de mercado. El producto compite con la disciplina de mantener buenos documentos, la búsqueda existente y asistentes con acceso a archivos. Una arquitectura compleja solo se justifica si ahorra esfuerzo o evita errores medibles.

## Escenarios y estructuras

| Escenario | Problema concreto | Estructura de evidencia | Resultado útil | Cómo falsar la hipótesis |
|---|---|---|---|---|
| Desarrollo | Corregir código con requisitos desactualizados | Repo + especificación + decisión de chat + pruebas | Parche y pruebas con requisitos trazables | Mismo modelo y archivos resuelven igual con menos esfuerzo |
| Investigación | Confundir resultados, hipótesis y versiones | Papers + notas + tablas + protocolo | Comparación citada y preguntas abiertas | Las citas no sustentan las afirmaciones o no reduce revisión |
| Operaciones de negocio | Comprometer una entrega con condiciones antiguas | Cotización + pedido + comunicación + inventario | Borrador de plan con conflictos visibles | Ignora una condición vigente o mezcla clientes |
| Trabajo creativo | Ejecutar cambios contra un brief anterior | Brief + referencias + feedback + versiones | Propuesta revisada y lista de cambios | Introduce requisitos inventados o pierde preferencias aprobadas |
| Traspaso entre personas | El siguiente responsable reconstruye todo | Misiones + entregables + decisiones + responsables | Paquete de continuidad revisable | El receptor necesita la misma explicación oral |
| Trabajo personal | Pendientes dispersos entre sesiones | Notas + compromisos + documentos | Próximas acciones sustentadas | Añade más mantenimiento del que elimina |

Explorar cuatro estructuras: carpeta única, fuentes de distintas herramientas, varios proyectos aislados y equipo con permisos por persona. El código nuevo prueba carpeta/proyecto local y aislamiento lógico entre proyectos. No implementa colaboración multiusuario ni permisos empresariales.

Escenarios adversos obligatorios: fuente contradictoria; actualización que invalida una conclusión; dato privado; proyecto con vocabulario idéntico a otro; ausencia de evidencia; interrupción; permiso revocado; documento que contiene instrucciones maliciosas; dos fuentes igualmente autorizadas que discrepan. En el último caso se conserva el conflicto: fecha reciente no equivale a autoridad.

## Arquitectura propuesta

1. Conectores explícitos: texto/código primero; documentos y aplicaciones con adaptadores específicos.
2. Registro local de fuentes: identidad, revisión, permiso y procedencia.
3. Recuperación: filtro por proyecto/permisos antes del paquete; búsqueda léxica, luego comparación con recuperación semántica.
4. Registro de afirmaciones: hecho observado, interpretación, decisión confirmada o resultado comprobado, con referencias a revisiones. Pendiente de implementar.
5. Misiones: objetivo, checkpoint y dependencias. Invalidación por cambio de evidencia.
6. Modelos Meta: extracción estructurada, propuesta de relaciones y razonamiento con herramientas.
7. Ejecución: herramientas delimitadas, revisión de cambios y comprobación independiente del resultado.
8. Experiencia: proyecto → evidencia → misión → resultado → retomar. Mostrar procedencia cuando sirve para decidir.

No se necesita representar toda esta estructura como un grafo visual permanente. Una ficha legible con vínculos puede ser más útil. El grafo aporta valor cuando ayuda a explicar dependencias o cambios.

## Implementado en esta ampliación

- Copia de trabajo del núcleo P0; conserva su panel y adaptadores anteriores.
- ProjectMemory: fuentes/revisiones y checkpoints persistidos en SQLite.
- SQLite FTS5 con ranking BM25, filtro por proyecto y alcance de transferencia.
- Ingestión de archivos explícitos UTF-8, formatos acotados y límite de tamaño.
- Detección de dependencia cambiada después de reingestión; bloqueo de exportación de una misión desactualizada.
- Reanudación tras cerrar y abrir la base.
- CLI para revisar el paquete y autorizar su hash antes de llamar al adaptador Meta existente.
- Corrección del selector anterior: la consulta incluye la acción del usuario, además del texto de la ventana.
- Cuatro escenarios sintéticos que ejercitan el mecanismo común.

La nueva memoria es una capa experimental por CLI; todavía no está integrada en el panel Win32. Las comprobaciones de escenarios son deterministas, sin modelo. No constituyen validación de comprensión semántica, impacto comercial o ahorro humano.

## Modelos y contrato de uso

Probar Spark 1.3 para extracción, clasificación y síntesis frecuente; Wonder para misiones complejas con herramientas. La elección final depende de resultados reales y presupuesto, no del nombre del modelo. Los permisos y la fuente canónica se mantienen en la aplicación. El modelo propone afirmaciones; un validador comprueba esquema, pertenencia de citas y condiciones de acción. La validez de una cita no demuestra que su contenido sustente una afirmación.

El CLI conecta con el proveedor de texto que ya existía y exige aprobación del paquete. Falta probarlo con cuenta real y extenderlo a herramientas/structured outputs. No se ha enviado contenido privado a Meta en esta implementación.

## Código reutilizable investigado y decisiones

| Alternativa | Aporte | Decisión y coste de integración |
|---|---|---|
| SQLite FTS5 | Búsqueda textual y BM25 local | Incorporado. Reutiliza SQLite; no comprende sinónimos o contradicciones |
| Microsoft MarkItDown | Conversión de documentos a Markdown, MIT | Primer candidato opcional para Office/PDF sencillo; exigir conversión local y conservar ubicación original |
| Docling | Layout, tablas y estructura documental; código MIT | Candidato para investigación con PDF complejo; evaluar tiempo, memoria y licencias de modelos adicionales |
| LangGraph | Ejecución durable e intervención humana | Evaluar cuando existan misiones con ramificaciones/reintentos; hoy duplicaría parte de persistencia y control |
| pywinauto | Win32 y UI Automation, BSD-3-Clause | Candidato para aplicaciones Windows concretas; comprobar compatibilidad por aplicación antes de prometer escritorio universal |
| LlamaIndex | Ingestión e índices modulares | Alternativa si la variedad de conectores justifica el framework; comparar con el camino directo actual |

No se ha copiado código de esos repositorios ni instalado estas dependencias opcionales. Antes de incorporar una, fijar versión, revisar licencia de esa versión y ejecutar pruebas con documentos representativos. Si extracción simple supera a una pila pesada, conservar la simple.

Fuentes primarias consultadas el 23 de octubre:
- https://www.sqlite.org/fts5.html
- https://github.com/microsoft/markitdown
- https://github.com/docling-project/docling
- https://github.com/langchain-ai/langgraph
- https://github.com/pywinauto/pywinauto
- https://github.com/run-llama/llama_index/blob/main/llama-index-core/LICENSE
- https://dev.meta.ai/docs/models
- https://dev.meta.ai/docs/tool-calling
- https://dev.meta.ai/docs/cookbook/structured-output

## Experimento de utilidad, previo a ampliar funciones

Preparar al menos 12 tareas inéditas, 3 por cada uno de los cuatro dominios iniciales. Es un piloto exploratorio; no basta para generalizar estadísticamente. Congelar respuesta esperada y criterios antes de observar al modelo. Separar los conjuntos usados para ajustar prompts y para evaluar.

Comparar: A, mismo modelo con recopilación manual; B, mismo modelo con recuperación léxica simple; C, MUSE con revisiones y checkpoints. Mantener presupuesto, configuración del modelo y herramientas equivalentes. Aleatorizar orden; evitar que el participante aprenda la solución antes de la siguiente condición. Medir tiempo humano solo con personas reales. Registrar latencia, tokens, aciertos, afirmaciones sin respaldo, fuentes privadas transferidas, cambios detectados y acciones duplicadas.

Incluir actualización de una fuente a mitad del trabajo. Comparar utilidad antes y después del cambio. Evaluar por separado cada dominio: una mejora en código no demuestra eficacia en operaciones.

Umbrales propuestos, aún no logrados: cero transferencia no autorizada en la batería; ninguna ejecución sobre evidencia invalidada; al menos 25% menos tiempo humano mediano sin empeorar calidad frente a la mejor referencia. Informar tamaño de muestra, dispersión, fallos y coste. Si no mejora, limitar el caso de uso o revisar la propuesta.

Entrevistar 3–5 usuarios por dominio, observar una tarea reciente real y medir dónde pierden tiempo. Priorizar por frecuencia, coste del error, acceso a fuentes, posibilidad de verificar el resultado y voluntad de adoptar. Estas entrevistas están pendientes.

## Hackathon y horizonte posterior

Antes del evento: candidatura clara, inventario de código previo y selección de una misión real. Revisar reglas de reutilización al publicarse.

Durante el evento: conectar inferencia real; integrar memoria en una ficha visible del proyecto; extraer decisiones con citas; ejecutar una herramienta acotada con verificación; demostrar reinicio y fuente cambiada; medir contra referencias y grabar un recorrido reproducible. El mínimo viable prueba el ciclo entero en un dominio, mientras la batería transversal descubre límites.

Después: documentos complejos, segundo dominio validado, conectores de aplicaciones, colaboración y permisos, recuperación híbrida si mejora resultados, ejecución durable si la complejidad lo justifica. CELL y los mecanismos de Fuse/Wings pueden aportar módulos concretos con evidencia de utilidad; integrar sus arquitecturas completas no es requisito del producto.

## Límites que deben permanecer visibles

No hay vigilancia automática de archivos: el cambio se detecta al volver a ingerir la fuente. Un archivo eliminado requiere gestión futura de tombstones. Las revisiones antiguas permanecen en la base; revocar transferencia no equivale a borrar datos históricos. Una carpeta por proyecto evita colisiones de rutas relativas. El límite de contexto se mide en caracteres, no tokens. BM25 es búsqueda, no razonamiento. Un checkpoint vigente no implica verdad. No hay aislamiento del sistema operativo ni ejecución automática de código generado en la capa nueva. No hay cuenta Meta verificada ni benchmark de utilidad humana.

## Posicionamiento para la candidatura

MUSE Environment busca ayudar a personas que trabajan con proyectos dispersos entre código, documentos y conversaciones. Conserva la evidencia y las decisiones de cada misión, utiliza modelos de Meta para proponer trabajo útil y permite retomar el proyecto identificando qué cambió. El prototipo previo aporta observación y ejecución controlada; el desarrollo propuesto se centra en memoria de proyecto, inferencia real, resultados verificables y evaluación comparativa. La visión abarca varios dominios, y la demostración inicial se concentra en una misión completa cuya calidad pueda comprobarse.
