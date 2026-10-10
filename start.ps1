param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$candidates = @()
$bundled = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
if (Test-Path -LiteralPath $bundled) { $candidates += $bundled }
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCommand -and $pythonCommand.Source -notlike '*WindowsApps*') { $candidates += $pythonCommand.Source }
foreach ($candidate in $candidates) {
    & $candidate -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)' 2>$null
    if ($LASTEXITCODE -eq 0) {
        & $candidate -m spec2proof.server --port $Port
        exit $LASTEXITCODE
    }
}
Write-Error 'Python 3.10+ was not found. Install Python, then run python -m spec2proof.server from this folder.'
