$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$candidates = @(
    (Join-Path $projectRoot '.venv\Scripts\python.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe')
)
$runtime = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $runtime) {
    $runtime = (Get-Command python -ErrorAction Stop).Source
}
Write-Host "Ejecutando Flujo Automatizado Win32 (Respuesta Sintética de Fixture)..." -ForegroundColor Cyan
& $runtime -B (Join-Path $projectRoot 'run_assisted_native_flow.py') @args
if ($LASTEXITCODE -ne 0) { throw 'El flujo asistido nativo falló.' }
Write-Host "Flujo completado con éxito. Evidencias selladas en data\runs\" -ForegroundColor Green
