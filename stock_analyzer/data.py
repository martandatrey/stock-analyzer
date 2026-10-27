"""Market data snapshot for one stock on one date.

Primary source is the OpenBB Open Data Platform (provider from Settings,
yfinance by default); any piece OpenBB can't supply falls back to calling
yfinance directly. Every value that can't be fetched is stored as None and
listed under `data_gaps`, so the prompts can say "unavailable" instead of
guessing.
"""

from __future__ import annotations

import logging
import os
import warnings
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from . import config, indicators

log = logging.getLogger(__name__)
warnings.filterwarnings("ignore")

MARKET_CLOSE = {
    "india": (ZoneInfo("Asia/Kolkata"), time(15, 30)),
    "us": (ZoneInfo("America/New_York"), time(16, 0)),
}

_obb = None


def _openbb(provider: str):
    """Import OpenBB lazily (first import is slow) and set the FMP key if that provider is chosen."""
    global _obb
    if _obb is None:
        from openbb import obb

        _obb = obb
    if provider == "fmp" and os.environ.get("FMP_API_KEY"):
        _obb.user.credentials.fmp_api_key = os.environ["FMP_API_KEY"]
    return _obb


def _dump(result) -> dict:
    first = result[0] if isinstance(result, list) else result
    return first.model_dump(exclude_none=True) if hasattr(first, "model_dump") else dict(first)


def _clean(value):
    """Make a value JSON-safe: NaN/inf -> None, dates -> ISO strings, numpy -> python."""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()[:10] if not isinstance(value, datetime) else value.isoformat()
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
        return None
    return value


# --- Prices ------------------------------------------------------------------

def _prices_openbb(symbol: str, start: date, end: date, provider: str) -> pd.DataFrame:
    obb = _openbb(provider)
    df = obb.equity.price.historical(
        symbol, start_date=start.isoformat(), end_date=end.isoformat(), provider=provider
    ).to_dataframe()
    df.index = pd.to_datetime(df.index)
    return df[["open", "high", "low", "close", "volume"]].astype(float)


def _prices_yf(symbol: str, start: date, end: date) -> pd.DataFrame:
    import yfinance as yf

    df = yf.Ticker(symbol).history(start=start.isoformat(), end=(end + timedelta(days=1)).isoformat(), auto_adjust=False)
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    df = df.rename(columns=str.lower)
    return df[["open", "high", "low", "close", "volume"]].astype(float)


def prices(symbol: str, as_of: date, years: int = 2, provider: str = "yfinance") -> pd.DataFrame:
    start = as_of - timedelta(days=365 * years + 15)
    try:
        df = _prices_openbb(symbol, start, as_of, provider)
    except Exception as exc:  # OpenBB/provider failure -> direct Yahoo
        log.warning("OpenBB prices failed for %s (%s); using yfinance", symbol, exc)
        df = _prices_yf(symbol, start, as_of)
    df = df[df.index.date <= as_of].dropna(subset=["close"])
    if df.empty:
        raise LookupError(f"No price history for {symbol}. Check the ticker and exchange in stocks.xlsx.")
    return df


def drop_unfinished_bar(df: pd.DataFrame, market: str, now: datetime | None = None) -> pd.DataFrame:
    """Remove today's bar while that market is still trading, so 'close' is a real close."""
    tz, close_at = MARKET_CLOSE[market]
    now = (now or datetime.now(tz)).astimezone(tz)
    if df.index[-1].date() == now.date() and now.time() < close_at:
        return df.iloc[:-1]
    return df


# --- Fundamentals, estimates, news --------------------------------------------

def _try(gaps: list, name: str, fn, default=None):
    try:
        return fn()
    except Exception as exc:
        log.info("%s unavailable: %s", name, exc)
        gaps.append(name)
        return default


def _year_ago(quarters: list[dict], i: int) -> dict | None:
    """The quarter ending about a year before quarters[i] (Yahoo sometimes skips a quarter)."""
    end = date.fromisoformat(str(quarters[i]["period_ending"])[:10])
    for q in quarters[i + 1:]:
        if abs((end - date.fromisoformat(str(q["period_ending"])[:10])).days - 365) <= 20:
            return q
    return None


def quarterly_growth(rows: list[dict]) -> dict:
    """Latest quarters plus year-on-year growth against the matching quarter a year earlier.

    Growth is None when that quarter is missing, rather than comparing against the wrong one.
    """
    rows = sorted(rows, key=lambda r: str(r["period_ending"]), reverse=True)
    quarters = [
        {
            "period_ending": str(r["period_ending"])[:10],
            "revenue": r.get("total_revenue"),
            "net_income": r.get("net_income"),
            "operating_income": r.get("operating_income"),
            "diluted_eps": r.get("diluted_earnings_per_share"),
        }
        for r in rows[:5]
    ]
    prior = _year_ago(quarters, 0) if quarters else None

    def yoy(key):
        if prior and quarters[0][key] and prior[key]:
            return quarters[0][key] / prior[key] - 1
        return None

    ends = [date.fromisoformat(q["period_ending"]) for q in quarters]
    skipped = [f"{b.isoformat()} to {a.isoformat()}" for a, b in zip(ends, ends[1:]) if (a - b).days > 100]
    return {
        "quarters": quarters,
        "missing_between": skipped or None,
        "latest_quarter": quarters[0]["period_ending"] if quarters else None,
        "compared_with": prior["period_ending"] if prior else None,
        "revenue_yoy": yoy("revenue"),
        "net_income_yoy": yoy("net_income"),
    }


