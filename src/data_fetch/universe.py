"""
NSE universe + market-cap & sector classification.
Uses a lightweight free source + yfinance fallback.
"""

import pandas as pd
import requests
from io import StringIO
from typing import Optional


def get_nse_equity_list() -> pd.DataFrame:
    """
    Fetch current NSE equity list (symbol, name, series).
    Falls back to a static popular list if NSE blocks the request.
    """
    url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text))
        df = df[df["SERIES"] == "EQ"].copy()
        df = df.rename(columns={
            "SYMBOL": "symbol",
            "NAME OF COMPANY": "name",
            "ISIN NUMBER": "isin"
        })
        return df[["symbol", "name", "isin"]].reset_index(drop=True)
    except Exception:
        # Minimal fallback universe (Nifty 50 + some popular names)
        fallback = [
            ("RELIANCE", "Reliance Industries Ltd"),
            ("TCS", "Tata Consultancy Services Ltd"),
            ("HDFCBANK", "HDFC Bank Ltd"),
            ("INFY", "Infosys Ltd"),
            ("ICICIBANK", "ICICI Bank Ltd"),
            ("HINDUNILVR", "Hindustan Unilever Ltd"),
            ("ITC", "ITC Ltd"),
            ("SBIN", "State Bank of India"),
            ("BHARTIARTL", "Bharti Airtel Ltd"),
            ("KOTAKBANK", "Kotak Mahindra Bank Ltd"),
            ("LT", "Larsen & Toubro Ltd"),
            ("AXISBANK", "Axis Bank Ltd"),
            ("BAJFINANCE", "Bajaj Finance Ltd"),
            ("ASIANPAINT", "Asian Paints Ltd"),
            ("MARUTI", "Maruti Suzuki India Ltd"),
            ("TITAN", "Titan Company Ltd"),
            ("SUNPHARMA", "Sun Pharmaceutical Industries Ltd"),
            ("ULTRACEMCO", "UltraTech Cement Ltd"),
            ("WIPRO", "Wipro Ltd"),
            ("NESTLEIND", "Nestle India Ltd"),
            ("LAURUSLABS", "Laurus Labs Ltd"),
            ("DIVISLAB", "Divi's Laboratories Ltd"),
            ("DRREDDY", "Dr. Reddy's Laboratories Ltd"),
            ("CIPLA", "Cipla Ltd"),
            ("AUROPHARMA", "Aurobindo Pharma Ltd"),
        ]
        return pd.DataFrame(fallback, columns=["symbol", "name"])


def classify_market_cap(market_cap_cr: float, large_threshold: float = 20000, mid_threshold: float = 5000) -> str:
    """Classify into Large / Mid / Small."""
    if pd.isna(market_cap_cr):
        return "Unknown"
    if market_cap_cr >= large_threshold:
        return "Large"
    elif market_cap_cr >= mid_threshold:
        return "Mid"
    else:
        return "Small"


def get_nse_universe(limit: Optional[int] = None) -> pd.DataFrame:
    """
    Returns a DataFrame with columns:
    symbol, name, sector (best effort), market_cap_cr (best effort)
    """
    universe = get_nse_equity_list()
    if limit:
        universe = universe.head(limit)

    # We enrich with yfinance later in the pipeline for market cap & sector
    universe["yahoo_symbol"] = universe["symbol"] + ".NS"
    return universe.reset_index(drop=True)