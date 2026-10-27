"""Run TradingAgents for one stock. Executed with .venv-ta/bin/python (TradingAgents' own environment).

Called by stock_analyzer/second_opinion.py; not meant to be run by hand, but you can:

    .venv-ta/bin/python scripts/ta_runner.py --symbol RELIANCE.NS --date 2026-10-27 --out reports/.../tradingagents

Writes <out>/result.json with {rating, decision, report}.
"""

import argparse
import json
import os
import traceback
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--quick-model", default="claude-sonnet-5-5")
    ap.add_argument("--deep-model", default="claude-opus-5-5")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    try:
        from tradingagents.default_config import DEFAULT_CONFIG
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        cfg = DEFAULT_CONFIG.copy()
        cfg.update({
            "llm_provider": "anthropic",
            "quick_think_llm": args.quick_model,
            "deep_think_llm": args.deep_model,
            "max_debate_rounds": 1,
            "max_risk_discuss_rounds": 1,
            "output_language": "English",
        })
        ta = TradingAgentsGraph(selected_analysts=("market", "social", "news", "fundamentals"), config=cfg)
        state, rating = ta.propagate(args.symbol, args.date)
        report = ta.save_reports(state, args.symbol, save_path=out / "report")
        html = out / "report" / "complete_report.html"
        result = {
            "rating": rating,
            "decision": state.get("final_trade_decision", ""),
            "report": str((html if html.exists() else Path(report)).relative_to(out.parent)),
        }
    except Exception as exc:  # recorded, never raised: a failed 2nd opinion must not break the main report
        result = {"error": f"{type(exc).__name__}: {exc}", "trace": traceback.format_exc()[-2000:]}
    (out / "result.json").write_text(json.dumps(result, indent=2, default=str))
    print(json.dumps({k: v for k, v in result.items() if k != "trace"}, default=str)[:2000])


if __name__ == "__main__":
    os.environ.setdefault("TRADINGAGENTS_NO_UPDATE_CHECK", "1")
    main()
