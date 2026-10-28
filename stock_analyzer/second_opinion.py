"""Optional 2nd opinion from TradingAgents (Apache-2.0), installed in its own .venv-ta.

It runs as a separate process so its dependencies never clash with ours, and a
failure there is recorded in the report instead of breaking the run.
"""

from __future__ import annotations

import json
import os
import subprocess

from . import config, rating
from .runfolder import RunFolder

RUNNER = config.ROOT / "scripts" / "ta_runner.py"
TA_PYTHON = config.venv_python(".venv-ta")


def available() -> tuple[bool, str]:
    if not TA_PYTHON.exists():
        return False, "TradingAgents is not installed (re-run setup without --no-tradingagents / -NoTradingAgents)"
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False, "ANTHROPIC_API_KEY is not set (add it to .env)"
    return True, ""


def run(folder: RunFolder, settings: dict, timeout: int = 45 * 60) -> dict:
    """Run TradingAgents for this stock and return the loaded result."""
    out = folder.dir / "tradingagents"
    out.mkdir(parents=True, exist_ok=True)
    ok, why = available()
    if not ok:
        (out / "result.json").write_text(json.dumps({"error": why}), encoding="utf-8")
        return load(folder)
    data = folder.data
    cache = config.CACHE_DIR / "tradingagents"
    env = {
        **os.environ,
        "TRADINGAGENTS_RESULTS_DIR": str(cache / "logs"),
        "TRADINGAGENTS_CACHE_DIR": str(cache / "cache"),
        "TRADINGAGENTS_MEMORY_LOG_PATH": str(cache / "memory" / "trading_memory.md"),
        "TRADINGAGENTS_NO_UPDATE_CHECK": "1",
        "PYTHONUTF8": "1",
    }
    cmd = [str(TA_PYTHON), str(RUNNER), "--symbol", data["symbol"], "--date", data["data_as_of"], "--out", str(out),
           "--quick-model", str(settings.get("TradingAgents Quick Model", "claude-sonnet-5-5")),
           "--deep-model", str(settings.get("TradingAgents Deep Model", "claude-opus-5-5"))]
    try:
        subprocess.run(cmd, env=env, cwd=config.ROOT, timeout=timeout, capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        (out / "result.json").write_text(json.dumps({"error": f"timed out after {timeout // 60} minutes"}), encoding="utf-8")
    if not (out / "result.json").exists():
        (out / "result.json").write_text(json.dumps({"error": "TradingAgents exited without a result"}), encoding="utf-8")
    return load(folder)


def load(folder: RunFolder) -> dict | None:
    """The saved 2nd opinion for this run folder, with agreement vs our own rating, or None."""
    path = folder.dir / "tradingagents" / "result.json"
    if not path.exists():
        return None
    res = json.loads(path.read_text(encoding="utf-8"))
    if res.get("error"):
        return {"rating": "Error", "error": res["error"]}
    theirs = rating.normalize(res.get("rating")) or rating.extract_rating(res.get("decision", ""))
    ours = (folder.output("final/portfolio_manager") or {}).get("rating")
    agrees = None
    if theirs in rating.RATINGS and ours in rating.RATINGS:
        agrees = rating.direction(theirs) == rating.direction(ours)
    decision = res.get("decision") or ""
    return {
        "rating": theirs or rating.REVIEW,
        "agrees": agrees,
        "excerpt": decision[:1500] + ("…" if len(decision) > 1500 else ""),
        "href": res.get("report"),
    }
