"""The 5-tier rating scale, what each rating means for a position, and how calls are scored.

Scale and the REVIEW rule follow TradingAgents (Apache-2.0): a decision whose
rating can't be read is REVIEW, never a silent Hold.
"""

from __future__ import annotations

import re
import unicodedata

RATINGS = ("Buy", "Overweight", "Hold", "Underweight", "Sell")
REVIEW = "REVIEW"

_SYNONYMS = {
    "buy": "Buy", "strong buy": "Buy",
    "overweight": "Overweight", "outperform": "Overweight", "accumulate": "Overweight", "add": "Overweight",
    "hold": "Hold", "neutral": "Hold", "market perform": "Hold",
    "underweight": "Underweight", "underperform": "Underweight", "reduce": "Underweight", "trim": "Underweight",
    "sell": "Sell", "strong sell": "Sell", "exit": "Sell",
}

ACTIONS = {
    "holding": {"Buy": "Add", "Overweight": "Add on dips", "Hold": "Hold", "Underweight": "Trim", "Sell": "Exit"},
    "watchlist": {"Buy": "Buy", "Overweight": "Accumulate", "Hold": "Wait", "Underweight": "Avoid", "Sell": "Avoid"},
}

# How close to the benchmark a Hold must stay to count as right, per horizon bucket.
HOLD_BAND = {"short": 0.02, "medium": 0.05, "long": 0.08}


def normalize(value) -> str | None:
    """Map free text to a canonical rating, or None if it isn't one."""
    if value is None:
        return None
    key = re.sub(r"[^a-z ]", "", unicodedata.normalize("NFKC", str(value)).lower()).strip()
    if key == "review":
        return REVIEW
    return _SYNONYMS.get(key)


def action(rating: str | None, holding: bool) -> str:
    if rating not in RATINGS:
        return "Review manually"
    return ACTIONS["holding" if holding else "watchlist"][rating]


def direction(rating: str | None) -> int:
    return {"Buy": 1, "Overweight": 1, "Hold": 0, "Underweight": -1, "Sell": -1}.get(rating or "", 0)


def outcome(rating: str | None, alpha: float, bucket: str) -> str:
    """Right / Wrong for a settled call; 'n/a' for REVIEW."""
    if rating not in RATINGS:
        return "n/a"
    d = direction(rating)
    if d == 0:
        return "Right" if abs(alpha) <= HOLD_BAND.get(bucket, 0.05) else "Wrong"
    return "Right" if alpha * d > 0 else "Wrong"


_LABEL_RE = re.compile(
    r"(?im)^[\s>*_#\-]*(?:final\s+|overall\s+|our\s+)?(?:rating|decision|recommendation)\**\s*[:\-–—]\s*\**\s*([A-Za-z ]+?)\**\s*$"
)


def extract_rating(text: str) -> str:
    """Read a 'Rating: X' style label from free text (used for TradingAgents' report).

    All labels found must agree; otherwise the result is REVIEW.
    """
    found = {normalize(m.group(1)) for m in _LABEL_RE.finditer(text or "")}
    found.discard(None)
    found.discard(REVIEW)
    return found.pop() if len(found) == 1 else REVIEW
