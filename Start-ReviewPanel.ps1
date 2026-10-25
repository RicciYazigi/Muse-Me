<#
.SYNOPSIS
    Inicia el panel local interactivo de revisión de Muse Environment.
.DESCRIPTION
    Abre el servidor local (http://127.0.0.1:8080) permitiendo:
    1. Activar / desactivar captura de Windows (opt-in).
    2. Seleccionar controles autorizados con políticas de captura y transferencia.
    3. Revisar fuentes y exclusiones explícitas de ContextBuilder.
    4. Autorizar el procesamiento (Compuerta 1).
    5. Revisar el borrador y citas del operador Antigravity.
    6. Aprobar la inserción exacta (Compuerta 2) y ejecutar en el control Win32 EDIT nativo con readback.
    7. Comprobar la integridad criptográfica de la cadena y la correspondencia con SQLite.
#>

# Asegurar que el directorio actual sea la carpeta del script
$scriptDir = $PSScriptRoot
if (-not $scriptDir) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}
if ($scriptDir) {
    Set-Location $scriptDir
}

$python = "C:\Users\USER\AppData\Local\Programs\Python\Python313\python.exe"
if (-not (Test-Path $python)) {
    if (Test-Path ".venv\Scripts\python.exe") {
        $python = ".venv\Scripts\python.exe"
    } else {
        $python = "python"
    }
}

Write-Host "Iniciando Panel Local de Revisión de Muse Environment..." -ForegroundColor Cyan
Write-Host "Directorio: $(Get-Location)" -ForegroundColor DarkGray
& $python run_panel.py
