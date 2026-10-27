"""Rebuild reports/<date>/index.html from every stock folder present for that date.

    python scripts/build_index.py [--date 2026-10-27]
"""

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stock_analyzer import config, report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", default=date.today().isoformat())
    args = ap.parse_args()
    if not (config.REPORTS_DIR / args.date).is_dir():
        sys.exit(f"No reports for {args.date}")
    print(report.build_index(args.date))


if __name__ == "__main__":
    main()
