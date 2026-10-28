# Stock Analyzer on Windows

This folder holds the Windows versions of the files that differ between Mac and Windows: the setup script, the runner, the scheduler and the Claude Code permission rules. Everything else is shared: the Python code, the prompts, and the `/analyze-stocks` command and its agents. Each copy/paste block below is one PowerShell command.

> Windows support is new: these scripts were written alongside the Mac version but haven't yet been run on a Windows PC. If a step fails, check [Troubleshooting](#troubleshooting) and report anything that doesn't work.

---

## What you need

| Need | Why |
|---|---|
| **Windows 10 (1809 or later) or Windows 11** | Supported by Claude Code |
| **Git for Windows** | To download the code. It also provides **Git Bash**, which Claude Code uses to run this project's trading-block safety hook |
| **uv** (recommended) or Python 3.11+ | Builds the Python environments; uv downloads the right Python by itself |
| **Microsoft Excel** | To edit `stocks.xlsx` |
| **Claude desktop app** or **Claude Code** | Runs `/analyze-stocks` and the daily schedule |
| *Optional:* Anthropic API key | Only for `windows\run.ps1` (standalone) and the TradingAgents 2nd opinion |

---

## 1. Install the tools (once)

Open **PowerShell** from the Start menu. You don't need administrator rights.

```powershell
winget install --id Git.Git -e
```
```powershell
winget install --id astral-sh.uv -e
```
```powershell
irm https://claude.ai/install.ps1 | iex
```

**Close PowerShell and open a new window**, so the new commands are found. Then check all three:

```powershell
git --version; uv --version; claude --version
```

If you prefer the desktop app, download it from <https://claude.ai/download>. Its Code tab and its scheduler work with this project too.

---

## 2. Get the code

The repository is private, so its owner must first add you as a collaborator on GitHub. Then:

```powershell
git clone https://github.com/martandatrey/stock-analyzer.git "$HOME\Stock Analyzer"
```
```powershell
cd "$HOME\Stock Analyzer"
```

The first time, a browser window asks you to sign in to GitHub.

**Downloaded a ZIP instead?** Unzip it, open PowerShell in that folder, and unblock the scripts so Windows will run them:
```powershell
Get-ChildItem -Recurse | Unblock-File
```

---

## 3. Run the setup (2–5 minutes, safe to re-run)

```powershell
powershell -ExecutionPolicy Bypass -File windows\setup.ps1
```

