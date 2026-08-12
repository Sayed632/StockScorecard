"""
Basic fundamental data via yfinance.
For production use you can later plug Screener.in / paid APIs.
"""

import yfinance as yf
import pandas as pd
from typing import Dict, Any, Optional


def fetch_basic_fundamentals(yahoo_symbol: str) -> Dict[str, Any]:
    """
    Pull key fundamental metrics from yfinance.
    Returns a flat dict with common ratios and growth proxies.
    """
    out: Dict[str, Any] = {
        "symbol": yahoo_symbol.replace(".NS", ""),
        "yahoo_symbol": yahoo_symbol,
        "market_cap_cr": None,
        "sector": None,
        "industry": None,
        "pe": None,
        "pb": None,
        "ps": None,
        "peg": None,
        "roe": None,
        "roa": None,
        "debt_to_equity": None,
        "current_ratio": None,
        "profit_margin": None,
        "operating_margin": None,
        "revenue_growth": None,
        "earnings_growth": None,
        "dividend_yield": None,
        "beta": None,
        "fifty_two_week_high": None,
        "fifty_two_week_low": None,
        "avg_volume": None,
        "trailing_eps": None,
        "forward_pe": None,
    }

    try:
        t = yf.Ticker(yahoo_symbol)
        info = t.info or {}

        # Market cap in Crores (INR)
        mcap = info.get("marketCap")
        if mcap:
            out["market_cap_cr"] = round(mcap / 1e7, 2)  # 1 Cr = 10 million

        out["sector"] = info.get("sector")
        out["industry"] = info.get("industry")
        out["pe"] = info.get("trailingPE") or info.get("forwardPE")
        out["pb"] = info.get("priceToBook")
        out["ps"] = info.get("priceToSalesTrailing12Months")
        out["peg"] = info.get("pegRatio")
        out["roe"] = info.get("returnOnEquity")
        out["roa"] = info.get("returnOnAssets")
        out["debt_to_equity"] = info.get("debtToEquity")
        out["current_ratio"] = info.get("currentRatio")
        out["profit_margin"] = info.get("profitMargins")
        out["operating_margin"] = info.get("operatingMargins")
        out["revenue_growth"] = info.get("revenueGrowth")
        out["earnings_growth"] = info.get("earningsGrowth")
        out["dividend_yield"] = info.get("dividendYield")
        out["beta"] = info.get("beta")
        out["fifty_two_week_high"] = info.get("fiftyTwoWeekHigh")
        out["fifty_two_week_low"] = info.get("fiftyTwoWeekLow")
        out["avg_volume"] = info.get("averageVolume")
        out["trailing_eps"] = info.get("trailingEps")
        out["forward_pe"] = info.get("forwardPE")

        # Clean None / NaN style values later in scoring
        return out
    except Exception:
        return out


def enrich_universe(universe: pd.DataFrame) -> pd.DataFrame:
    """Add fundamental columns to the universe DataFrame."""
    records = []
    for _, row in universe.iterrows():
        fund = fetch_basic_fundamentals(row["yahoo_symbol"])
        records.append(fund)

    fund_df = pd.DataFrame(records)
    merged = universe.merge(
        fund_df,
        left_on="symbol",
        right_on="symbol",
        how="left",
        suffixes=("", "_y")
    )
    # Prefer original name if conflict
    if "name" in merged.columns and "name_y" in merged.columns:
        merged = merged.drop(columns=["name_y"])
    return merged