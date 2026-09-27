# A complete local stack selection, consistent across up/down/logs/config.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
New-Item -ItemType Directory -Force -Path (Join-Path $projectRoot 'var/logs') | Out-Null
& (Join-Path $PSScriptRoot 'compose.ps1') -f compose.observability.yaml @args
exit $LASTEXITCODE
