<#
.SYNOPSIS
    One-time setup for Stock Analyzer on Windows (the Windows version of setup.sh). Safe to re-run.

.DESCRIPTION
    Creates .venv (the analyzer) and .venv-ta (TradingAgents), downloads TradingAgents and
    ai-hedge-fund into vendor\, creates your own stocks.xlsx and .env, adds the Windows
    permission rules for Claude Code to .claude\settings.local.json, and runs a self-check.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File windows\setup.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File windows\setup.ps1 -NoTradingAgents
#>
[CmdletBinding()]
param(
    [switch]$NoTradingAgents,
    [string]$PythonVersion = "3.13"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONUTF8 = "1"
$TaTag = "v0.7.0"

function Say([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

# Runs a program, shows its output, and stops the script if it fails.
function Invoke-Checked([string]$Exe, [string[]]$Arguments) {
    & $Exe @Arguments | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "Command failed (exit $LASTEXITCODE): $Exe $($Arguments -join ' ')" }
}

# A Python 3.11+ to build the virtualenvs with, used only when uv is not installed.
function Find-Python {
    $ErrorActionPreference = "Continue"
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($v in @($PythonVersion, "3.13", "3.12", "3.11")) {
            & py "-$v" -c "import sys" 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { return @("py", "-$v") }
        }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        & python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { return @("python") }
    }
    throw "Python 3.11+ not found. Install uv (recommended):  winget install astral-sh.uv   or Python:  winget install Python.Python.3.13"
}

$Uv = Get-Command uv -ErrorAction SilentlyContinue

# Creates a virtualenv (if missing), installs packages into it, and returns its python.exe.
function New-Venv([string]$Dir, [string[]]$Packages) {
    $py = Join-Path $Root "$Dir\Scripts\python.exe"
    if ($Uv) {
        if (-not (Test-Path $py)) { Invoke-Checked "uv" @("venv", $Dir, "--python", $PythonVersion, "--quiet") }
        Invoke-Checked "uv" (@("pip", "install", "--python", $py, "--quiet") + $Packages)
    }
    else {
        $base = @(Find-Python)
        if (-not (Test-Path $py)) {
            Invoke-Checked $base[0] (@($base | Select-Object -Skip 1) + @("-m", "venv", $Dir))
        }
        Invoke-Checked $py @("-m", "pip", "install", "--quiet", "--upgrade", "pip")
        Invoke-Checked $py (@("-m", "pip", "install", "--quiet") + $Packages)
    }
    return $py
}

# --- Prerequisites ------------------------------------------------------------

$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git) {
    throw "git not found. Install Git for Windows:  winget install Git.Git   (then open a new PowerShell window)"
}
$gitRoot = Split-Path (Split-Path $git.Source)
$gitBash = Join-Path $gitRoot "bin\bash.exe"
if (-not (Test-Path $gitBash)) {
    Write-Warning "Git Bash not found at $gitBash. Claude Code runs this project's trading-block hook with Git Bash; install Git for Windows from https://git-scm.com/download/win"
}
if (-not $Uv) {
    Write-Host "uv not found; using your installed Python instead (uv is faster:  winget install astral-sh.uv)"
}

# --- Environments -----------------------------------------------------------------

Say "Installing the analyzer into .venv (OpenBB, yfinance, pandas, openpyxl, anthropic...)"
$Py = New-Venv ".venv" @("-r", "requirements.txt")

Say "Fetching third-party repos into vendor\"
New-Item -ItemType Directory -Force -Path (Join-Path $Root "vendor") | Out-Null
if (-not (Test-Path (Join-Path $Root "vendor\TradingAgents"))) {
    Invoke-Checked "git" @("-c", "core.longpaths=true", "clone", "--quiet", "--depth", "1", "--branch", $TaTag,
        "https://github.com/TauricResearch/TradingAgents.git", "vendor/TradingAgents")
}
if (-not (Test-Path (Join-Path $Root "vendor\ai-hedge-fund"))) {
    # Reference only: its persona ideas are re-written in prompts\personas\. Nothing from it is installed.
    Invoke-Checked "git" @("-c", "core.longpaths=true", "clone", "--quiet", "--depth", "1",
        "https://github.com/virattt/ai-hedge-fund.git", "vendor/ai-hedge-fund")
}

if ($NoTradingAgents) {
    Say "Skipping TradingAgents (the 2nd opinion will be unavailable)"
}
else {
    Say "Installing TradingAgents $TaTag into .venv-ta (kept separate so its dependencies never clash)"
    New-Venv ".venv-ta" @("./vendor/TradingAgents") | Out-Null
}

# --- Personal files -----------------------------------------------------------------

Say "Creating your personal files"
if (-not (Test-Path (Join-Path $Root "stocks.xlsx"))) {
    if (-not (Test-Path (Join-Path $Root "templates\stocks.template.xlsx"))) {
        Invoke-Checked $Py @("scripts/create_workbook.py", "--template")
    }
    Copy-Item (Join-Path $Root "templates\stocks.template.xlsx") (Join-Path $Root "stocks.xlsx")
    Write-Host "Created stocks.xlsx from the template. Replace the example rows with your own stocks."
}
else {
    Write-Host "stocks.xlsx already exists, leaving it alone."
}
if (-not (Test-Path (Join-Path $Root ".env"))) {
    Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env")
    Write-Host "Created .env (add ANTHROPIC_API_KEY only if you use run.ps1 or the 2nd opinion)."
}

# --- Claude Code permission rules for Windows paths ----------------------------------

Say "Adding the Windows permission rules to .claude\settings.local.json"
$localPath = Join-Path $Root ".claude\settings.local.json"
$extra = Get-Content (Join-Path $PSScriptRoot "claude-settings.windows.json") -Raw | ConvertFrom-Json
if (Test-Path $localPath) {
    $local = Get-Content $localPath -Raw | ConvertFrom-Json
}
else {
    $local = New-Object PSObject
}
if (-not $local.PSObject.Properties["permissions"]) {
    $local | Add-Member -NotePropertyName "permissions" -NotePropertyValue (New-Object PSObject)
}
if (-not $local.permissions.PSObject.Properties["allow"]) {
    $local.permissions | Add-Member -NotePropertyName "allow" -NotePropertyValue @()
}
$local.permissions.allow = @(@($local.permissions.allow) + @($extra.permissions.allow) | Where-Object { $_ } | Select-Object -Unique)
$json = $local | ConvertTo-Json -Depth 20
# UTF-8 without a byte-order mark: Claude Code reads settings as strict JSON.
[System.IO.File]::WriteAllText($localPath, $json, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "Done ($($local.permissions.allow.Count) allow rules)."

# --- Self-check -----------------------------------------------------------------------

Say "Self-check"
Invoke-Checked $Py @("scripts/selfcheck.py")

Say "Done"
Write-Host @"
Next steps:
  1. Open stocks.xlsx and add your stocks (keep it closed while an analysis runs).
  2. Open this folder in Claude Code and run:   /analyze-stocks <TICKER>
     Approve the tools it asks for ("Always allow") so scheduled runs can work unattended.
  3. Schedule the daily runs:                   /setup-schedule   (or windows\schedule.ps1)
  Standalone (Claude API key in .env):          .\windows\run.ps1 --help
  Open today's reports:                         .\windows\open-reports.ps1
"@
