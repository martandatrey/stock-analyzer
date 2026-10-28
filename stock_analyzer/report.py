"""Render a stock's report.html and a day's index.html.

Pages are self-contained (inline CSS, inline SVG chart, a few lines of JS for
the chart's hover readout) so they open offline and can be emailed as one file.
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown_it import MarkdownIt
from markupsafe import Markup

from . import config, rating, schemas
from .runfolder import RunFolder, file_name

_md = MarkdownIt("commonmark", {"html": False, "linkify": False}).enable("table")


def md(text) -> Markup:
    """Markdown from an LLM output -> HTML. Raw HTML in the text is escaped, never rendered."""
    return Markup(_md.render(str(text or "")))


def num(v, nd=2):
    if v is None:
        return "n/a"
    if isinstance(v, (int, float)):
        if abs(v) >= 1e12:
            return f"{v / 1e12:.2f}T"
        if abs(v) >= 1e9:
            return f"{v / 1e9:.2f}B"
        if abs(v) >= 1e7:
            return f"{v / 1e6:.1f}M"
        return f"{v:,.{nd}f}"
    return str(v)


def pct(v, signed=True):
    if v is None:
        return "n/a"
    return f"{v * 100:+.1f}%" if signed else f"{v * 100:.1f}%"


_env = Environment(loader=FileSystemLoader(config.TEMPLATES_DIR), autoescape=select_autoescape(["html", "j2"]))
_env.filters.update(md=md, num=num, pct=pct, tojson_safe=lambda o: Markup(json.dumps(o).replace("</", "<\\/")))


# --- chart --------------------------------------------------------------------

def _nice_ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    span = hi - lo or abs(hi) or 1
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    start = math.floor(lo / step) * step
    ticks, t = [], start
    while t <= hi + step * 0.001:
        ticks.append(round(t, 10))
        t += step
    return ticks


def price_chart(chart: dict, levels: dict, currency: str) -> dict:
    """Geometry for the price chart (close, SMA50, SMA200 plus target/stop lines) and volume bars."""
    W, H, L, R, T, B = 760, 300, 56, 92, 14, 26
    dates = chart["dates"]
    n = len(dates)
    if n < 2:
        return {}
    series = [("close", "Close", 1), ("sma50", "SMA 50", 2), ("sma200", "SMA 200", 3)]
    values = [v for key, _, _ in series for v in chart[key] if v is not None]
    level_vals = [v for v in levels.values() if isinstance(v, (int, float))]
    lo, hi = min(values + level_vals), max(values + level_vals)
    pad = (hi - lo) * 0.04
    ticks = _nice_ticks(lo - pad, hi + pad)
    y0, y1 = ticks[0], ticks[-1]
    x = lambda i: L + i * (W - L - R) / (n - 1)  # noqa: E731
    y = lambda v: T + (y1 - v) * (H - T - B) / (y1 - y0)  # noqa: E731

    lines = []
    for key, label, slot in series:
        d, pen = [], "M"
        for i, v in enumerate(chart[key]):
            if v is None:
                pen = "M"
                continue
            d.append(f"{pen}{x(i):.1f},{y(v):.1f}")
            pen = "L"
        last = next(((i, v) for i, v in reversed(list(enumerate(chart[key]))) if v is not None), None)
        if d and last:
            lines.append({"key": key, "label": label, "slot": slot, "d": " ".join(d),
                          "end_x": x(last[0]), "end_y": y(last[1]), "end_v": last[1]})
    # End labels: keep at least 14px apart so they never collide.
    prev = None
    for s in sorted(lines, key=lambda s: s["end_y"]):
        s["label_y"] = s["end_y"] if prev is None else max(s["end_y"], prev + 14)
        prev = s["label_y"]

    level_lines = [{"label": name, "value": v, "y": y(v)} for name, v in levels.items() if isinstance(v, (int, float))]

    months, seen = [], set()
    for i, d in enumerate(dates):
        m = d[:7]
        if m not in seen and i > 0:
            seen.add(m)
            if int(d[5:7]) % 2 == 1:
                months.append({"x": x(i), "label": datetime.strptime(d, "%Y-%m-%d").strftime("%b %y")})

    VH = 86
    vmax = max(chart["volume"]) or 1
    step = (W - L - R) / n
    bars = [{"x": L + i * step, "w": max(step - 1, 0.8), "h": (v / vmax) * (VH - 18), "y": VH - (v / vmax) * (VH - 18)}
            for i, v in enumerate(chart["volume"])]
    return {
        "W": W, "H": H, "L": L, "R": R, "T": T, "B": B, "VH": VH,
        "lines": lines, "levels": level_lines, "months": months, "bars": bars, "vmax": vmax,
        "yticks": [{"v": t, "y": y(t), "label": num(t, 0 if (y1 - y0) >= 50 else 2)} for t in ticks],
        "currency": currency,
        "data": {"dates": dates, "close": chart["close"], "sma50": chart["sma50"], "sma200": chart["sma200"],
                 "volume": chart["volume"], "L": L, "R": R, "W": W, "n": n},
    }


# --- report -----------------------------------------------------------------

def _rating_class(r: str | None) -> str:
    return {"Buy": "r-buy", "Overweight": "r-ow", "Hold": "r-hold", "Underweight": "r-uw", "Sell": "r-sell"}.get(
        r or "", "r-review")


def report_context(run: RunFolder, second: dict | None) -> dict:
    stock, data = run.stock, run.data
    row = stock["row"]
    outputs = run.outputs()
    d = outputs.get("final/portfolio_manager") or {}
    final_rating = d.get("rating") if rating.normalize(d.get("rating")) in rating.RATINGS and not d.get("abstained") \
        else rating.REVIEW
    comp = run.composite()
    analysts = [(a, outputs.get(f"analysts/{a}")) for a in config.ANALYSTS]
    personas = [(s.split("/")[1], o) for s, o in outputs.items() if schemas.kind(s) == "persona"]
    debate = [(s.split("/")[1].split("@")[0], int(s.split("@")[1]), o) for s, o in outputs.items()
              if schemas.kind(s) == "argument"]
    risks = [(s.split("/")[1], o) for s, o in outputs.items() if schemas.kind(s) == "risk"]
    reflections = []
    from .memory import reflection_stage

    for p in stock.get("pending_reflections") or []:
        o = run.output(reflection_stage(p)) or {}
        reflections.append({**p, "lesson": o.get("lesson")})

    levels = {}
    if isinstance(d.get("target"), (int, float)):
        levels["Target"] = d["target"]
    if isinstance(d.get("stop"), (int, float)):
        levels["Stop"] = d["stop"]

    prompt_files = sorted(p.name for p in (run.dir / "prompts").glob("*.md"))
    output_files = {p.stem for p in (run.dir / "outputs").glob("*.json")}
    sections = [("decision", "Decision"), ("scores", "Scores"), ("chart", "Price chart")]
    if stock.get("previous") or stock.get("lessons") or reflections:
        sections.append(("memory", "Since last & lessons"))
    sections.append(("analysts", "Analysts"))
    if personas:
        sections.append(("personas", "Investor personas"))
    if debate:
        sections.append(("debate", "Bull vs bear"))
    if risks:
        sections.append(("risk", "Risk review"))
    if second:
        sections.append(("second", "2nd opinion"))
    sections += [("data", "Data"), ("files", "Prompts & outputs")]

    return {
        "stock": stock, "row": row, "data": data, "d": d, "final_rating": final_rating,
        "rating_class": _rating_class(final_rating), "rating_class_of": _rating_class,
        "action": rating.action(final_rating, row["holding"]),
        "comp": comp, "analysts": analysts, "personas": personas, "debate": debate, "risks": risks,
        "plan": outputs.get("debate/research_manager"), "reflections": reflections,
        "chart": price_chart(data["chart"], levels, data["currency"]),
        "second": second, "sections": sections,
        "prompt_files": [(f, f[:-3] in output_files) for f in prompt_files],
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "company": (data.get("company") or {}).get("name") or row.get("company") or row["ticker"],
    }


def render(run: RunFolder, second: dict | None = None) -> Path:
    html = _env.get_template("report.html.j2").render(**report_context(run, second))
    out = run.dir / "report.html"
    out.write_text(html, encoding="utf-8")
    return out


def build_index(run_date: str, root: Path = config.REPORTS_DIR) -> Path:
    """reports/<date>/index.html: every stock reported that day, best rating first."""
    day = Path(root) / run_date
    order = {r: i for i, r in enumerate(rating.RATINGS)}
    rows = []
    for folder in sorted(p for p in day.iterdir() if p.is_dir()):
        run = RunFolder(run_date, folder.name, root)
        if not (folder / "stock.json").exists():
            continue
        stock, data = run.stock, run.data
        row = stock["row"]
        d = run.output("final/portfolio_manager") or {}
        r = d.get("rating") if not d.get("abstained") and d.get("rating") in rating.RATINGS else rating.REVIEW
        done = (folder / "report.html").exists()
        rows.append({
            "key": folder.name, "ticker": row["ticker"], "exchange": row["exchange"],
            "company": (data.get("company") or {}).get("name") or row["ticker"],
            "status": row["status"], "horizon": row["horizon"], "price": data["price"],
            "currency": data["currency"], "data_as_of": data["data_as_of"],
            "change_1d": None, "ret_1m": (data["technicals"].get("returns") or {}).get("1M"),
            "rating": r if done else "Incomplete", "rating_class": _rating_class(r if done else None),
            "action": rating.action(r, row["holding"]) if done else "Run did not finish",
            "confidence": d.get("confidence"), "composite": run.composite()["score"],
            "summary": d.get("summary"), "href": f"{folder.name}/report.html" if done else None,
        })
    rows.sort(key=lambda x: (order.get(x["rating"], 9), -(x["confidence"] or 0)))
    html = _env.get_template("index.html.j2").render(
        run_date=run_date, rows=rows, generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        weekday=date.fromisoformat(run_date).strftime("%A"))
    out = day / "index.html"
    out.write_text(html, encoding="utf-8")
    return out
