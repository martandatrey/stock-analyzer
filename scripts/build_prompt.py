"""Fill one stage's prompt for a stock, save it to the run folder, and print it.

    python scripts/build_prompt.py --dir reports/2026-10-27/RELIANCE_NSE --stage analysts/technical
    python scripts/build_prompt.py --dir reports/2026-10-27/RELIANCE_NSE --next     # first stage without output
    python scripts/build_prompt.py --dir reports/2026-10-27/RELIANCE_NSE --list     # pending stages

After the prompt it prints the path where that stage's JSON output must be written.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stock_analyzer import pipeline
from stock_analyzer.runfolder import RunFolder


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True, help="the stock's run folder")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--stage")
    g.add_argument("--next", action="store_true")
    g.add_argument("--list", action="store_true")
    args = ap.parse_args()

    run = RunFolder.at(Path(args.dir))
    pending = pipeline.pending_stages(run)
    if args.list:
        print(json.dumps({"pending": pending, "done": [s for s in pipeline.all_stages(run) if s not in pending]},
                         indent=2))
        return
    stage = args.stage or (pending[0] if pending else None)
    if stage is None:
        print("ALL STAGES DONE. Run scripts/render_report.py --dir " + args.dir)
        return
    system, user = pipeline.fill_prompt(run, stage)
    print(f"STAGE: {stage}\nPROMPT SAVED TO: {run.prompt_path(stage)}\n")
    print("=" * 80)
    print(system)
    print("\n" + "-" * 80 + "\n")
    print(user)
    print("=" * 80)
    print(f"\nWRITE THE JSON OUTPUT TO: {run.output_path(stage)}")
    print(f"THEN RUN: .venv/bin/python scripts/record_output.py --dir {args.dir} --stage {stage}")


if __name__ == "__main__":
    main()
