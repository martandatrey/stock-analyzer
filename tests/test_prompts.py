import re

import pytest

from conftest import make_prices
from stock_analyzer import config, indicators, memory, pipeline, prompts
from stock_analyzer.runfolder import RunFolder


@pytest.fixture
def run(tmp_path):
    df = make_prices()
    tech = indicators.summarize(df, df * 0.95)
    r = RunFolder("2026-10-27", "TEST_NSE", tmp_path)
    r.save_data({
        "ticker": "TEST", "exchange": "NSE", "market": "india", "symbol": "TEST.NS", "currency": "INR",
        "as_of": "2026-10-27", "data_as_of": "2026-10-26", "price": tech["price"], "technicals": tech,
        "company": {"name": "Test Industries", "sector": "Energy"}, "fundamentals": {"pe_ratio": 20.0},
        "quarterly_results": None, "analyst_consensus": None, "analyst_recommendations": None,
        "news": [{"date": "2026-10-25", "title": "Test wins order", "publisher": "Wire", "link": None}],
        "market_context": {"benchmark": "NIFTY 50"}, "position": None, "chart": indicators.chart_series(df),
        "data_gaps": [], "notes": [], "provider": "yfinance", "fetched_at": "2026-10-27T10:00:00",
    })
    stages = config.stages_for_depth("Deep", "long", config.DEFAULT_PERSONAS, 2)
    pending = [{"log_row": 2, "date": "2026-09-01", "rating": "Buy", "confidence": 0.7, "summary": "s",
                "horizon": "1 Year", "bucket": "long", "settle_days": 20, "settled_on": "2026-09-29",
                "raw_return": 0.05, "benchmark_return": 0.01, "alpha": 0.04, "outcome": "Right"}]
    r.save_stock({"run_date": "2026-10-27", "depth": "Deep", "stages": stages, "personas": [], "settings": {},
                  "row": {"ticker": "TEST", "exchange": "NSE", "status": "Holding", "horizon": "1 Year",
                          "bucket": "long", "risk_tolerance": "Med", "holding": True, "notes": "my thesis",
                          "target_return": 10.0},
                  "previous": None, "lessons": [], "pending_reflections": pending, "second_opinion": False})
    return r


def test_every_stage_fills_without_unknown_placeholders(run):
    for stage in pipeline.all_stages(run):
        system, user = pipeline.fill_prompt(run, stage)
        leftovers = re.findall(r"\{\{.*?\}\}|\(no value for \w+\)", system + user)
        assert not leftovers, f"{stage}: {leftovers}"
        assert run.prompt_path(stage).exists()


def test_fresh_lesson_reaches_portfolio_manager(run):
    stage = memory.reflection_stage(run.stock["pending_reflections"][0])
    pipeline.record(run, stage, {"lesson": "Momentum kept working; trust the trend."})
    _, user = pipeline.fill_prompt(run, "final/portfolio_manager")
    assert "trust the trend" in user


def test_record_rejects_bad_output(run):
    with pytest.raises(ValueError):
        pipeline.record(run, "analysts/technical", {"score": 5})
    pipeline.abstain(run, "analysts/technical", "no data")
    assert "analysts/technical" not in pipeline.pending_stages(run)
