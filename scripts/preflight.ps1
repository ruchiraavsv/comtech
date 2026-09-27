$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$engine = if ($env:CONTAINER_ENGINE) { $env:CONTAINER_ENGINE } else { 'podman' }
if ($engine -notin @('podman', 'docker')) { throw 'CONTAINER_ENGINE must be podman or docker.' }
if (-not (Get-Command $engine -ErrorAction SilentlyContinue)) { throw "$engine is unavailable." }
& $engine info *> $null
if ($LASTEXITCODE) { throw 'Container engine is unreachable. Inspect/start your existing Podman machine.' }
& $engine compose version
if ($LASTEXITCODE) { throw 'Compose provider unavailable. Configure PODMAN_COMPOSE_PROVIDER.' }
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot '.env'))) { throw 'Copy .env.example to .env first.' }
Push-Location $projectRoot
try {
    & $engine compose -f compose.yaml -f compose.dev.yaml config --quiet
    if ($LASTEXITCODE) { throw 'Compose configuration is invalid.' }
} finally { Pop-Location }
foreach ($port in @(5433, 8000, 8501, 5081)) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    if ($listener) { Write-Warning "Port $port is in use (possibly by this project's running stack)." }
}
Write-Host 'Preflight passed. No secret values were printed.'