def _quarterly_growth(obb, symbol: str, provider: str) -> dict:
    rows = obb.equity.fundamental.income(symbol, provider=provider, period="quarter", limit=5).results
    return quarterly_growth([r.model_dump(exclude_none=True) for r in rows])


def clean_fundamentals(metrics: dict, profile: dict, consensus: dict | None) -> tuple[dict, dict, dict | None]:
    """Remove fields that clash with our own computed numbers and make units explicit.

    Yahoo reports `dividend_yield` in percent but `dividend_yield_5y_avg` as a fraction, and its
    `price_return_1y` / consensus `current_price` use a live price that differs from our close.
    """
    metrics = {k: v for k, v in metrics.items() if k not in ("symbol", "currency", "price_return_1y")}
    if "dividend_yield" in metrics:
        metrics["dividend_yield_pct"] = metrics.pop("dividend_yield")
    if "dividend_yield_5y_avg" in metrics:
        v = metrics.pop("dividend_yield_5y_avg")
        metrics["dividend_yield_5y_avg_pct"] = None if v is None else round(v * 100, 3)
    profile = dict(profile)
    if "dividend_yield" in profile:
        profile["dividend_yield_pct"] = profile.pop("dividend_yield")
    if consensus:
        consensus = {k: v for k, v in consensus.items() if k != "current_price"}
    return metrics, profile, consensus


def _recommendations(symbol: str) -> dict | None:
    import yfinance as yf

    rec = yf.Ticker(symbol).recommendations_summary
    if rec is None or rec.empty:
        return None
    row = rec.iloc[0]
    return {k: int(row[k]) for k in ("strongBuy", "buy", "hold", "sell", "strongSell") if k in row}


_SUFFIXES = {"limited", "ltd", "ltd.", "inc", "inc.", "corporation", "corp", "corp.", "plc", "co", "co.", "company"}


def short_name(company: str | None, symbol: str) -> str:
    """'Reliance Industries Limited' -> 'Reliance Industries'; falls back to the bare ticker."""
    if not company:
        return symbol.split(".")[0]
    words = company.replace(",", " ").split()
    while words and words[-1].lower() in _SUFFIXES:
        words.pop()
    return " ".join(words) or company


def _news_yahoo(symbol: str, name: str, lo: float, hi: float) -> list[dict]:
    import yfinance as yf

    bare = symbol.split(".")[0].upper()
    out = []
    for it in yf.Search(name, news_count=25).news or []:
        ts = it.get("providerPublishTime") or 0
        related = [t.upper() for t in it.get("relatedTickers") or []]
        title = it.get("title", "")
        if lo <= ts <= hi and (symbol.upper() in related or bare in related or name.lower() in title.lower()):
            out.append({"ts": ts, "title": title, "publisher": it.get("publisher"), "link": it.get("link")})
    return out


def _news_google(name: str, market: str, start: date, end: date) -> list[dict]:
    import urllib.parse
    import urllib.request
    import xml.etree.ElementTree as ET
    from email.utils import parsedate_to_datetime

    region = {"india": ("en-IN", "IN", "IN:en"), "us": ("en-US", "US", "US:en")}[market]
    q = f'"{name}" after:{start.isoformat()} before:{(end + timedelta(days=1)).isoformat()}'
    url = (f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}"
           f"&hl={region[0]}&gl={region[1]}&ceid={region[2]}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (stock-analyzer)"})
    root = ET.fromstring(urllib.request.urlopen(req, timeout=20).read())
    out = []
    for it in root.findall("./channel/item"):
        title = it.findtext("title") or ""
        source = it.findtext("source")
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3]
        out.append({
            "ts": parsedate_to_datetime(it.findtext("pubDate")).timestamp(),
            "title": title, "publisher": source, "link": it.findtext("link"),
        })
    return out


def news(symbol: str, company: str | None, market: str, as_of: date, days: int = 14, limit: int = 12) -> list[dict]:
    """Recent headlines (Yahoo search + Google News RSS), published on or before as_of."""
    name = short_name(company, symbol)
    start = as_of - timedelta(days=days)
    lo = datetime.combine(start, time.min).timestamp()
    hi = datetime.combine(as_of, time.max).timestamp()
    items: list[dict] = []
    for fetch in (lambda: _news_yahoo(symbol, name, lo, hi), lambda: _news_google(name, market, start, as_of)):
        try:
            items += fetch()
        except Exception as exc:
            log.info("news source failed for %s: %s", symbol, exc)
    seen, out = set(), []
    for it in sorted(items, key=lambda i: i["ts"], reverse=True):
        key = it["title"].lower()[:80]
        if key in seen or not (lo <= it["ts"] <= hi):
            continue
        seen.add(key)
        out.append({"date": datetime.fromtimestamp(it["ts"]).strftime("%Y-%m-%d"), "title": it["title"],
                    "publisher": it["publisher"], "link": it["link"]})
    return out[:limit]


