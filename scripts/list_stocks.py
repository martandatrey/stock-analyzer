"""List the stocks to analyse, as JSON (used by /analyze-stocks and the scheduled runs).

    python scripts/list_stocks.py                     # every row with Analyze? = Y
    python scripts/list_stocks.py --market india      # only NSE/BSE rows
    python scripts/list_stocks.py --ticker RELIANCE   # one stock, even if Analyze? = N
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stock_analyzer.excel_io import Book
from stock_analyzer.pipeline import select_rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ticker")
    ap.add_argument("--market", choices=["india", "us"])
    args = ap.parse_args()
    book = Book()
    settings = book.settings()
    try:
        rows = select_rows(book, settings, args.ticker, args.market)
    except LookupError as exc:
        sys.exit(str(exc))
    out = [{"ticker": r.ticker, "exchange": r.exchange, "key": r.key, "status": r.status, "horizon": r.horizon,
            "depth": r.depth, "second_opinion": r.second_opinion, "errors": r.errors} for r in rows]
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
