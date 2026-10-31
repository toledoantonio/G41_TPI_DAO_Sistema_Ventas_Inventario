param(
    [switch]$Demo,
    [string]$BaseDatos,
    [switch]$Ayuda
)

$ErrorActionPreference = 'Stop'
$pythonLocal = Get-Command python.exe -All -ErrorAction SilentlyContinue |
    Where-Object { $_.Source -notlike '*\WindowsApps\*' } |
    Select-Object -First 1 -ExpandProperty Source
$pythonIncluido = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if ($pythonLocal) {
    $ejecutablePython = $pythonLocal
} elseif (Test-Path -LiteralPath $pythonIncluido) {
    $ejecutablePython = $pythonIncluido
} else {
    throw 'No se encontró Python. Instale Python 3.11 o superior con Tkinter y agréguelo a PATH.'
}

$argumentosAplicacion = @('-m', 'backend.main')
if ($Demo) { $argumentosAplicacion += '--demo' }
if ($BaseDatos) { $argumentosAplicacion += @('--db', $BaseDatos) }
if ($Ayuda) { $argumentosAplicacion += '--help' }
Push-Location -LiteralPath $PSScriptRoot
try {
    & $ejecutablePython @argumentosAplicacion
    if ($LASTEXITCODE -ne 0) { throw "La aplicación terminó con código $LASTEXITCODE." }
} finally {
    Pop-Location
}
