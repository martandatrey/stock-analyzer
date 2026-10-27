import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from conftest import make_prices
from create_workbook import build
from stock_analyzer import memory
from stock_analyzer.excel_io import Book, WorkbookOpenError, lock_file


@pytest.fixture
def wb(tmp_path):
    return build(tmp_path / "stocks.xlsx")


def entry(day, rating="Overweight", price=100.0):
    return {"Date": day, "Ticker": "AAPL", "Exchange": "NASDAQ", "Horizon": "3 Months", "Status": "Watchlist",
            "Data As Of": day, "Price": price, "Rating": rating, "Action": "Accumulate", "Confidence": 0.6,
            "Summary": "test call"}


def test_examples_and_settings(wb):
    b = Book(wb)
    rows = b.stocks()
    assert [r.key for r in rows] == ["RELIANCE_NSE", "AAPL_NASDAQ"]
    assert rows[0].position == {"qty": 50.0, "avg_price": 1250.0, "buy_date": "2025-11-03"}
    assert rows[1].bucket == "medium" and not rows[1].errors
    s = b.settings()
    assert s["personas"]["long"][0] == "buffett" and s["settle_days"]["medium"] == 20


def test_log_upsert_replaces_same_day(wb):
    b = Book(wb, write=True)
    b.upsert_log(entry("2026-10-01"))
    b.upsert_log(entry("2026-10-01", rating="Hold"))
    b.upsert_log(entry("2026-10-02"))
    b.save()
    hist = Book(wb).history("AAPL", "NASDAQ")
    assert [(h["Date"], h["Rating"]) for h in hist] == [("2026-10-01", "Hold"), ("2026-10-02", "Overweight")]


def test_refuses_to_write_while_open(wb):
    lock_file(wb).write_text("")
    with pytest.raises(WorkbookOpenError):
        Book(wb, write=True)


def test_settlement_and_scorecard(wb):
    prices = make_prices(n=120, drift=0.004, start_date="2026-05-01")
    bench = make_prices(n=120, drift=0.0, seed=2, start_date="2026-05-01")
    call_day = prices.index[10].strftime("%Y-%m-%d")
    b = Book(wb, write=True)
    b.upsert_log(entry(call_day))
    b.save()
    b = Book(wb, write=True)
    pending = memory.pending_settlements(b.history("AAPL", "NASDAQ"), prices["close"], bench["close"],
                                         {"short": 5, "medium": 20, "long": 60}, "2026-10-27")
    assert len(pending) == 1
    p = pending[0]
    assert p["settle_days"] == 20 and p["outcome"] == ("Right" if p["alpha"] > 0 else "Wrong")
    b.settle(p["log_row"], {"Settled On": p["settled_on"], "Return": p["raw_return"], "Alpha": p["alpha"],
                            "Outcome": p["outcome"], "Lesson": "Trend calls held up."})
    b.rebuild_scorecard()
    b.save()
    b = Book(wb)
    assert memory.lessons(b.history("AAPL", "NASDAQ"))[0]["lesson"] == "Trend calls held up."
    assert b.wb["Scorecard"]["A1"].value.startswith("Scorecard: 1 settled")
    # once settled, it is not pending again
    assert memory.pending_settlements(b.history("AAPL", "NASDAQ"), prices["close"], bench["close"],
                                      {"short": 5, "medium": 20, "long": 60}, "2026-10-27") == []