# --- Snapshot -------------------------------------------------------------------

def build_snapshot(
    ticker: str,
    exchange_code: str,
    as_of: date,
    provider: str = "yfinance",
    position: dict | None = None,
    now: datetime | None = None,
    return_frames: bool = False,
):
    """Everything the prompts need about one stock, as plain JSON-safe data.

    With `return_frames=True` also returns the stock and benchmark price frames
    (used to settle past calls without fetching twice).
    """
    ex = config.exchange(exchange_code)
    symbol = config.yahoo_symbol(ticker, exchange_code)
    gaps: list[str] = []

    df = drop_unfinished_bar(prices(symbol, as_of, provider=provider), ex.market, now)
    bench = _try(gaps, "benchmark", lambda: prices(ex.benchmark, as_of, provider=provider))
    if bench is not None:
        bench = bench[bench.index <= df.index[-1]]
    vix = _try(gaps, "volatility_index", lambda: prices(ex.volatility_index, as_of, years=1, provider=provider))

    obb = _try(gaps, "openbb", lambda: _openbb(provider))
    profile = _try(gaps, "profile", lambda: _dump(obb.equity.profile(symbol, provider=provider).results), {}) if obb else {}
    metrics = _try(gaps, "metrics", lambda: _dump(obb.equity.fundamental.metrics(symbol, provider=provider).results), {}) if obb else {}
    consensus = _try(gaps, "analyst_consensus", lambda: _dump(obb.equity.estimates.consensus(symbol, provider=provider).results)) if obb else None
    growth = _try(gaps, "quarterly_results", lambda: _quarterly_growth(obb, symbol, provider)) if obb else None
    recs = _try(gaps, "analyst_recommendations", lambda: _recommendations(symbol))
    company = profile.get("name")
    headlines = _try(gaps, "news", lambda: news(symbol, company, ex.market, as_of), [])
    if not headlines and "news" not in gaps:
        gaps.append("news")
    if growth and growth.get("missing_between"):
        gaps.append("quarterly_results: a quarter is missing between " + "; ".join(growth["missing_between"]))

    tech = indicators.summarize(df, bench)
    price = tech["price"]
    market_context = {
        "benchmark": ex.benchmark_name,
        "benchmark_returns": tech.get("benchmark_returns"),
        "volatility_index": ex.volatility_index,
        "volatility_index_level": None if vix is None else round(float(vix["close"].iloc[-1]), 2),
        "volatility_index_1m_change": None if vix is None or len(vix) < 22
        else round(float(vix["close"].iloc[-1] / vix["close"].iloc[-22] - 1), 4),
    }
    if bench is not None and len(bench) >= 200:
        b = bench["close"]
        market_context["benchmark_above_sma200"] = bool(b.iloc[-1] > b.rolling(200).mean().iloc[-1])

    pos = None
    if position and position.get("qty") and position.get("avg_price"):
        qty, avg = float(position["qty"]), float(position["avg_price"])
        pos = {
            "qty": qty,
            "avg_price": avg,
            "buy_date": position.get("buy_date"),
            "market_value": round(qty * price, 2),
            "unrealized_pnl": round(qty * (price - avg), 2),
            "unrealized_pnl_pct": round(price / avg - 1, 4),
        }

    keep_profile = ("name", "sector", "industry_category", "hq_country", "employees", "market_cap", "beta",
                    "dividend_yield", "currency", "long_description")
    metrics, profile, consensus = clean_fundamentals(metrics, profile, consensus)
    profile = {k: profile[k] for k in keep_profile if k in profile}
    if "long_description" in profile:
        profile["long_description"] = profile["long_description"][:700]

    snapshot = _clean({
        "ticker": ticker.upper(),
        "exchange": ex.code,
        "market": ex.market,
        "symbol": symbol,
        "currency": profile.get("currency") or ex.currency,
        "as_of": as_of.isoformat(),
        "data_as_of": df.index[-1].strftime("%Y-%m-%d"),
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "provider": provider,
        "company": profile,
        "price": price,
        "technicals": tech,
        "fundamentals": metrics,
        "quarterly_results": growth,
        "analyst_consensus": consensus,
        "analyst_recommendations": recs,
        "news": headlines,
        "market_context": market_context,
        "position": pos,
        "chart": indicators.chart_series(df),
        "data_gaps": gaps,
        "notes": [
            "Fundamentals and analyst data are the latest available at fetch time, not point-in-time.",
        ],
    })
    return (snapshot, df, bench) if return_frames else snapshot


def benchmark_close(exchange_code: str, as_of: date, years: int = 2) -> pd.Series:
    return prices(config.exchange(exchange_code).benchmark, as_of, years=years)["close"]