What it does:
- creates `.venv` (the analyzer) and `.venv-ta` (TradingAgents)
- downloads TradingAgents and ai-hedge-fund into `vendor\`
- creates **your own** `stocks.xlsx` and `.env`
- adds the Windows permission rules from `windows\claude-settings.windows.json` to `.claude\settings.local.json`
- runs a self-check

To skip the optional TradingAgents 2nd opinion, add `-NoTradingAgents` to the end.

`-ExecutionPolicy Bypass` applies to that one run only. To run the helper scripts directly (`.\windows\run.ps1` and so on), allow local scripts for your account once:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

---

## 4. Add your stocks

```powershell
Invoke-Item stocks.xlsx
```

Replace the two example rows (RELIANCE, AAPL) with your own; the [main README](../README.md#4-the-excel-workbook) explains every column. **Save and close Excel** before an analysis runs. Windows locks a workbook while Excel has it open, and the agent will not overwrite your edits.

---

## 5. Run your first analysis in Claude Code

In the **desktop app**, open the Code tab and choose the `Stock Analyzer` folder. Or, from PowerShell in that folder:

```powershell
claude
```

Then type:
```
/analyze-stocks RELIANCE
```

When Claude asks to use a connector or web search, choose **"Always allow"**. That saves the approval in `.claude\settings.local.json`, so scheduled runs never stop to ask. The other forms work the same as on Mac: `/analyze-stocks`, `/analyze-stocks --market india`, `/analyze-stocks --market us`.

---

## 6. Schedule the daily runs

Pick **one** of these. Using both runs every stock twice a day.

**Option A: Claude desktop app scheduler.** Type this in Claude:
```
/setup-schedule
```
Indian stocks run at 4:30 pm IST Mon–Fri and US stocks at 7:30 am IST Tue–Sat, converted to your time zone. They run while the desktop app is open; a run that was due while it was closed happens on the next launch.

**Option B: Windows Task Scheduler.** No desktop app needed; it runs while you're signed in to Windows:
```powershell
.\windows\schedule.ps1
```

| To | Run |
|---|---|
| Choose your own IST times | `.\windows\schedule.ps1 -IndiaIST 17:00 -UsIST 08:00` |
| Use the standalone engine (needs an API key) | `.\windows\schedule.ps1 -Engine Api` |
| Remove the tasks | `.\windows\schedule.ps1 -Remove` |

Logs go to `reports\logs\`.

---

## 7. Read the reports

```powershell
.\windows\open-reports.ps1
```

This opens today's `reports\<date>\index.html` (or the latest day's) in your browser. Each stock links to its full report.

---

## Standalone runs (Claude API)

Put your key in `.env` (`ANTHROPIC_API_KEY=sk-ant-...`):
```powershell
notepad .env
```
Then:
```powershell
.\windows\run.ps1 --ticker AAPL
```
```powershell
.\windows\run.ps1 --market india --depth Quick
```
```powershell
.\windows\run.ps1 --dry-run
```
`--dry-run` fills every prompt into `reports\_dry-run\` without calling the API.

---

## Updating to a newer version

```powershell
git pull
```
```powershell
powershell -ExecutionPolicy Bypass -File windows\setup.ps1
```

Your `stocks.xlsx`, reports and `.env` are never touched by an update.

---

## What's in this folder

| File | Windows version of | What it does |
|---|---|---|
| `setup.ps1` | `setup.sh` | One-time setup and self-check |
| `run.ps1` | `.venv/bin/python run.py` | Standalone run with the Claude API; same arguments as `run.py` |
| `schedule.ps1` | cron / launchd recipe | Creates or removes the two Task Scheduler jobs |
| `scheduled-run.ps1` | — | What each scheduled job runs; writes a log |
| `open-reports.ps1` | — | Opens a day's report index |
| `claude-settings.windows.json` | the allow rules in `.claude/settings.json` | Pre-approves `.venv/Scripts/python.exe` commands for Claude Code; merged into `.claude\settings.local.json` by setup |

### What's different on Windows, and why
- **Python's location.** A Windows virtualenv keeps Python in `.venv\Scripts\python.exe`, not `.venv/bin/python`. The shared command and agent files tell Claude to use `.venv/Scripts/python.exe` on Windows, and the permission rules here pre-approve exactly that.
- **Claude Code's shell.** On Windows, Claude Code runs commands in PowerShell, and in Git Bash when Git for Windows is installed. The `.venv/Scripts/python.exe scripts/...` form works in both.
- **Safety hook.** `.claude/hooks/block_trading.sh` runs under Git Bash. It refuses any broker order tool on every OS. Without Git Bash it can't run, so keep Git for Windows installed.
- **Line endings.** `.gitattributes` keeps shell scripts with Unix line endings and PowerShell scripts with Windows ones, whichever OS they're cloned on.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "running scripts is disabled on this system" | Use the `powershell -ExecutionPolicy Bypass -File windows\...` form, or run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once |
| `git`, `uv` or `claude` "is not recognized" | Open a **new** PowerShell window after installing; winget updates PATH only for new windows |
| Typing `python` opens the Microsoft Store | That's Windows' app alias, not a real Python. Setup uses uv instead; or turn the alias off in Settings → Apps → Advanced app settings → App execution aliases |
| Claude Code says it can't find Git Bash | Add `"env": {"CLAUDE_CODE_GIT_BASH_PATH": "C:\\Program Files\\Git\\bin\\bash.exe"}` to `%USERPROFILE%\.claude\settings.json` |
| Claude keeps asking before running `.venv/Scripts/python.exe ...` | Re-run `windows\setup.ps1` (it re-adds the rules), then choose "Always allow" |
| "stocks.xlsx is locked" / "open in Excel" | Close Excel. The report was still written; re-run `.venv\Scripts\python.exe scripts\render_report.py --dir reports\<date>\<STOCK>` to log it |
| Errors about long file names during setup | Run `git config --global core.longpaths true`, then re-run setup |
| Setup fails building a package | Try another Python: `powershell -ExecutionPolicy Bypass -File windows\setup.ps1 -PythonVersion 3.12` |
| Check the safety hook works (in Git Bash) | `echo '{"tool_name":"mcp__kite__place_order"}' \| sh .claude/hooks/block_trading.sh` should print a "deny" message |
| Prefer Linux tools? | Inside WSL (`wsl --install`), follow the main README's Mac/Linux steps instead |

Everything else (the workbook, how the analysis works, memory and the Scorecard, the 2nd opinion, safety, sharing) is in the [main README](../README.md).
