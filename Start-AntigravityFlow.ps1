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
Write-Host "Ejecutando Flujo Asistido con Operador Antigravity..." -ForegroundColor Cyan
& $runtime -B (Join-Path $projectRoot 'demo_antigravity_flow.py') @args
if ($LASTEXITCODE -ne 0) { throw 'La demo asistida falló.' }
Write-Host "Ejecución completada con éxito. Evidencias en data\runs\" -ForegroundColor Green
