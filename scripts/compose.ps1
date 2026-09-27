# Forward arguments verbatim. Select Docker with $env:CONTAINER_ENGINE = 'docker'.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$engine = if ($env:CONTAINER_ENGINE) { $env:CONTAINER_ENGINE } else { 'podman' }
if ($engine -notin @('podman', 'docker')) { throw 'CONTAINER_ENGINE must be podman or docker.' }
if (-not (Get-Command $engine -ErrorAction SilentlyContinue)) { throw "$engine is not installed or is not on PATH." }
Push-Location $projectRoot
try {
    & $engine compose -f compose.yaml -f compose.dev.yaml @args
    $result = $LASTEXITCODE
} finally { Pop-Location }
exit $result
