"""Offline health check run at the end of setup.sh: imports, workbook, prompt files, hook, optional parts."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stock_analyzer import config, prompts, second_opinion
from stock_analyzer.excel_io import Book

ok = True


def check(label, fn):
    global ok
    try:
        detail = fn()
        print(f"  ✓ {label}" + (f": {detail}" if detail else ""))
    except Exception as exc:
        ok = False
        print(f"  ✗ {label}: {exc}")


def workbook():
    book = Book()
    rows = book.stocks()
    bad = [f"{r.ticker}: {'; '.join(r.errors)}" for r in rows if r.errors]
    if bad:
        raise ValueError("; ".join(bad))
    return f"{len(rows)} stock rows"


def prompt_files():
    stages = {f"analysts/{a}" for a in config.ANALYSTS} | {f"risk/{v}" for v in config.RISK_VIEWS}
    stages |= {f"personas/{p}" for ps in config.DEFAULT_PERSONAS.values() for p in ps}
    stages |= {"debate/bull", "debate/bear", "debate/research_manager", "final/portfolio_manager", "memory/reflection"}
    missing = [s for s in sorted(stages) if not prompts.template_path(s).exists()]
    if missing:
        raise FileNotFoundError(", ".join(missing))
    return f"{len(stages) + 1} templates"


def find_sh() -> str | None:
    """sh on PATH, or the one that ships with Git for Windows (Claude Code runs hooks with Git Bash there)."""
    if sh := shutil.which("sh"):
        return sh
    if git := shutil.which("git"):
        base = Path(git).resolve().parent.parent  # ...\Git\cmd\git.exe -> ...\Git
        for cand in (base / "bin" / "sh.exe", base / "usr" / "bin" / "sh.exe"):
            if cand.exists():
                return str(cand)
    return None


def hook():
    sh = find_sh()
    if sh is None:
        raise RuntimeError("sh not found. On Windows install Git for Windows (winget install Git.Git)")
    script = config.ROOT / ".claude" / "hooks" / "block_trading.sh"
    event = json.dumps({"tool_name": "mcp__kite__place_order", "tool_input": {}})
    out = subprocess.run([sh, str(script)], input=event, capture_output=True, text=True).stdout
    if "deny" not in out:
        raise RuntimeError("trading-block hook did not block place_order")
    return "blocks broker order tools"


check("Python packages (OpenBB, yfinance, pandas, openpyxl, anthropic)",
      lambda: __import__("openbb") and __import__("yfinance") and __import__("anthropic") and None)
check("stocks.xlsx", workbook)
check("prompt files", prompt_files)
check("trading-block hook", hook)
ta_ok, why = second_opinion.available()
print(f"  {'✓' if ta_ok else '•'} TradingAgents 2nd opinion: {'ready' if ta_ok else why} (optional)")
sys.exit(0 if ok else 1)
