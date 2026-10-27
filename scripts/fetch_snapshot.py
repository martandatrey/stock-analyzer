"""Prepare one stock's run folder: fetch data, plan the stages, and find past calls to settle.

    python scripts/fetch_snapshot.py --ticker RELIANCE [--exchange NSE] [--date 2026-10-27] [--force]

Prints a JSON summary with the run folder and the stages still to do.
Exit code 3 means the latest close was already analysed (e.g. a market holiday): skip the stock.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from stock_analyzer import config, pipeline
from stock_analyzer.excel_io import Book

load_dotenv(config.ROOT / ".env")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ticker", required=True)
    ap.add_argument("--exchange", help="only needed if the same ticker is listed on two exchanges")
    ap.add_argument("--date", default=date.today().isoformat(), help="as-of date, YYYY-MM-DD (default today)")
    ap.add_argument("--force", action="store_true", help="analyse even if this close was already reported")
    args = ap.parse_args()

    book = Book()
    settings = book.settings()
    rows = pipeline.select_rows(book, settings, args.ticker)
    if args.exchange:
        rows = [r for r in rows if r.exchange == args.exchange.upper()]
    if len(rows) != 1:
        sys.exit(f"Expected exactly one row for {args.ticker}; found {len(rows)}. Pass --exchange.")
    try:
        run = pipeline.prepare(rows[0], book, settings, date.fromisoformat(args.date), force=args.force)
    except pipeline.AlreadyReported as exc:
        print(json.dumps({"skip": True, "reason": str(exc)}))
        sys.exit(3)
    data = run.data
    print(json.dumps({
        "run_dir": str(run.dir),
        "ticker": data["ticker"], "exchange": data["exchange"], "symbol": data["symbol"],
        "company": (data.get("company") or {}).get("name"),
        "price": data["price"], "currency": data["currency"], "data_as_of": data["data_as_of"],
        "data_gaps": data["data_gaps"],
        "depth": run.stock["depth"],
        "pending_reflections": len(run.stock["pending_reflections"]),
        "stages": pipeline.all_stages(run),
        "second_opinion": run.stock["second_opinion"],
    }, indent=2))


if __name__ == "__main__":
    main()
