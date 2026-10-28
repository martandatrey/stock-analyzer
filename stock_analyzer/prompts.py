"""Fill prompt templates (prompts/<stage>.md) for one stock and save the filled copy.

Templates use {{placeholder}} markers. Every placeholder is built here from the
run folder (stock.json, data.json and earlier stage outputs), so the same filled
prompt is produced whether Claude Code or run.py drives the pipeline.
"""

from __future__ import annotations

import json
import re

from . import config, schemas
from .runfolder import RunFolder

_PLACEHOLDER = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")
NONE = "_None available._"


def template_path(stage: str):
    return config.PROMPTS_DIR / f"{stage.split('@')[0]}.md"


def _pct(v, signed=True):
    if v is None:
        return "n/a"
    return f"{v * 100:+.1f}%" if signed else f"{v * 100:.1f}%"


def _json(obj) -> str:
    return "```json\n" + json.dumps(obj, indent=2, ensure_ascii=False, default=str) + "\n```"


def _bullets(items) -> str:
    return "\n".join(f"- {i}" for i in items) if items else NONE


# --- blocks ---------------------------------------------------------------

def stock_block(stock: dict, data: dict) -> str:
    row = stock["row"]
    co = data.get("company") or {}
    lines = [
        f"- **Stock**: {row['ticker']} ({row['exchange']}), {co.get('name') or row.get('company') or 'name unavailable'}",
        f"- **Sector / industry**: {co.get('sector', 'n/a')} / {co.get('industry_category', 'n/a')}",
        f"- **Price**: {data['price']} {data['currency']} (close of {data['data_as_of']})",
        f"- **Investor status**: {row['status']}",
        f"- **Investment horizon**: {row['horizon']} ({row['bucket']}-term)",
        f"- **Risk tolerance**: {row['risk_tolerance']}",
    ]
    if row.get("target_return") is not None:
        lines.append(f"- **Target return over the horizon**: {row['target_return']:g}%")
    pos = data.get("position")
    if pos:
        lines.append(
            f"- **Position**: {pos['qty']:g} shares at avg {pos['avg_price']:g} {data['currency']}"
            f" (bought {pos.get('buy_date') or 'n/a'}); value {pos['market_value']:,.0f},"
            f" unrealised P&L {pos['unrealized_pnl']:,.0f} ({_pct(pos['unrealized_pnl_pct'])})"
        )
    elif row["holding"]:
        lines.append("- **Position**: holding, but quantity / average price not given")
    if row.get("notes"):
        lines.append(f"- **Investor's own thesis / notes**: {row['notes']}")
    return "\n".join(lines)


def technicals_block(data: dict) -> str:
    t = dict(data.get("technicals") or {})
    return _json(t)


def fundamentals_block(data: dict) -> str:
    return _json({
        "company": data.get("company"),
        "valuation_and_ratios": data.get("fundamentals"),
        "quarterly_results": data.get("quarterly_results"),
        "analyst_consensus": data.get("analyst_consensus"),
        "analyst_recommendations": data.get("analyst_recommendations"),
        "data_gaps": data.get("data_gaps"),
        "notes": data.get("notes"),
    })


def fundamentals_brief(data: dict) -> str:
    f = data.get("fundamentals") or {}
    keys = ("market_cap", "pe_ratio", "forward_pe", "peg_ratio", "revenue_growth", "earnings_growth",
            "profit_margin", "debt_to_equity", "return_on_equity", "dividend_yield_pct")
    q = data.get("quarterly_results") or {}
    return _json({**{k: f.get(k) for k in keys if k in f},
                  "revenue_yoy_last_quarter": q.get("revenue_yoy"),
                  "net_income_yoy_last_quarter": q.get("net_income_yoy"),
                  "analyst_consensus": data.get("analyst_consensus")})


def price_summary(data: dict) -> str:
    t = data.get("technicals") or {}
    r = t.get("returns") or {}
    return _bullets([
        f"Price {t.get('price')} {data['currency']}; 52-week range {t.get('low_52w')} - {t.get('high_52w')}"
        f" ({_pct(t.get('pct_from_52w_high'))} from the high)",
        f"Returns: 1M {_pct(r.get('1M'))}, 6M {_pct(r.get('6M'))}, 1Y {_pct(r.get('1Y'))}",
        f"Price vs 200-day average {t.get('sma200')}: {'above' if (t.get('trend') or {}).get('above_sma200') else 'below or n/a'}",
        f"1-year max drawdown {_pct(t.get('max_drawdown_1y'))}",
    ])


