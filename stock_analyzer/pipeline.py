"""The per-stock pipeline shared by both front ends.

    prepare()        snapshot + stage list + memory  ->  reports/<date>/<KEY>/{data,stock}.json
    pending_stages() what still needs an output (reflections first, then the analysis stages)
    record()         validate and save one stage's output (or an abstention)
    finalize()       render report.html, then write the Analysis Log / Stocks row / Scorecard

Claude Code drives these through the scripts/ CLIs; run.py calls them directly.
"""

from __future__ import annotations

from datetime import date

from . import config, memory, rating, schemas
from .data import build_snapshot
from .excel_io import Book, StockRow
from .runfolder import RunFolder


class AlreadyReported(Exception):
    """This stock's latest close was already analysed on an earlier run (e.g. a market holiday)."""


def select_rows(book: Book, settings: dict, ticker: str | None = None, market: str | None = None) -> list[StockRow]:
    rows = book.stocks(settings)
    if ticker:
        t = ticker.upper()
        rows = [r for r in rows if r.ticker == t or f"{r.ticker}_{r.exchange}" == t]
        if not rows:
            raise LookupError(f"{ticker} is not in the Stocks sheet")
        return rows  # an explicitly named stock runs even if Analyze? = N
    rows = [r for r in rows if r.analyze]
    if market:
        rows = [r for r in rows if not r.errors and r.market == market.lower()]
    return rows


def prepare(row: StockRow, book: Book, settings: dict, as_of: date, force: bool = False,
            root=config.REPORTS_DIR) -> RunFolder:
    if row.errors:
        raise ValueError(f"Row {row.row} ({row.ticker}): " + "; ".join(row.errors))
    run_date = as_of.isoformat()
    snapshot, df, bench = build_snapshot(row.ticker, row.exchange, as_of, provider=settings["Data Provider"],
                                         position=row.position, return_frames=True)
    history = book.history(row.ticker, row.exchange)
    earlier = [h for h in history if (h.get("Date") or "") < run_date]
    if not force and any(h.get("Data As Of") == snapshot["data_as_of"] for h in earlier):
        raise AlreadyReported(
            f"{row.ticker}: the {snapshot['data_as_of']} close was already analysed on an earlier run "
            "(market holiday?). Pass --force to analyse it again."
        )
    previous = earlier[-1] if earlier else None
    stages = config.stages_for_depth(row.depth, row.bucket, settings["personas"], settings["Debate Rounds"])
    pending = memory.pending_settlements(
        history, df["close"], None if bench is None else bench["close"], settings["settle_days"], run_date)

    run = RunFolder(run_date, row.key, root)
    run.dir.mkdir(parents=True, exist_ok=True)
    for stale in list(run.dir.glob("outputs/*.json")) + list(run.dir.glob("prompts/*.md")):
        stale.unlink()  # re-running a day starts that stock from scratch
    run.save_data(snapshot)
    run.save_stock({
        "run_date": run_date,
        "row": row.as_dict(),
        "depth": row.depth,
        "stages": stages,
        "settings": {k: settings[k] for k in ("Data Provider", "Stage Model", "Decision Model", "Debate Rounds",
                                               "use_kite", "use_web_search")},
        "personas": settings["personas"].get(row.bucket, []),
        "previous": None if previous is None else {k: previous.get(k) for k in (
            "Date", "Data As Of", "Price", "Rating", "Action", "Confidence", "Summary", "Composite")},
        "lessons": memory.lessons(earlier),
        "pending_reflections": pending,
        "second_opinion": row.second_opinion,
    })
    return run


def all_stages(run: RunFolder) -> list[str]:
    stock = run.stock
    return [memory.reflection_stage(p) for p in stock.get("pending_reflections") or []] + stock["stages"]


def pending_stages(run: RunFolder) -> list[str]:
    return [s for s in all_stages(run) if run.output(s) is None]


def fill_prompt(run: RunFolder, stage: str) -> tuple[str, str]:
    from . import prompts

    extra = None
    if stage.startswith("memory/reflection@"):
        p = next(p for p in run.stock["pending_reflections"] if memory.reflection_stage(p) == stage)
        extra = memory.reflection_context(p, run.stock, run.data)
    return prompts.fill(run, stage, extra)


