from stock_analyzer import rating, schemas


def test_normalize_and_actions():
    assert rating.normalize("strong buy") == "Buy"
    assert rating.normalize("**Overweight**") == "Overweight"
    assert rating.normalize("Underperform") == "Underweight"
    assert rating.normalize("maybe") is None
    assert rating.action("Overweight", holding=True) == "Add on dips"
    assert rating.action("Overweight", holding=False) == "Accumulate"
    assert rating.action("REVIEW", holding=True) == "Review manually"


def test_outcome():
    assert rating.outcome("Buy", 0.03, "medium") == "Right"
    assert rating.outcome("Sell", 0.03, "medium") == "Wrong"
    assert rating.outcome("Hold", 0.01, "short") == "Right"
    assert rating.outcome("Hold", 0.09, "long") == "Wrong"
    assert rating.outcome("REVIEW", 0.5, "long") == "n/a"


def test_extract_rating_needs_agreement():
    assert rating.extract_rating("## Decision\n**Rating**: Overweight\nmore text") == "Overweight"
    assert rating.extract_rating("Rating: Buy\n...\nFinal rating: Sell") == "REVIEW"
    assert rating.extract_rating("no label here, but we like it") == "REVIEW"


def test_schema_normalize_and_validate():
    out = schemas.normalize("final/portfolio_manager", {
        "rating": "strong buy", "confidence": 140, "summary": "s", "entry_zone": "1-2", "target": "1,250",
        "stop": None, "what_changes_view": ["x"], "since_last": "First report", "body_md": "b"})
    assert out["rating"] == "Buy" and out["confidence"] == 100 and out["target"] == 1250.0
    assert schemas.validate("final/portfolio_manager", out) == []
    assert schemas.validate("analysts/technical", {"score": 5}) != []
    assert schemas.validate("analysts/technical", {"abstained": True, "reason": "no data"}) == []
