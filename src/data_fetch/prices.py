"""
Price history fetching using yfinance (free, reliable for NSE/BSE).
"""

import yfinance as yf
import pandas as pd
from typing import Optional


# Yahoo BSE numeric codes when SYMBOL.BO is thin / missing
BSE_YAHOO_CODE = {
    "NIYOGIN": "538772.BO",
    "SUBAM": "544267.BO",
}


def _normalize_ohlcv(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    try:
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.columns = ["open", "high", "low", "close", "volume"]
    except Exception:
        rename = {}
        for c in df.columns:
            cl = str(c).lower()
            if cl in ("open", "high", "low", "close", "volume") or cl.startswith("adj"):
                rename[c] = "close" if "close" in cl else cl
        df = df.rename(columns=rename)
        keep = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
        df = df[keep].copy()
    if "close" not in df.columns:
        return None
    df = df.dropna(subset=["close"])
    if df.empty or len(df) < 5:
        return None
    return df


def fetch_price_history(
    symbol: str,
    period: str = "2y",
    interval: str = "1d",
) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV for Yahoo symbol (e.g. RELIANCE.NS).
    If SYMBOL.NS fails, try SYMBOL.BO and known BSE numeric codes.
    """
    candidates = [symbol]
    if symbol.endswith(".NS"):
        bare = symbol[:-3]
        candidates.append(bare + ".BO")
        if bare in BSE_YAHOO_CODE:
            candidates.append(BSE_YAHOO_CODE[bare])
    elif symbol.endswith(".BO"):
        pass
    elif "." not in symbol:
        candidates = [symbol + ".NS", symbol + ".BO"]
        if symbol in BSE_YAHOO_CODE:
            candidates.append(BSE_YAHOO_CODE[symbol])

    seen = set()
    for yahoo in candidates:
        if yahoo in seen:
            continue
        seen.add(yahoo)
        try:
            ticker = yf.Ticker(yahoo)
            df = ticker.history(period=period, interval=interval, auto_adjust=True)
            if df is None or df.empty:
                df = yf.download(
                    yahoo, period=period, interval=interval, progress=False, auto_adjust=True
                )
            out = _normalize_ohlcv(df)
            if out is not None:
                return out
        except Exception:
            continue
    return None


def fetch_multiple_prices(symbols: list, period: str = "2y") -> dict:
    """Fetch price history for multiple symbols. Returns {symbol: df}."""
    result = {}
    for sym in symbols:
        df = fetch_price_history(sym, period=period)
        if df is not None and not df.empty:
            result[sym] = df
    return result
