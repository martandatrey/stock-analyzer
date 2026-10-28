<#
.SYNOPSIS
    One unattended daily run, started by the Windows Task Scheduler jobs that schedule.ps1 creates.
    Writes a log to reports\logs\<date>-<market>.log.

.EXAMPLE
    .\windows\scheduled-run.ps1 -Market india
.EXAMPLE
    .\windows\scheduled-run.ps1 -Market us -Engine Api
#>
param(
    [Parameter(Mandatory = $true)][ValidateSet("india", "us")][string]$Market,
    [ValidateSet("Claude", "Api")][string]$Engine = "Claude"
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONUTF8 = "1"

$logDir = Join-Path $Root "reports\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("{0}-{1}.log" -f (Get-Date -Format "yyyy-MM-dd"), $Market)
"=== $(Get-Date -Format s)  market=$Market  engine=$Engine ===" | Out-File -FilePath $log -Append -Encoding utf8

if ($Engine -eq "Claude") {
    $claude = Get-Command claude -ErrorAction SilentlyContinue
    if (-not $claude) {
        "claude was not found on PATH. Install Claude Code:  irm https://claude.ai/install.ps1 | iex" |
            Out-File -FilePath $log -Append -Encoding utf8
        exit 1
    }
    & $claude.Source -p "/analyze-stocks --market $Market" 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
}
else {
    & (Join-Path $Root ".venv\Scripts\python.exe") (Join-Path $Root "run.py") --market $Market 2>&1 |
        Out-File -FilePath $log -Append -Encoding utf8
}
$code = $LASTEXITCODE
"=== finished with exit code $code ===" | Out-File -FilePath $log -Append -Encoding utf8
exit $code