def street_block(data: dict) -> str:
    return _json({"analyst_consensus": data.get("analyst_consensus"),
                  "analyst_recommendations": data.get("analyst_recommendations")})


def news_block(data: dict) -> str:
    items = data.get("news") or []
    if not items:
        return "_No company headlines found for the last 14 days._"
    return "\n".join(f"- {n['date']} · {n.get('publisher') or 'unknown'} · {n['title']}" for n in items)


def enrichment_block(data: dict) -> str:
    e = data.get("enrichment")
    if not e:
        return "_None gathered._"
    if not isinstance(e, str):
        return _json(e)
    # Push its headings two levels down so they nest under the prompt's own "##" sections.
    return re.sub(r"(?m)^(#{1,6})(?=\s)", lambda m: "#" * min(6, len(m.group(1)) + 2), e)


def risk_metrics(data: dict) -> str:
    t = data.get("technicals") or {}
    keys = ("price", "atr14", "atr_pct", "support_20d", "resistance_20d", "support_60d", "resistance_60d",
            "low_52w", "high_52w", "sma50", "sma200", "bb_lower", "bb_upper", "volatility_1m", "volatility_1y",
            "max_drawdown_1y")
    return _json({"currency": data["currency"], **{k: t.get(k) for k in keys}, "position": data.get("position")})


def _abstained(o):
    return f"_Abstained: {o.get('reason', 'no reason given')}_"


def analyst_reports(outputs: dict) -> str:
    parts = []
    for analyst in config.ANALYSTS:
        o = outputs.get(f"analysts/{analyst}")
        title = f"### {analyst.title()} analyst"
        if not o:
            continue
        if o.get("abstained"):
            parts.append(f"{title}\n{_abstained(o)}")
            continue
        parts.append(
            f"{title}: score {o.get('score')}/10, {o.get('stance')}\n"
            f"**Summary**: {o.get('summary')}\n\n{_bullets(o.get('key_points'))}\n\n{o.get('body_md', '')}"
        )
    return "\n\n".join(parts) or NONE


def persona_views(outputs: dict) -> str:
    rows = []
    for stage, o in outputs.items():
        if schemas.kind(stage) != "persona":
            continue
        name = stage.split("/")[1].title()
        if o.get("abstained"):
            rows.append(f"- **{name}**: {_abstained(o)}")
        else:
            rows.append(f"- **{name}**: {o.get('signal')} (confidence {o.get('confidence')}). {o.get('reasoning')}")
    return "\n".join(rows) or NONE


def debate_history(outputs: dict, upto: str | None = None) -> str:
    parts = []
    for stage, o in outputs.items():
        if stage == upto:
            break
        if schemas.kind(stage) != "argument":
            continue
        side, rnd = stage.split("/")[1].split("@")
        body = _abstained(o) if o.get("abstained") else o.get("argument_md", "")
        parts.append(f"**{side.title()} (round {rnd})**\n\n{body}")
    return "\n\n---\n\n".join(parts) or "_The debate has not started yet._"


def opponent_last(stage: str, outputs: dict) -> str:
    side, rnd = stage.split("/")[1].split("@")
    rnd = int(rnd)
    other = f"debate/bear@{rnd - 1}" if side == "bull" else f"debate/bull@{rnd}"
    o = outputs.get(other)
    if not o:
        return "_None yet: this is the opening argument._"
    return _abstained(o) if o.get("abstained") else o.get("argument_md", "")


def research_plan(outputs: dict) -> str:
    o = outputs.get("debate/research_manager")
    if not o:
        return "_No research manager plan at this depth: rely on the analyst reports and composite score._"
    if o.get("abstained"):
        return _abstained(o)
    return f"**Rating: {o.get('rating')}** (winning side: {o.get('winning_side')})\n\n{o.get('summary')}\n\n{o.get('plan_md')}"


def risk_views(outputs: dict) -> str:
    parts = []
    for view in config.RISK_VIEWS:
        o = outputs.get(f"risk/{view}")
        if not o:
            continue
        if o.get("abstained"):
            parts.append(f"**{view.title()}**: {_abstained(o)}")
        else:
            parts.append(f"**{view.title()}** ({o.get('stance')}): {o.get('summary')}\n{_bullets(o.get('recommendations'))}")
    return "\n\n".join(parts) or "_No separate risk review at this depth._"


