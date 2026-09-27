$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    # Psycopg async connections require the selector loop on Windows.
    & py -m uv run --frozen python -c "import asyncio,sys,pytest; asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy()) if sys.platform == 'win32' else None; raise SystemExit(pytest.main(sys.argv[1:]))" @args
    $result = $LASTEXITCODE
} finally { Pop-Location }
exit $result
