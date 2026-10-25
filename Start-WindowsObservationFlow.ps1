<#
.SYNOPSIS
    Ejecuta el flujo de observación Windows de solo lectura con activación explícita (opt-in).
.DESCRIPTION
    1. Crea dos superficies de prueba con controles EDIT nativos reales.
    2. Activa el Win32ReadonlyObserver (opt-in) sobre las superficies autorizadas.
    3. Lee procedencia real e identidad de ventana/control (HWND, PID, clase EDIT, control_id).
    4. Demuestra selección de fuente pertinente y exclusión estricta de fuente irrelevante y restringida.
    5. Ejecuta el ciclo con el operador Antigravity e inserta con readback verificado.
    6. Emite informe de evidencia separando observaciones reales, inferencias y datos sintéticos.
#>

$python = "C:\Users\USER\AppData\Local\Programs\Python\Python313\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

Write-Host "Iniciando Flujo de Observación Windows (Solo Lectura, Opt-In)..." -ForegroundColor Cyan
& $python run_windows_observation_flow.py
