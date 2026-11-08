$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
Push-Location $workspace
try {
    & ./apps/backend/.venv/Scripts/python.exe -m pytest -c tests/backend/pytest.ini --confcutdir=tests/backend tests/backend/focused/native_setup @args
    $testExitCode = $LASTEXITCODE
} finally { Pop-Location }
exit $testExitCode
