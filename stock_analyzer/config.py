"""Static configuration: paths, exchanges, horizons, weights and personas.

Everything a user may want to tune day to day lives in the Settings sheet of
stocks.xlsx; this module holds the defaults and the fixed mappings.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "stocks.xlsx"
TEMPLATE_WORKBOOK = ROOT / "templates" / "stocks.template.xlsx"
PROMPTS_DIR = ROOT / "prompts"
TEMPLATES_DIR = ROOT / "templates"
REPORTS_DIR = ROOT / "reports"
CACHE_DIR = ROOT / ".cache"
IS_WINDOWS = sys.platform == "win32"


def venv_python(venv: str = ".venv") -> Path:
    """The Python inside one of the project's virtualenvs: bin/python on macOS/Linux, Scripts\\python.exe on Windows."""
    return ROOT / venv / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")


@dataclass(frozen=True)
class Exchange:
    code: str
    market: str  # "india" | "us"
    yahoo_suffix: str
    benchmark: str
    benchmark_name: str
    volatility_index: str
    currency: str


EXCHANGES: dict[str, Exchange] = {
    "NSE": Exchange("NSE", "india", ".NS", "^NSEI", "NIFTY 50", "^INDIAVIX", "INR"),
    "BSE": Exchange("BSE", "india", ".BO", "^BSESN", "SENSEX", "^INDIAVIX", "INR"),
    "NASDAQ": Exchange("NASDAQ", "us", "", "^GSPC", "S&P 500", "^VIX", "USD"),
    "NYSE": Exchange("NYSE", "us", "", "^GSPC", "S&P 500", "^VIX", "USD"),
}


def exchange(code: str) -> Exchange:
    try:
        return EXCHANGES[code.strip().upper()]
    except KeyError:
        raise ValueError(f"Unknown exchange {code!r}; use one of {', '.join(EXCHANGES)}") from None


def yahoo_symbol(ticker: str, exchange_code: str) -> str:
    """RELIANCE + NSE -> RELIANCE.NS; AAPL + NASDAQ -> AAPL. Already-suffixed tickers pass through."""
    ticker = ticker.strip().upper()
    suffix = exchange(exchange_code).yahoo_suffix
    if not suffix or ticker.endswith(suffix):
        return ticker
    return ticker + suffix


def stock_key(ticker: str, exchange_code: str) -> str:
    """Folder name for one stock inside a day's report folder, e.g. RELIANCE_NSE."""
    return f"{ticker.strip().upper()}_{exchange_code.strip().upper()}"


# --- Investment horizon -------------------------------------------------------

HORIZONS = ["2 Weeks", "1 Month", "3 Months", "6 Months", "1 Year", "3 Years", "5+ Years"]

HORIZON_DAYS = {
    "2 Weeks": 14, "1 Month": 30, "3 Months": 91, "6 Months": 182,
    "1 Year": 365, "3 Years": 1095, "5+ Years": 1825,
}


def horizon_bucket(horizon: str) -> str:
    """short (<= 1 month), medium (3-6 months) or long (>= 1 year)."""
    days = HORIZON_DAYS.get((horizon or "").strip())
    if days is None:
        raise ValueError(f"Unknown investment horizon {horizon!r}; use one of {', '.join(HORIZONS)}")
    if days <= 30:
        return "short"
    if days < 365:
        return "medium"
    return "long"


# How much each analyst's score counts toward the composite, per bucket.
WEIGHTS = {
    "short": {"technical": 0.45, "sentiment": 0.25, "news": 0.20, "fundamental": 0.10},
    "medium": {"technical": 0.30, "fundamental": 0.30, "news": 0.20, "sentiment": 0.20},
    "long": {"fundamental": 0.50, "news": 0.20, "technical": 0.15, "sentiment": 0.15},
}

DEFAULT_PERSONAS = {
    "short": ["druckenmiller"],
    "medium": ["lynch", "druckenmiller", "munger"],
    "long": ["buffett", "munger", "graham", "lynch"],
}

# Trading days after which a call is settled against what the price actually did.
DEFAULT_SETTLE_DAYS = {"short": 5, "medium": 20, "long": 60}

ANALYSTS = ["technical", "fundamental", "news", "sentiment"]
RISK_VIEWS = ["aggressive", "conservative", "neutral"]
DEPTHS = ["Quick", "Standard", "Deep"]

DEFAULT_SETTINGS = {
    "Data Provider": "yfinance",
    "Stage Model": "claude-sonnet-5-5",
    "Decision Model": "claude-opus-5-5",
    "Default Depth": "Standard",
    "Debate Rounds": 1,
    "Personas (short)": ", ".join(DEFAULT_PERSONAS["short"]),
    "Personas (medium)": ", ".join(DEFAULT_PERSONAS["medium"]),
    "Personas (long)": ", ".join(DEFAULT_PERSONAS["long"]),
    "Settle Days (short)": DEFAULT_SETTLE_DAYS["short"],
    "Settle Days (medium)": DEFAULT_SETTLE_DAYS["medium"],
    "Settle Days (long)": DEFAULT_SETTLE_DAYS["long"],
    "Use Kite": "Y",
    "Use Web Search": "Y",
    "TradingAgents Quick Model": "claude-sonnet-5-5",
    "TradingAgents Deep Model": "claude-opus-5-5",
}


def stages_for_depth(depth: str, bucket: str, personas: dict[str, list[str]], debate_rounds: int) -> list[str]:
    """The ordered stage names one stock goes through at a given depth.

    Stage names double as prompt paths (prompts/<stage>.md) and output names.
    """
    depth = (depth or "Standard").strip().title()
    stages = [f"analysts/{a}" for a in ANALYSTS]
    if depth in ("Standard", "Deep"):
        stages += [f"personas/{p}" for p in personas.get(bucket, [])]
        rounds = max(1, debate_rounds if depth == "Deep" else 1)
        if depth == "Deep":
            rounds = max(rounds, 2)
        for r in range(1, rounds + 1):
            stages += [f"debate/bull@{r}", f"debate/bear@{r}"]
        stages.append("debate/research_manager")
    if depth == "Deep":
        stages += [f"risk/{v}" for v in RISK_VIEWS]
    stages.append("final/portfolio_manager")
    return stages