def composite_block(comp: dict) -> str:
    if comp["score"] is None:
        return "_No analyst scores available._"
    parts = ", ".join(f"{a} {s}/10 x {comp['weights'][a]:.0%}" for a, s in comp["scores"].items())
    missing = f" Missing: {', '.join(comp['missing'])}." if comp["missing"] else ""
    return f"**{comp['score']}/10** ({parts}).{missing}"


def since_last_block(stock: dict, data: dict) -> str:
    prev = stock.get("previous")
    if not prev:
        return "First report for this stock."
    price = prev.get("Price")
    change = f"{_pct(data['price'] / price - 1)}" if price else "n/a"
    return (f"Last report {prev.get('Date')}: rating **{prev.get('Rating')}** ({prev.get('Action')}),"
            f" price then {price}, now {data['price']} ({change}). Summary then: {prev.get('Summary') or 'n/a'}")


def lessons_block(stock: dict, run: RunFolder | None = None) -> str:
    lessons = list(stock.get("lessons") or [])
    if run is not None:  # calls settled during this run, whose lessons were just written
        from .memory import reflection_stage

        for p in stock.get("pending_reflections") or []:
            o = run.output(reflection_stage(p))
            if o and o.get("lesson"):
                lessons.insert(0, {"date": p["date"], "rating": p["rating"], "alpha": p["alpha"],
                                   "outcome": p["outcome"], "lesson": o["lesson"]})
    if not lessons:
        return "_No settled calls yet for this stock._"
    return "\n".join(
        f"- {l['date']} call **{l['rating']}** → alpha {_pct(l.get('alpha'))} ({l.get('outcome')}): {l['lesson']}"
        for l in lessons
    )


# --- fill -------------------------------------------------------------------

def context(run: RunFolder, stage: str) -> dict:
    stock, data = run.stock, run.data
    outputs = run.outputs()
    row = stock["row"]
    ctx = {
        "as_of": data["as_of"],
        "data_as_of": data["data_as_of"],
        "horizon": row["horizon"],
        "bucket": row["bucket"],
        "status": row["status"],
        "risk_tolerance": row["risk_tolerance"],
        "currency": data["currency"],
        "benchmark": (data.get("market_context") or {}).get("benchmark", "the market"),
        "stock": stock_block(stock, data),
        "technicals": technicals_block(data),
        "market_context": _json(data.get("market_context")),
        "fundamentals": fundamentals_block(data),
        "fundamentals_brief": fundamentals_brief(data),
        "price_summary": price_summary(data),
        "street": street_block(data),
        "news": news_block(data),
        "enrichment": enrichment_block(data),
        "risk_metrics": risk_metrics(data),
        "analyst_reports": analyst_reports(outputs),
        "persona_views": persona_views(outputs),
        "debate_history": debate_history(outputs, upto=stage),
        "research_plan": research_plan(outputs),
        "risk_views": risk_views(outputs),
        "composite": composite_block(run.composite()),
        "since_last": since_last_block(stock, data),
        "lessons": lessons_block(stock, run),
        "output_schema": schemas.prompt_text(stage),
    }
    if "@" in stage:
        ctx["round"] = stage.split("@")[1]
        ctx["opponent_last"] = opponent_last(stage, outputs)
    return ctx


def render(text: str, ctx: dict) -> str:
    return _PLACEHOLDER.sub(lambda m: str(ctx.get(m.group(1), f"(no value for {m.group(1)})")), text)


def fill(run: RunFolder, stage: str, extra: dict | None = None) -> tuple[str, str]:
    """(system, user) prompt text for a stage, also saved to the run's prompts/ folder."""
    ctx = {} if stage.startswith("memory/") else context(run, stage)
    ctx.update(extra or {})
    ctx.setdefault("output_schema", schemas.prompt_text(stage))
    system = render((config.PROMPTS_DIR / "system.md").read_text(encoding="utf-8"), ctx)
    user = render(template_path(stage).read_text(encoding="utf-8"), ctx)
    path = run.prompt_path(stage)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"<!-- system prompt: prompts/system.md -->\n{system}\n\n---\n\n{user}\n", encoding="utf-8")
    return system, user
