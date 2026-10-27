"""Finish one stock: render report.html and record the run in stocks.xlsx (log, Stocks row, Scorecard).

    python scripts/render_report.py --dir reports/2026-10-27/RELIANCE_NSE
    python scripts/render_report.py --dir ... --no-excel     # report only (e.g. while Excel is open)
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stock_analyzer import pipeline, report, second_opinion
from stock_analyzer.excel_io import WorkbookOpenError
from stock_analyzer.runfolder import RunFolder


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--no-excel", action="store_true")
    args = ap.parse_args()
    run = RunFolder.at(Path(args.dir))
    if args.no_excel:
        print(report.render(run, second_opinion.load(run)))
        return
    try:
        summary = pipeline.finalize(run)
    except WorkbookOpenError as exc:
        report.render(run, second_opinion.load(run))
        sys.exit(f"Report written, but the workbook was not updated: {exc}\n"
                 f"Re-run: .venv/bin/python scripts/render_report.py --dir {args.dir}")
    report.build_index(run.run_date, run.dir.parent.parent)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
