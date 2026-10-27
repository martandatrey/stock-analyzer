"""Standalone Stock Analyzer: the same pipeline as /analyze-stocks, driven by the Claude API.

    .venv/bin/python run.py                       # every stock with Analyze? = Y
    .venv/bin/python run.py --ticker RELIANCE     # one stock
    .venv/bin/python run.py --market us           # only NASDAQ/NYSE rows
    .venv/bin/python run.py --depth Quick         # override depth for this run
    .venv/bin/python run.py --dry-run             # fill every prompt into reports/_dry-run/, no API calls, no Excel writes

Needs ANTHROPIC_API_KEY in .env (except --dry-run). Stocks are analysed one at a time.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date

from dotenv import load_dotenv

from stock_analyzer import config, llm, pipeline, report, second_opinion
from stock_analyzer.excel_io import Book, WorkbookOpenError

load_dotenv(config.ROOT / ".env")
log = logging.getLogger("run")


def analyse(row, book: Book, settings: dict, as_of: date, dry_run: bool, force: bool) -> dict:
    root = config.REPORTS_DIR / "_dry-run" if dry_run else config.REPORTS_DIR
    run = pipeline.prepare(row, book, settings, as_of, force=force or dry_run, root=root)
    print(f"  prepared {run.dir.relative_to(config.ROOT)} ({len(pipeline.all_stages(run))} stages)", flush=True)
    if dry_run:
        # Without outputs, later prompts show placeholders like "None yet"; that's expected for a dry run.
        for stage in pipeline.all_stages(run):
            pipeline.fill_prompt(run, stage)
        return {"ticker": row.ticker, "dry_run": True, "prompts": str(run.dir / "prompts")}

    if row.second_opinion:
        ok, why = second_opinion.available()
        print(f"  2nd opinion: {'running TradingAgents (10-20 min)' if ok else 'skipped, ' + why}", flush=True)
        if ok:
            second_opinion.run(run, settings)

    for stage in pipeline.all_stages(run):
        system, user = pipeline.fill_prompt(run, stage)
        try:
            out = llm.complete(stage, system, user, settings)
            pipeline.record(run, stage, out)
            print(f"  ✓ {stage}", flush=True)
        except (llm.LLMError, ValueError) as exc:
            pipeline.abstain(run, stage, str(exc))
            print(f"  ✗ {stage}: abstained ({exc})", flush=True)
    try:
        return pipeline.finalize(run)
    except WorkbookOpenError as exc:
        report.render(run, second_opinion.load(run))
        return {"ticker": row.ticker, "report": str(run.dir / "report.html"), "warning": str(exc)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ticker")
    ap.add_argument("--market", choices=["india", "us"])
    ap.add_argument("--date", default=date.today().isoformat(), help="as-of date, YYYY-MM-DD")
    ap.add_argument("--depth", choices=config.DEPTHS)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="re-analyse a close that was already reported")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    as_of = date.fromisoformat(args.date)
    book = Book()
    settings = book.settings()
    rows = pipeline.select_rows(book, settings, args.ticker, args.market)
    results = []
    for row in rows:
        if args.depth:
            row.depth = args.depth
        print(f"\n▶ {row.ticker} ({row.exchange}) · {row.horizon} · {row.depth}", flush=True)
        if row.errors:
            results.append({"ticker": row.ticker, "error": "; ".join(row.errors)})
            print(f"  skipped: {'; '.join(row.errors)}")
            continue
        try:
            results.append(analyse(row, book, settings, as_of, args.dry_run, args.force))
        except pipeline.AlreadyReported as exc:
            results.append({"ticker": row.ticker, "skipped": str(exc)})
            print(f"  skipped: {exc}")
        except Exception as exc:  # one stock failing never stops the others
            log.exception("failed: %s", row.ticker)
            results.append({"ticker": row.ticker, "error": f"{type(exc).__name__}: {exc}"})
        book = Book()  # pick up this stock's writes before the next one
    day = config.REPORTS_DIR / as_of.isoformat()
    if day.is_dir() and not args.dry_run:
        print(f"\nIndex: {report.build_index(as_of.isoformat())}")
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
