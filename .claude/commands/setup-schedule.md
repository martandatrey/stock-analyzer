---
description: Create (or update) the two daily scheduled runs of /analyze-stocks in the Claude desktop app
argument-hint: "[india HH:MM IST] [us HH:MM IST]   e.g. 16:30 07:30"
---

# Set up the daily schedule

Arguments: `$ARGUMENTS`

This creates two **local** scheduled tasks in the Claude desktop app. They have to be local, not cloud routines, because they read `stocks.xlsx` and write reports on this computer.

1. **Find this project's absolute path.** Run `pwd`. Call it PROJECT.

2. **Work out the times.**
   - With no arguments: `.venv/bin/python scripts/schedule_times.py`
   - With two times: `.venv/bin/python scripts/schedule_times.py --india <first> --us <second>`

   This prints a cron expression for each task in this machine's local time. The defaults are 4:30 pm IST Mon–Fri for India (after NSE closes) and 7:30 am IST Tue–Sat for the US (after the overnight NYSE close).

3. **Check for existing tasks.** List the scheduled tasks. If `stock-analyzer-india` or `stock-analyzer-us` already exists, update it (schedule and prompt) instead of creating a duplicate.

4. **Create or update each task** with the scheduled-tasks tool, using the values below. Leave `notifyOnCompletion` on.

   | Field | India task | US task |
   |---|---|---|
   | `taskId` | `stock-analyzer-india` | `stock-analyzer-us` |
   | `title` | "Stock Analyzer: India stocks (daily)" | "Stock Analyzer: US stocks (daily)" |
   | `description` | "Daily analysis of NSE/BSE stocks in stocks.xlsx" | "Daily analysis of NASDAQ/NYSE stocks in stocks.xlsx" |
   | `cronExpression` | the `india.cron` value | the `us.cron` value |
   | `prompt` | the text below, with MARKET = `india` | the text below, with MARKET = `us` |

   In the prompt text, replace PROJECT with the real path and MARKET with the market:

   ```
   Run the Stock Analyzer daily analysis for MARKET stocks.

   Project folder: PROJECT

   1. Work in that folder. If your current working directory is different, switch to it first (use the change-directory tool if you have one). Run every command from that folder with relative paths.
   2. Run the /analyze-stocks command with the argument "--market MARKET". If slash commands aren't available, read .claude/commands/analyze-stocks.md and follow its steps with ARGUMENTS = "--market MARKET".
   3. This run is unattended, so don't ask questions. Zerodha Kite needs a manual daily login: if a Kite tool says you aren't logged in, skip Kite and carry on. Never place, modify or cancel any order.
   4. If stocks.xlsx is open in Excel, reports are still written. Say so in the summary.
   5. Finish with a short summary: one line per stock with rating, action and report path, then any skipped or failed stocks, then the path to reports/<today>/index.html.
   ```

5. **Confirm.** List the scheduled tasks again and tell the user:
   - each task's next run time
   - tasks only run while the Claude app is open; one that was due while the app was closed runs on the next launch
   - the first unattended run may stop on a permission prompt for a connector tool. The fix is to run `/analyze-stocks <one ticker>` manually once and choose "Always allow" for the Financial Modeling Prep / Kite / web search tools it uses.
