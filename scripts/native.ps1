#Requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateSet('setup', 'start', 'stop', 'restart', 'check')]
    [string]$Action = 'start',
    [ValidateRange(1, 3600)][int]$WaitTimeoutSeconds = 300
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repositoryRoot 'apps/backend/.venv/Scripts/python.exe'
Push-Location $repositoryRoot
try {
    if ($Action -eq 'setup') {
        Get-Command node, npm.cmd -ErrorAction Stop | Out-Null
        & node -e "if(Number(process.versions.node.split('.')[0]) !== 24) process.exit(1)"
        if ($LASTEXITCODE -ne 0) { throw 'Install Node.js 24 before setup.' }
        if (-not (Test-Path -LiteralPath $python)) {
            if (Get-Command uv -ErrorAction SilentlyContinue) {
                & uv venv apps/backend/.venv --python 3.12
            } else {
                & py -3.12 -m venv apps/backend/.venv
            }
            if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 (or uv) before setup.' }
        }
        & $python -c "import sys; sys.exit(0 if sys.version_info[:2] == (3,12) else 1)"
        if ($LASTEXITCODE -ne 0) { throw 'Backend virtual environment must use Python 3.12.' }
        & $python -m ensurepip --upgrade
        if ($LASTEXITCODE -ne 0) { throw 'pip bootstrap failed.' }
        & $python -m pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
        if ($LASTEXITCODE -ne 0) { throw 'CPU PyTorch installation failed.' }
        $previousVersion = $env:SETUPTOOLS_SCM_PRETEND_VERSION
        try {
            $env:SETUPTOOLS_SCM_PRETEND_VERSION = '1.3.0.dev0'
            & $python -m pip install -e . -r apps/backend/requirements-dialog.txt
            if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
        } finally { $env:SETUPTOOLS_SCM_PRETEND_VERSION = $previousVersion }
        & npm.cmd --prefix apps/frontend ci
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
        if (-not (Test-Path -LiteralPath '.env')) { Copy-Item .env.example .env }
        Write-Host 'Setup complete. Configure .env, provision the database and prepare models before start. No models were downloaded.'
    } else {
        if (-not (Test-Path -LiteralPath $python)) { throw 'Run scripts/native.ps1 setup first.' }
        & $python scripts/native.py $Action --timeout $WaitTimeoutSeconds
        if ($LASTEXITCODE -ne 0) { throw "Native $Action failed. See .local-run logs if startup began." }
    }
} finally { Pop-Location }
