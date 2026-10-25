# Roadmap Muse-Me: Asistencia Contextual Residente

Este documento define las prioridades de desarrollo para la experiencia de asistencia residente y la preparación para el hackathon.

---

## Prioridades y Criterios de Salida

| Hito | Título | Alcance | Criterio de Salida |
| :--- | :--- | :--- | :--- |
| **H0** | Referencia y Reglas | Código previo identificado por commit `2f0b3dd`; lectura de reglas oficiales cuando se publiquen; delimitación nítida entre trabajo previo y trabajo del evento. | Base congelada inalterada; reglas oficiales leídas; no asumir elegibilidad sin verificación. |
| **H1** | Cierres de Autoridad en Demo | Destinos resueltos estrictamente dentro de raíz permitida; fuente borrada en disco excluida de inmediato en MCP; aprobación persistente exacta con consumo atómico; etiqueta visual de Meta en panel honesta. | Pruebas de regresión automatizadas que fallen antes de la corrección y pasen después, sin alterar el uso permitido. |
| **H2** | Inferencia Meta Real | Contrato de API comprobado con cuenta real; entrada autorizada y respuesta original conservadas con hashes; registro visible de errores; ningún fixture sustituyendo una llamada fallida. | Invocación exitosa demostrable contra endpoint Meta Llama; solicitud y respuesta persistidas en ledger. |
| **H3** | Asistencia Residente Acotada | Dos aplicaciones autorizadas concretas; actividad agrupada en episodios temporales; contexto con caducidad; invocación rápida y opciones pertinentes generadas por modelo real. | Demostración de ciclo completo en vivo: actividad → episodio → interpretación → invocación → propuesta. Pausa y revocación verificables. |
| **H4** | Acción Útil Completa | Elección de opción por el usuario, revisión previa, ejecución en destino autorizado y comprobación de resultado; gestión de fuente cambiada, rechazo y recuperación. | Inserción/acción ejecutada y confirmada por readback nativo en aplicación autorizada. |
| **H5** | Evaluación y Entrega | Tareas nuevas e inéditas; comparación con el mismo modelo y presupuesto sobre contexto reunido manualmente; medición de esfuerzo, tiempo, calidad y coste observados. | Reporte comparativo objetivo sin métricas simuladas (`null` en no observado); paquete reproducible del commit final. |

---

## Líneas Rojas de Arquitectura
1. **El modelo propone; la aplicación valida y ejecuta.** Ningún contenido de fuente puede ampliar permisos o invocar herramientas.
2. **Doble compuerta explícita:** `approve_transfer` antes de que los datos salgan hacia el modelo; `approve_insertion` antes de modificar el destino.
3. **Transparencia epistémica:** Distinción estricta entre observado, inferido y simulado.
4. **Fuse es contención, no permiso:** Puede degradar o detener una acción riesgosa; nunca autorizar una acción no permitida por política.
5. **Aislamiento de memoria:** Multiusuario, agentes complejos y auto-mejora son expansiones futuras; no se introducen antes de consolidar el ciclo residente acotado.
