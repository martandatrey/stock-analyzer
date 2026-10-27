"""Technical indicators computed with pandas only.

All numbers the analysis quotes come from here, never from the LLM. Inputs are
daily OHLCV frames indexed by date with lower-case columns
(open, high, low, close, volume).
"""

from __future__ import annotations

import math

import pandas as pd

TRADING_DAYS = 252
RETURN_WINDOWS = {"1W": 5, "1M": 21, "3M": 63, "6M": 126, "1Y": 252}


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """Wilder's RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = gain / loss
    out = 100 - 100 / (1 + rs)
    # No losses at all means maximum strength; no gains at all means minimum.
    out = out.where(loss != 0, 100.0)
    out = out.where(~((gain == 0) & (loss == 0)), 50.0)
    return out.where(gain.notna())


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    prev_close = df["close"].shift()
    tr = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    mid = sma(close, n)
    sd = close.rolling(n, min_periods=n).std(ddof=0)
    return pd.DataFrame({"mid": mid, "upper": mid + k * sd, "lower": mid - k * sd})


def period_return(close: pd.Series, days: int) -> float | None:
    if len(close) <= days:
        return None
    return float(close.iloc[-1] / close.iloc[-1 - days] - 1)


def max_drawdown(close: pd.Series) -> float | None:
    if close.empty:
        return None
    return float((close / close.cummax() - 1).min())


def annualized_vol(close: pd.Series, days: int) -> float | None:
    r = close.pct_change().dropna().tail(days)
    if len(r) < max(5, days // 2):
        return None
    return float(r.std(ddof=1) * math.sqrt(TRADING_DAYS))


def _last(s: pd.Series) -> float | None:
    s = s.dropna()
    return None if s.empty else float(s.iloc[-1])


def _round(v, nd=4):
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return None
    return round(float(v), nd)


def summarize(df: pd.DataFrame, bench: pd.DataFrame | None = None) -> dict:
    """Latest indicator values plus trend flags, ready for a prompt."""
    close = df["close"]
    price = float(close.iloc[-1])
    year = df.tail(TRADING_DAYS)

    m = macd(close)
    bb = bollinger(close)
    s20, s50, s200 = sma(close, 20), sma(close, 50), sma(close, 200)
    atr14 = _last(atr(df))
    vol20 = df["volume"].tail(20).mean()

    out = {
        "price": _round(price, 2),
        "sma20": _round(_last(s20), 2),
        "sma50": _round(_last(s50), 2),
        "sma200": _round(_last(s200), 2),
        "ema20": _round(_last(ema(close, 20)), 2),
        "rsi14": _round(_last(rsi(close)), 1),
        "macd": _round(_last(m["macd"]), 3),
        "macd_signal": _round(_last(m["signal"]), 3),
        "macd_hist": _round(_last(m["hist"]), 3),
        "atr14": _round(atr14, 2),
        "atr_pct": _round(atr14 / price if atr14 else None),
        "bb_upper": _round(_last(bb["upper"]), 2),
        "bb_lower": _round(_last(bb["lower"]), 2),
        "high_52w": _round(year["high"].max(), 2),
        "low_52w": _round(year["low"].min(), 2),
        "pct_from_52w_high": _round(price / year["high"].max() - 1),
        "pct_from_52w_low": _round(price / year["low"].min() - 1),
        "support_20d": _round(df["low"].tail(20).min(), 2),
        "resistance_20d": _round(df["high"].tail(20).max(), 2),
        "support_60d": _round(df["low"].tail(60).min(), 2),
        "resistance_60d": _round(df["high"].tail(60).max(), 2),
        "volume_vs_20d_avg": _round(df["volume"].iloc[-1] / vol20 if vol20 else None, 2),
        "volatility_1m": _round(annualized_vol(close, 21)),
        "volatility_1y": _round(annualized_vol(close, TRADING_DAYS)),
        "max_drawdown_1y": _round(max_drawdown(year["close"])),
        "returns": {k: _round(period_return(close, n)) for k, n in RETURN_WINDOWS.items()},
    }
    sma50_v, sma200_v = out["sma50"], out["sma200"]
    out["trend"] = {
        "above_sma50": None if sma50_v is None else price > sma50_v,
        "above_sma200": None if sma200_v is None else price > sma200_v,
        "sma50_above_sma200": None if None in (sma50_v, sma200_v) else sma50_v > sma200_v,
        "macd_above_signal": None if out["macd_hist"] is None else out["macd_hist"] > 0,
    }
    if bench is not None and not bench.empty:
        b = bench["close"]
        out["benchmark_returns"] = {k: _round(period_return(b, n)) for k, n in RETURN_WINDOWS.items()}
        out["relative_strength"] = {
            k: _round(out["returns"][k] - out["benchmark_returns"][k])
            if out["returns"][k] is not None and out["benchmark_returns"][k] is not None
            else None
            for k in RETURN_WINDOWS
        }
    return out


def chart_series(df: pd.DataFrame, days: int = TRADING_DAYS) -> dict:
    """Last `days` sessions of close, SMA50, SMA200 and volume for the report chart."""
    close = df["close"]
    frame = pd.DataFrame({
        "close": close, "sma50": sma(close, 50), "sma200": sma(close, 200), "volume": df["volume"],
    }).tail(days)
    clean = lambda s: [None if pd.isna(v) else round(float(v), 4) for v in s]  # noqa: E731
    return {
        "dates": [d.strftime("%Y-%m-%d") for d in frame.index],
        "close": clean(frame["close"]),
        "sma50": clean(frame["sma50"]),
        "sma200": clean(frame["sma200"]),
        "volume": [0 if pd.isna(v) else int(v) for v in frame["volume"]],
    }


def forward_return(close: pd.Series, start: pd.Timestamp, days: int) -> tuple[float, pd.Timestamp] | None:
    """Return from the first close on/after `start` to `days` sessions later, if that much history exists."""
    after = close[close.index >= start]
    if len(after) <= days:
        return None
    return float(after.iloc[days] / after.iloc[0] - 1), after.index[days]

