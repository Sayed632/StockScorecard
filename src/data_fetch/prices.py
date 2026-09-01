"""
Price history fetching using yfinance (free, reliable for NSE).
"""

import yfinance as yf
import pandas as pd
from typing import Optional
from datetime import datetime, timedelta


def fetch_price_history(
    symbol: str,
    period: str = "2y",
    interval: str = "1d"
) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV for a Yahoo Finance symbol (e.g. RELIANCE.NS).
    Returns DataFrame with DatetimeIndex or None on failure.
    """
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval, auto_adjust=True)
        if df is None or df.empty:
            # fallback download once
            df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True)
        if df is None or df.empty:
            return None
        # flatten multiindex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        cols = {str(c).lower(): c for c in df.columns}
        need = []
        for k in ("open", "high", "low", "close", "volume"):
            if k not in cols and k.title() not in df.columns:
                # try exact
                pass
        try:
            df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        except Exception:
            # already lower or mixed
            rename = {}
            for c in df.columns:
                cl = str(c).lower()
                if cl in ("open", "high", "low", "close", "volume") or cl.startswith("adj"):
                    rename[c] = "close" if "close" in cl else cl
            df = df.rename(columns=rename)
            keep = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
            df = df[keep].copy()
        else:
            df.columns = ["open", "high", "low", "close", "volume"]
        df = df.dropna(subset=["close"])
        if df.empty or len(df) < 5:
            return None
        return df
    except Exception:
        return None


def fetch_multiple_prices(symbols: list, period: str = "2y") -> dict:
    """Fetch price history for multiple symbols. Returns {symbol: df}."""
    result = {}
    for sym in symbols:
        df = fetch_price_history(sym, period=period)
        if df is not None and not df.empty:
            result[sym] = df
    return result