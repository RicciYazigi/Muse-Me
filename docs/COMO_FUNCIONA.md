# Qué sería Muse Environment

Una aplicación de escritorio con un motor local y un visor. El visor es la interfaz;
el motor selecciona contexto y conserva memoria; Muse es un proveedor de inferencia.

## Recorrido del usuario que se quiere construir

1. Habilitas aplicaciones o carpetas concretas y puedes pausar la observación.
2. Trabajas normalmente; el motor registra eventos permitidos y propone episodios.
3. Invocas «Responder con Muse» mediante un atajo o botón.
4. Revisas el contexto elegido. Se comprueba autorización para procesarlo en Meta.
5. Muse devuelve un borrador con fuentes identificables.
6. Revisas y apruebas ese texto para un destino concreto.
7. La aplicación verifica el destino y la inserción; la memoria conserva el resultado.

La observación local y las llamadas a Muse tienen ritmos distintos. Capturar no
autoriza automáticamente conservar indefinidamente, transferir ni ejecutar acciones.
Los permisos siguen aplicándose cuando el sensor experimental Fuse está apagado.

## Qué hace esta versión

La demo recorre observaciones simuladas, crea episodios por reglas, selecciona
contexto, usa un proveedor local extractivo y simula aprobación e inserción. Guarda
eventos en SQLite y comprueba que siguen presentes tras cerrar y reabrir la base.
También demuestra que un STOP opcional bloquea una inserción por la misma interfaz.

El visor HTML es estático y de sólo lectura: presenta esa ejecución. No observa
ventanas, no incorpora un diálogo de consentimiento real y no envía contenido.

## Motor preparado, integración real pendiente

El cliente Meta interpreta respuestas HTTP y exige autorización previa ligada al
paquete y al proveedor. Se verifica con HTTP simulado; no se ha probado con una cuenta
real. Aún no maneja imágenes, herramientas ni conversación encadenada.

El adaptador de Windows debe comprobar en cada aplicación qué texto y controles
expone UIA, limitar captura y retención y validar identidad y lectura posterior a
la inserción. La interfaz `FakeSurface` demuestra el contrato con una lista en memoria.
El texto observado se trata como evidencia y no como instrucciones para ampliar permisos.

## Fronteras de confianza

`approve_transfer` y `approve_insertion` representan decisiones de la interfaz u
operador autorizado; no son herramientas que se deban entregar al modelo. Una
aplicación real debe conectarlas con su política y UI autenticada. En la demo las
invoca un script y esto se etiqueta como simulado. Un hash no acredita consentimiento humano.

La aprobación de inserción queda ligada al borrador exacto, ID de destino y un
intento único. El adaptador real debe revalidar el destino dentro de su propia
operación para impedir que un cambio de foco inserte en otro control.

La cadena de registro incluye fuentes, payload, borrador y aprobación. Detecta
alteraciones de ese contenido; no es almacenamiento inmutable ni certificación de
verdad o de ausencia de borrado por un administrador. Las bases del P0 anterior
no se migran automáticamente: se conservan como evidencia histórica separada.
