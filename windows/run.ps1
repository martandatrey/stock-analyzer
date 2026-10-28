<#
.SYNOPSIS
    Standalone Stock Analyzer run on Windows (the Windows wrapper for run.py). Takes the same arguments.

.DESCRIPTION
    Uses the Claude API directly, so it needs ANTHROPIC_API_KEY in .env (except --dry-run).
    Stocks are analysed one at a time and reports go to reports\<date>\.

.EXAMPLE
    .\windows\run.ps1                       # every stock with Analyze? = Y
.EXAMPLE
    .\windows\run.ps1 --ticker RELIANCE     # one stock
.EXAMPLE
    .\windows\run.ps1 --market us --depth Quick
.EXAMPLE
    .\windows\run.ps1 --dry-run             # fill every prompt, no API calls
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    throw "Not set up yet. Run:  powershell -ExecutionPolicy Bypass -File windows\setup.ps1"
}
$env:PYTHONUTF8 = "1"
Push-Location $Root
try {
    & $Py (Join-Path $Root "run.py") @args
    $code = $LASTEXITCODE
}
finally {
    Pop-Location
}
exit $code
