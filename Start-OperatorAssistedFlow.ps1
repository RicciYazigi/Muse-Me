<#
.SYNOPSIS
    Lanza el flujo asistido con el Operador Antigravity real y host Win32 persistente.
.DESCRIPTION
    1. Inicia el host Win32 persistente con ventana EDIT real.
    2. Ejecuta export_mission.py --use-win32-real.
    3. Aguarda a que el operador Antigravity redacte genuinamente response.json.
    4. Ejecuta complete_mission.py para validar, insertar y verificar lectura nativa.
    5. Comprueba rechazo de repetición (replay) en SQLite.
    6. Cierra ordenadamente el host.
#>

$python = "C:\Users\USER\AppData\Local\Programs\Python\Python313\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

Write-Host "Iniciando flujo asistido con Operador Antigravity..." -ForegroundColor Cyan
& $python run_operator_assisted_flow.py
