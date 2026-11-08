$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$previousDialogMode = $env:DIALOG_ENABLED
Push-Location $workspace
try {
    # These protocol checks deliberately isolate dialog and persistence dependencies.
    $env:DIALOG_ENABLED = 'false'
    & ./apps/backend/.venv/Scripts/python.exe -m pytest -c tests/backend/pytest.ini --confcutdir=tests/backend tests/backend/focused/voice_capture @args
    $testExitCode = $LASTEXITCODE
}
finally {
    $env:DIALOG_ENABLED = $previousDialogMode
    Pop-Location
}
exit $testExitCode
