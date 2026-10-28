<#
.SYNOPSIS
    Create (or remove) two Windows Task Scheduler jobs for the daily analysis.

.DESCRIPTION
    An alternative to the Claude desktop app's scheduler (/setup-schedule). Use one or the
    other, not both, or each market will be analysed twice a day.

    Times are given in India Standard Time and converted to this PC's time zone:
      StockAnalyzer-India   Mon-Fri, default 16:30 IST (after NSE closes at 15:30)
      StockAnalyzer-US      Tue-Sat, default 07:30 IST (after the overnight NYSE close)

    -Engine Claude (default) runs  claude -p "/analyze-stocks --market ..."  (your Claude plan, no API key).
    -Engine Api runs the standalone run.py (needs ANTHROPIC_API_KEY in .env).
    Tasks run only while you are signed in to Windows; a run missed while the PC was off starts when it is next available.

.EXAMPLE
    .\windows\schedule.ps1
.EXAMPLE
    .\windows\schedule.ps1 -Engine Api -IndiaIST 17:00 -UsIST 08:00
.EXAMPLE
    .\windows\schedule.ps1 -Remove
#>
param(
    [ValidateSet("Claude", "Api")][string]$Engine = "Claude",
    [string]$IndiaIST = "16:30",
    [string]$UsIST = "07:30",
    [switch]$Remove
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$TaskPath = "\StockAnalyzer\"

if ($Remove) {
    foreach ($name in @("StockAnalyzer-India", "StockAnalyzer-US")) {
        Unregister-ScheduledTask -TaskName $name -TaskPath $TaskPath -Confirm:$false -ErrorAction SilentlyContinue
    }
    Write-Host "Removed the Stock Analyzer scheduled tasks."
    return
}

$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { throw "Not set up yet. Run:  powershell -ExecutionPolicy Bypass -File windows\setup.ps1" }
if ($Engine -eq "Claude" -and -not (Get-Command claude -ErrorAction SilentlyContinue)) {
    throw "claude not found on PATH. Install Claude Code:  irm https://claude.ai/install.ps1 | iex   (or use -Engine Api)"
}

$env:PYTHONUTF8 = "1"
$times = & $Py (Join-Path $Root "scripts\schedule_times.py") --india $IndiaIST --us $UsIST | Out-String | ConvertFrom-Json

$dayNames = @{ "0" = "Sunday"; "1" = "Monday"; "2" = "Tuesday"; "3" = "Wednesday"; "4" = "Thursday"; "5" = "Friday"; "6" = "Saturday" }
function Get-Days([string]$CronDays) {
    $out = @()
    foreach ($part in $CronDays.Split(",")) {
        if ($part -match '^(\d)-(\d)$') {
            foreach ($d in ([int]$matches[1])..([int]$matches[2])) { $out += $dayNames["$d"] }
        }
        else {
            $out += $dayNames[$part]
        }
    }
    return $out
}

$runner = Join-Path $PSScriptRoot "scheduled-run.ps1"
$jobs = @(
    @{ Name = "StockAnalyzer-India"; Market = "india"; Info = $times.india },
    @{ Name = "StockAnalyzer-US"; Market = "us"; Info = $times.us }
)
foreach ($job in $jobs) {
    $fields = $job.Info.cron.Split(" ")          # minute hour * * days
    $at = "{0:D2}:{1:D2}" -f [int]$fields[1], [int]$fields[0]
    $days = Get-Days $fields[4]
    $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $days -At $at
    $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$runner`" -Market $($job.Market) -Engine $Engine"
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arguments -WorkingDirectory $Root
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 4)
    Register-ScheduledTask -TaskName $job.Name -TaskPath $TaskPath -Trigger $trigger -Action $action `
        -Settings $settings -Description "Stock Analyzer daily $($job.Market) analysis ($Engine)" -Force | Out-Null
    Write-Host ("{0}: {1} at {2} local time ({3} IST), engine {4}" -f $job.Name, ($days -join ", "), $at, $job.Info.ist_time, $Engine)
}
Write-Host ""
Write-Host "Logs go to reports\logs\. Manage the tasks in Task Scheduler under 'StockAnalyzer'. Remove them with:  .\windows\schedule.ps1 -Remove"
