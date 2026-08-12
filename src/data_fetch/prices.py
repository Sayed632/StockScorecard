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
            return None
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.columns = ["open", "high", "low", "close", "volume"]
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