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
& $runtime -B (Join-Path $projectRoot 'demo.py')
if ($LASTEXITCODE -ne 0) { throw 'La demo falló. Revisa Python y las dependencias de README.md.' }
& $runtime -B (Join-Path $projectRoot 'make_viewer.py')
if ($LASTEXITCODE -ne 0) { throw 'No se pudo generar el visor.' }
Start-Process -FilePath (Join-Path $projectRoot 'viewer.html') -WindowStyle Hidden
