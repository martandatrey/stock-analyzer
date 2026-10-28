---
description: Analyse the stocks in stocks.xlsx one at a time and write an HTML report for each
argument-hint: "[TICKER | --market india | --market us]"
---

# Analyse stocks

Arguments: `$ARGUMENTS`

You are running the Stock Analyzer pipeline in this project folder. All commands are run from the project root with relative paths, exactly as written below (they are pre-approved in `.claude/settings.json`). Never place, modify or cancel any order with any broker tool. This is research only.

**Windows:** wherever this file says `.venv/bin/python`, use `.venv/Scripts/python.exe` instead. Keep the forward slashes; that form works in both PowerShell and Git Bash and matches the pre-approved rules.

## 1. Pick the stocks

Work out the arguments for `list_stocks.py` from `$ARGUMENTS`:
- empty: no arguments (every row with Analyze? = Y)
- `--market india` or `--market us`: pass it through
- anything else is a ticker: `--ticker <TICKER>`

```
.venv/bin/python scripts/list_stocks.py <args>
```

Rows with a non-empty `errors` list can't be analysed: note them for the final summary and skip them.

## 2. Analyse each stock, one at a time

Finish one stock completely before starting the next. For each stock:

**a. Prepare.**
```
.venv/bin/python scripts/fetch_snapshot.py --ticker <TICKER> --exchange <EXCHANGE>
```
- Exit code 3 means this close was already analysed (a market holiday, for example). Record "skipped" and move on.
- Any other failure: record the error and move on.
- On success, keep `run_dir` and the `stages` list from the JSON it prints.

**b. 2nd opinion (only if `second_opinion` is true).** Start it now in the background, because it takes 10-20 minutes and runs alongside the other steps:
```
.venv/bin/python scripts/run_second_opinion.py --dir <run_dir>
```
Use `run_in_background`. If it reports `skipped` (for example, no API key), carry on without it.

**c. Analyst stage.** Launch the `stock-analyst` subagent, telling it the `run_dir`, ticker, exchange and market. It handles reflections on past calls, enrichment, the four analysts and the investor personas. Wait for it to finish.

**d. Debate.** For each round `n` listed in `stages` (`debate/bull@n`, `debate/bear@n`):
- Launch `bull-researcher` with the `run_dir` and stage `debate/bull@n`, and wait for it.
- Then launch `bear-researcher` with stage `debate/bear@n`, and wait for it.

Skip this step if `stages` has no debate stages (Quick depth).

**e. Decision.** Launch the `portfolio-manager` subagent with the `run_dir`. It does the research manager stage (if listed), the risk views (Deep depth) and the final decision.

**f. Check.**
```
.venv/bin/python scripts/build_prompt.py --dir <run_dir> --list
```
If anything is still pending, do it yourself with the stage protocol below, or abstain it with a reason.

**g. Finish.** If a 2nd opinion was started, wait until its background task has finished. Then run:
```
.venv/bin/python scripts/render_report.py --dir <run_dir>
```
This writes `report.html`, updates `stocks.xlsx` (Analysis Log, Stocks row, Scorecard) and refreshes the day's index. If it says the workbook is open in Excel, the report is still written. Note it for the summary so the user can close Excel and re-run that one command.

## 3. Wrap up

Run `.venv/bin/python scripts/build_index.py`, then reply with:
- a table with one row per stock: ticker, rating, action, confidence, report path
- skipped and failed stocks, and why
- the path to `reports/<today>/index.html`

## Stage protocol (used by every subagent, and by you for any leftover stage)

1. `.venv/bin/python scripts/build_prompt.py --dir <run_dir> --stage <stage>` prints the filled prompt and saves it under `prompts/`.
2. Do exactly what the prompt asks, using only its data.
3. Write the single JSON object to the output path it printed, using the Write tool.
4. `.venv/bin/python scripts/record_output.py --dir <run_dir> --stage <stage>` validates the output. If it prints INVALID, fix the file and run it again.
5. If the stage truly can't be done, record an abstention instead: `.venv/bin/python scripts/record_output.py --dir <run_dir> --stage <stage> --abstain "<reason>"`.
