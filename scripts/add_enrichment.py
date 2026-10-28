"""Attach extra findings (connector data, web search) to a stock's data.json so every later prompt sees them.

    .venv/bin/python scripts/add_enrichment.py --dir <run folder> --file /path/to/notes.md
    .venv/bin/python scripts/add_enrichment.py --dir <run folder> --text "..."

Markdown, with a date and source for every item. Appends to anything already attached.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stock_analyzer.runfolder import RunFolder


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--file")
    g.add_argument("--text")
    args = ap.parse_args()
    text = Path(args.file).read_text(encoding="utf-8") if args.file else args.text
    run = RunFolder.at(Path(args.dir))
    data = run.data
    existing = data.get("enrichment") or ""
    data["enrichment"] = (existing + "\n\n" + text).strip() if existing else text.strip()
    run.save_data(data)
    print(f"Attached {len(text)} characters of enrichment to {run.dir / 'data.json'}")


if __name__ == "__main__":
    main()
