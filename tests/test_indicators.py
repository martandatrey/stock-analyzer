import pandas as pd
import pytest

from stock_analyzer import indicators


def test_sma_exact():
    s = pd.Series([1, 2, 3, 4, 5], dtype=float)
    assert indicators.sma(s, 3).tolist()[2:] == [2.0, 3.0, 4.0]


def test_rsi_extremes_and_bounds(prices):
    up = pd.Series(range(1, 60), dtype=float)
    down = pd.Series(range(60, 1, -1), dtype=float)
    assert indicators.rsi(up).iloc[-1] == pytest.approx(100.0)
    assert indicators.rsi(down).iloc[-1] == pytest.approx(0.0)
    r = indicators.rsi(prices["close"]).dropna()
    assert ((r >= 0) & (r <= 100)).all()


def test_summarize_has_core_fields(prices):
    s = indicators.summarize(prices, prices * 0.9)
    for k in ("price", "sma50", "sma200", "rsi14", "atr14", "high_52w", "returns", "relative_strength"):
        assert k in s
    assert s["relative_strength"]["1M"] == pytest.approx(0.0, abs=1e-9)  # same shape as benchmark


def test_forward_return(prices):
    start = prices.index[10]
    ret, end = indicators.forward_return(prices["close"], start, 5)
    assert end == prices.index[15]
    assert ret == pytest.approx(prices["close"].iloc[15] / prices["close"].iloc[10] - 1)
    assert indicators.forward_return(prices["close"], prices.index[-3], 5) is None


def test_quarterly_growth_matches_year_ago_quarter():
    from stock_analyzer.data import quarterly_growth

    rows = [{"period_ending": d, "total_revenue": r, "net_income": n} for d, r, n in [
        ("2026-06-30", 127, 78), ("2026-03-31", 120, 90), ("2025-12-31", 115, 95),
        ("2025-06-30", 100, 100), ("2025-03-31", 98, 70)]]  # 2025-09-30 is missing
    g = quarterly_growth(rows)
    assert g["compared_with"] == "2025-06-30"
    assert g["revenue_yoy"] == pytest.approx(0.27) and g["net_income_yoy"] == pytest.approx(-0.22)
    assert quarterly_growth(rows[:3])["revenue_yoy"] is None  # no year-ago quarter: no guess


def test_quarterly_growth_flags_missing_quarter():
    from stock_analyzer.data import quarterly_growth

    rows = [{"period_ending": d, "total_revenue": 1, "net_income": 1}
            for d in ("2026-06-30", "2026-03-31", "2025-12-31", "2025-06-30")]
    assert quarterly_growth(rows)["missing_between"] == ["2025-06-30 to 2025-12-31"]


def test_enrichment_headings_nest_under_prompt_sections():
    from stock_analyzer.prompts import enrichment_block

    out = enrichment_block({"enrichment": "# Title\n## Section\ntext #not-a-heading"})
    assert out.splitlines() == ["### Title", "#### Section", "text #not-a-heading"]
