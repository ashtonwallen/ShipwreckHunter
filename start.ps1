$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (Test-Path -LiteralPath '.venv\Scripts\python.exe') {
        & '.venv\Scripts\python.exe' 'start.py'
    } else {
        & python 'start.py'
    }
    if ($LASTEXITCODE -ne 0) { throw "Shipwreck Hunting Tool exited with code $LASTEXITCODE" }
} finally { Pop-Location }
