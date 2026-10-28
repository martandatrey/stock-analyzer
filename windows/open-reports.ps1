<#
.SYNOPSIS
    Open a day's report index in your default browser (today's by default, else the latest day).

.EXAMPLE
    .\windows\open-reports.ps1
.EXAMPLE
    .\windows\open-reports.ps1 -Date 2026-10-27
#>
param([string]$Date = (Get-Date -Format "yyyy-MM-dd"))

$Root = Split-Path -Parent $PSScriptRoot
$reports = Join-Path $Root "reports"
$index = Join-Path $reports "$Date\index.html"
if (-not (Test-Path $index)) {
    $latest = Get-ChildItem $reports -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^\d{4}-\d{2}-\d{2}$' -and (Test-Path (Join-Path $_.FullName "index.html")) } |
        Sort-Object Name -Descending | Select-Object -First 1
    if (-not $latest) { throw "No reports yet. Run /analyze-stocks in Claude Code, or .\windows\run.ps1" }
    Write-Host "No reports for $Date; opening the latest day, $($latest.Name)."
    $index = Join-Path $latest.FullName "index.html"
}
Invoke-Item $index
