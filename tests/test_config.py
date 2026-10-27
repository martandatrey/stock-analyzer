import pytest

from stock_analyzer import config


def test_yahoo_symbols():
    assert config.yahoo_symbol("reliance", "NSE") == "RELIANCE.NS"
    assert config.yahoo_symbol("RELIANCE.NS", "NSE") == "RELIANCE.NS"
    assert config.yahoo_symbol("500325", "BSE") == "500325.BO"
    assert config.yahoo_symbol("aapl", "NASDAQ") == "AAPL"
    with pytest.raises(ValueError):
        config.exchange("LSE")


@pytest.mark.parametrize("horizon,bucket", [("2 Weeks", "short"), ("1 Month", "short"), ("3 Months", "medium"),
                                            ("6 Months", "medium"), ("1 Year", "long"), ("5+ Years", "long")])
def test_horizon_bucket(horizon, bucket):
    assert config.horizon_bucket(horizon) == bucket


def test_weights_sum_to_one():
    for w in config.WEIGHTS.values():
        assert sum(w.values()) == pytest.approx(1.0)
        assert set(w) == set(config.ANALYSTS)


def test_stages_by_depth():
    p = config.DEFAULT_PERSONAS
    quick = config.stages_for_depth("Quick", "long", p, 1)
    std = config.stages_for_depth("Standard", "long", p, 3)
    deep = config.stages_for_depth("Deep", "short", p, 1)
    assert quick == [f"analysts/{a}" for a in config.ANALYSTS] + ["final/portfolio_manager"]
    assert "debate/bull@1" in std and "debate/bull@2" not in std and "personas/buffett" in std
    assert "debate/bear@2" in deep and "risk/neutral" in deep and deep[-1] == "final/portfolio_manager"
