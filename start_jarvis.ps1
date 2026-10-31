$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$appPath = Join-Path $projectRoot "jarvis_v11.py"

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    Write-Error "Project Python was not found at $pythonPath. Create .venv and install requirements.txt first."
    exit 1
}

if (-not (Test-Path -LiteralPath $appPath -PathType Leaf)) {
    Write-Error "JARVIS entry point was not found at $appPath."
    exit 1
}

& $pythonPath -c "import PySide6" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Error "PySide6 is missing from the project environment. Run: .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
    exit 1
}

Push-Location $projectRoot
try {
    & $pythonPath $appPath @args
    $appExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

exit $appExitCode
