# ==============================================================================
# Lanzador del Gesto de Escritorio Muse-Me ("Responder con Muse")
# Inspecciona la ventana activa, comprueba permisos y prepara la propuesta.
# ==============================================================================
Write-Host "Ejecutando Gesto Muse-Me..." -ForegroundColor Cyan
& python -m muse_env.gesture --trigger
