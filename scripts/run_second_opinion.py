"""Run the TradingAgents 2nd opinion for one prepared stock (needs ANTHROPIC_API_KEY; ~10-20 min).

    python scripts/run_second_opinion.py --dir reports/2026-10-27/RELIANCE_NSE
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from stock_analyzer import config, second_opinion
from stock_analyzer.excel_io import Book
from stock_analyzer.runfolder import RunFolder

load_dotenv(config.ROOT / ".env")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True)
    args = ap.parse_args()
    ok, why = second_opinion.available()
    if not ok:
        print(json.dumps({"skipped": True, "reason": why}))
        return
    result = second_opinion.run(RunFolder.at(Path(args.dir)), Book().settings())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
