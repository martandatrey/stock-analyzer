"""Decision memory: settle past calls against what the price did, and collect lessons.

Idea from TradingAgents (Apache-2.0): once a call's window has passed, compute
the stock's return and its alpha vs the benchmark, score the call, and have the
reflection prompt write a short lesson that later runs of this stock read.
"""

from __future__ import annotations

import pandas as pd

from . import config, indicators, rating


def pending_settlements(history: list[dict], close: pd.Series, bench_close: pd.Series | None,
                        settle_days: dict[str, int], run_date: str) -> list[dict]:
    """Log rows of this stock whose window has passed but which have no Outcome yet."""
    out = []
    for r in history:
        if r.get("Outcome") or r.get("Rating") not in rating.RATINGS or (r.get("Date") or "") >= run_date:
            continue
        try:
            bucket = config.horizon_bucket(r.get("Horizon"))
        except ValueError:
            continue
        days = settle_days[bucket]
        start = pd.Timestamp(r.get("Data As Of") or r["Date"])
        # Measure from the close the call was based on, so the first move after the call counts.
        fwd = indicators.forward_return(close, start, days)
        if fwd is None:
            continue
        raw, end = fwd
        bench = None
        if bench_close is not None:
            b = bench_close[bench_close.index >= start]
            if len(b) > days:
                bench = float(b.iloc[days] / b.iloc[0] - 1)
        alpha = raw - bench if bench is not None else raw
        out.append({
            "log_row": r["_row"],
            "date": r["Date"],
            "rating": r["Rating"],
            "confidence": r.get("Confidence"),
            "summary": r.get("Summary") or "",
            "horizon": r.get("Horizon"),
            "bucket": bucket,
            "settle_days": days,
            "settled_on": end.strftime("%Y-%m-%d"),
            "raw_return": round(raw, 4),
            "benchmark_return": None if bench is None else round(bench, 4),
            "alpha": round(alpha, 4),
            "outcome": rating.outcome(r["Rating"], alpha, bucket),
        })
    return out


def lessons(history: list[dict], limit: int = 3) -> list[dict]:
    """Most recent settled calls that already carry a lesson, newest first."""
    done = [r for r in history if r.get("Lesson")]
    done.sort(key=lambda r: r.get("Date") or "", reverse=True)
    return [{"date": r["Date"], "rating": r.get("Rating"), "alpha": r.get("Alpha"),
             "outcome": r.get("Outcome"), "lesson": r["Lesson"]} for r in done[:limit]]


def reflection_stage(p: dict) -> str:
    return f"memory/reflection@{p['date']}"


def reflection_context(p: dict, stock: dict, data: dict) -> dict:
    """Placeholders for prompts/memory/reflection.md (plus the system prompt's)."""
    row = stock["row"]
    pct = lambda v: "n/a" if v is None else f"{v * 100:+.1f}%"  # noqa: E731
    conf = p.get("confidence")
    return {
        "as_of": data["as_of"], "data_as_of": data["data_as_of"],
        "horizon": p.get("horizon") or row["horizon"], "bucket": p.get("bucket") or row["bucket"],
        "call_date": p["date"], "ticker": row["ticker"], "exchange": row["exchange"],
        "rating": p["rating"],
        "confidence": f"{conf:.0%}" if isinstance(conf, float) and conf <= 1 else (conf or "n/a"),
        "call_summary": p.get("summary") or "n/a",
        "settle_days": p["settle_days"],
        "raw_return": pct(p["raw_return"]), "benchmark_return": pct(p["benchmark_return"]),
        "alpha": pct(p["alpha"]), "outcome": p["outcome"],
        "benchmark": (data.get("market_context") or {}).get("benchmark", "Benchmark"),
    }