def record(run: RunFolder, stage: str, obj: dict) -> dict:
    if stage not in all_stages(run):
        raise ValueError(f"{stage!r} is not a stage of this run; expected one of {all_stages(run)}")
    obj = schemas.normalize(stage, obj)
    errors = schemas.validate(stage, obj)
    if errors:
        raise ValueError(f"{stage}: " + "; ".join(errors))
    run.save_output(stage, obj)
    return obj


def abstain(run: RunFolder, stage: str, reason: str) -> dict:
    return record(run, stage, {"abstained": True, "reason": reason})


# --- finalize ----------------------------------------------------------------

def decision(run: RunFolder) -> dict:
    o = run.output("final/portfolio_manager") or {}
    if o.get("abstained") or rating.normalize(o.get("rating")) not in rating.RATINGS:
        o = {**o, "rating": rating.REVIEW}
    return o


def log_entry(run: RunFolder, report_href: str, second: dict | None) -> dict:
    stock, data = run.stock, run.data
    row = stock["row"]
    d = decision(run)
    comp = run.composite()
    plan = run.output("debate/research_manager") or {}
    votes = run.persona_votes()
    conf = d.get("confidence")
    return {
        "Date": stock["run_date"], "Ticker": row["ticker"], "Exchange": row["exchange"],
        "Horizon": row["horizon"], "Status": row["status"], "Depth": stock["depth"],
        "Data As Of": data["data_as_of"], "Price": data["price"], "Currency": data["currency"],
        "Technical": comp["scores"].get("technical"), "Fundamental": comp["scores"].get("fundamental"),
        "News": comp["scores"].get("news"), "Sentiment": comp["scores"].get("sentiment"),
        "Composite": comp["score"],
        "Persona Votes": ", ".join(f"{k.title()}: {v['signal']} {v['confidence']}" for k, v in votes.items()) or None,
        "Research Plan": plan.get("rating"),
        "Rating": d["rating"], "Action": rating.action(d["rating"], row["holding"]),
        "Confidence": conf / 100 if isinstance(conf, (int, float)) else None,
        "Summary": d.get("summary"), "Entry Zone": d.get("entry_zone"),
        "Target": d.get("target"), "Stop": d.get("stop"),
        "2nd Opinion": (second or {}).get("rating"), "Report": report_href,
    }


def finalize(run: RunFolder, book_path=config.WORKBOOK) -> dict:
    """Render the report, then record everything in the workbook. Returns a short summary."""
    from . import report, second_opinion

    missing = [s for s in pending_stages(run)]
    if "final/portfolio_manager" in missing:
        abstain(run, "final/portfolio_manager", "No portfolio manager output was produced.")
    second = second_opinion.load(run)
    html_path = report.render(run, second)
    href = html_path.relative_to(config.ROOT).as_posix()
    stock = run.stock
    row = stock["row"]
    d = decision(run)

    book = Book(book_path, write=True)
    for p in stock.get("pending_reflections") or []:
        o = run.output(memory.reflection_stage(p)) or {}
        book.settle(p["log_row"], {
            "Settled On": p["settled_on"], "Return": p["raw_return"], "Benchmark Return": p["benchmark_return"],
            "Alpha": p["alpha"], "Outcome": p["outcome"], "Lesson": o.get("lesson"),
        })
    book.upsert_log(log_entry(run, href, second))
    book.update_stock(
        row["ticker"], row["exchange"],
        **{"Company": (run.data.get("company") or {}).get("name"),
           "Last Analyzed": date.fromisoformat(stock["run_date"]),
           "Last Rating": d["rating"], "Last Action": rating.action(d["rating"], row["holding"]),
           "Last Report": href},
    )
    book.rebuild_scorecard()
    book.save()
    return {"ticker": row["ticker"], "exchange": row["exchange"], "rating": d["rating"],
            "action": rating.action(d["rating"], row["holding"]), "confidence": d.get("confidence"),
            "report": str(html_path), "missing_stages": [s for s in missing if s != "final/portfolio_manager"],
            "second_opinion": (second or {}).get("rating")}
