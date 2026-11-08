#Requires -Version 5.1
<#
.SYNOPSIS
Rebuild and redeploy the current checkout using Docker Compose.
.DESCRIPTION
Requires a configured .env, prepared models, and Compose v2.20+.
Preserves volumes. Ends active calls before migrating the voice database.
.EXAMPLE
.\scripts\redeploy.ps1 -NoCache -WaitTimeoutSeconds 600
#>
[CmdletBinding()]
param(
    [switch]$NoCache,
    [ValidateRange(1, 3600)]
    [int]$WaitTimeoutSeconds = 300
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent $PSScriptRoot

function Invoke-Compose {
    param([string[]]$ComposeArguments)
    & docker compose --project-directory $repositoryRoot --env-file (Join-Path $repositoryRoot '.env') --file (Join-Path $repositoryRoot 'compose.yaml') @ComposeArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose failed (exit $LASTEXITCODE): $($ComposeArguments -join ' ')"
    }
}

try {
    Get-Command docker -ErrorAction Stop | Out-Null
    if (-not (Test-Path -LiteralPath (Join-Path $repositoryRoot '.env') -PathType Leaf)) {
        throw 'Create .env from .env.example and set POSTGRES_PASSWORD first. See docs/voice-capture.md.'
    }
    & docker info --format '{{.OSType}}' | ForEach-Object {
        if ($_ -ne 'linux') { throw 'Docker must use Linux containers.' }
    }
    if ($LASTEXITCODE -ne 0) { throw 'Docker is unavailable. Start Docker Desktop or Docker Engine.' }
    Invoke-Compose -ComposeArguments @('config', '--quiet')

    Write-Host 'Building the current checkout before stopping application services...'
    $buildArguments = @('build')
    if ($NoCache) { $buildArguments += '--no-cache' }
    Invoke-Compose -ComposeArguments ($buildArguments + @('migrate', 'api', 'web'))
    Invoke-Compose -ComposeArguments @('up', '-d', '--wait', '--wait-timeout', "$WaitTimeoutSeconds", 'db')

    Write-Host 'Ending active calls and stopping web/API for database migrations...'
    Invoke-Compose -ComposeArguments @('stop', 'web', 'api')
    Write-Host 'Migrating the Compose voice database (db:5432); existing volumes are retained.'
    Invoke-Compose -ComposeArguments @('run', '--rm', '--no-deps', '-T', 'migrate')
    Invoke-Compose -ComposeArguments @('up', '-d', '--no-deps', '--force-recreate', '--wait', '--wait-timeout', "$WaitTimeoutSeconds", 'api', 'web')
    Invoke-Compose -ComposeArguments @('ps')
    Write-Host 'Deployment ready: http://localhost:8080'
}
catch {
    Write-Error -Message "Redeployment failed: $($_.Exception.Message). Check docker compose logs --tail 100 api db. If migration/startup failed, app services may remain stopped; fix the cause and rerun. No automatic database rollback is attempted." -ErrorAction Continue
    exit 1
}
