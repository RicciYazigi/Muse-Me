# MUSE: ampliación para explorar utilidad real

La visión, escenarios, alternativas de código y prioridades están en [Panorama y estrategia](docs/PANORAMA_Y_ESTRATEGIA.md).

El núcleo heredado sigue descrito en README.md. Sus reportes históricos no son pruebas nuevas. La ampliación usa una memoria independiente por CLI, pendiente de integración con el panel.

## Demostración local sin API

Desde esta carpeta, con Python 3.10+:

```powershell
python demo_projects.py
```

Genera validation/scenarios.json con cuatro escenarios sintéticos: software, investigación, operaciones y trabajo creativo. Comprueba búsqueda, persistencia, detección de cambio tras reingestión y bloqueo de exportación desactualizada. No mide respuestas de IA.

## Probar con archivos propios

Indicar únicamente archivos que se quieran incluir. La ruta raíz es una carpeta autorizada; usar una carpeta por proyecto.

```powershell
python project_cli.py ingest mi-proyecto C:\ruta\autorizada brief.md notas.txt --scope may_transfer
python project_cli.py search mi-proyecto "preparar propuesta" --external --checkpoint
python project_cli.py resume ID_MISION
python project_cli.py preview ID_MISION
```

El último comando muestra exactamente el paquete y su SHA-256. Solo si se desea enviarlo a Meta:

```powershell
python project_cli.py generate ID_MISION --approve-payload-sha256 HASH_MOSTRADO
```

Requiere MODEL_API_KEY en el entorno. Usa muse-spark-1.3; admite --model. Devuelve un borrador por consola, sin ejecutar ni insertar acciones. Esta ruta no se ha validado contra API real. Para conservarlo, redirigir la salida a un archivo elegido. Las aprobaciones de CLI son responsabilidad del operador; no constituyen una interfaz multiusuario.

Repetir ingest cuando cambie un documento y luego resume para ver qué misiones necesitan revisión. No hay observación automática de archivos.

## Pruebas

Con pytest y numpy disponibles:

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m pytest tests -q
```

ProjectMemory añade pruebas de persistencia, revocación, aislamiento de proyectos, presupuesto y límites de ruta. La evidencia de esta sesión queda en validation/.
