"""Validate a stage output written by the agent (normalising near-misses in place), or record an abstention.

    python scripts/record_output.py --dir <run folder> --stage analysts/technical
    python scripts/record_output.py --dir <run folder> --stage personas/graham --abstain "data too thin"

Exit code 1 with the list of problems if the JSON doesn't match the stage's schema.
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
    ap.add_argument("--dir", required=True)
    ap.add_argument("--stage", required=True)
    ap.add_argument("--abstain", metavar="REASON")
    args = ap.parse_args()
    run = RunFolder.at(Path(args.dir))
    if args.abstain:
        pipeline.abstain(run, args.stage, args.abstain)
    else:
        path = run.output_path(args.stage)
        if not path.exists():
            sys.exit(f"{path} does not exist; write the stage's JSON there first.")
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            sys.exit(f"{path} is not valid JSON: {exc}")
        try:
            pipeline.record(run, args.stage, obj)
        except ValueError as exc:
            sys.exit(f"INVALID: {exc}\nFix {path} and run this again.")
    left = pipeline.pending_stages(run)
    print(f"OK {args.stage}. Next: {left[0] if left else 'none, run scripts/render_report.py'}")


if __name__ == "__main__":
    main()
