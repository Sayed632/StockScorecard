"""
Basic fundamental data via yfinance.
Includes multi-year CAGR (revenue / earnings / price) when series are available.
"""

from __future__ import annotations

import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional


def _cagr(start: float, end: float, years: float) -> Optional[float]:
    """Annualised CAGR as decimal (0.15 = 15%)."""
    try:
        if start is None or end is None or years is None:
            return None
        start, end, years = float(start), float(end), float(years)
        if start <= 0 or end <= 0 or years <= 0:
            return None
        return (end / start) ** (1.0 / years) - 1.0
    except Exception:
        return None


def _series_cagr_from_financials(df: Optional[pd.DataFrame], row_keys: tuple, max_years: int = 4) -> Optional[float]:
    """
    yfinance financials: columns are period ends (newest first).
    Pick a row like Total Revenue / Net Income and compute CAGR over available span.
    """
    if df is None or df.empty:
        return None
    row = None
    idx_lower = {str(i).lower(): i for i in df.index}
    for key in row_keys:
        for lk, orig in idx_lower.items():
            if key in lk:
                row = df.loc[orig]
                break
        if row is not None:
            break
    if row is None:
        return None
    vals = []
    for v in row.values:
        try:
            x = float(v)
            if np.isfinite(x) and x != 0:
                vals.append(x)
        except Exception:
            continue
    # vals are typically newest → oldest
    if len(vals) < 2:
        return None
    newest, oldest = vals[0], vals[-1]
    years = float(len(vals) - 1)
    if years < 1:
        return None
    years = min(years, float(max_years))
    # if signs differ (loss ↔ profit), CAGR not meaningful
    if newest * oldest <= 0:
        return None
    return _cagr(abs(oldest), abs(newest), years)


def _price_cagr(yahoo_symbol: str, years: int = 3) -> Optional[float]:
    try:
        t = yf.Ticker(yahoo_symbol)
        hist = t.history(period=f"{years + 1}y", auto_adjust=True)
        if hist is None or len(hist) < 200:
            return None
        close = hist["Close"].dropna()
        if len(close) < 200:
            return None
        end = float(close.iloc[-1])
        # approx years back
        target = close.index[-1] - pd.Timedelta(days=int(365.25 * years))
        past = close[close.index <= target]
        if past.empty:
            start = float(close.iloc[0])
            span = max((close.index[-1] - close.index[0]).days / 365.25, 1.0)
        else:
            start = float(past.iloc[-1])
            span = float(years)
        return _cagr(start, end, span)
    except Exception:
        return None


def fetch_basic_fundamentals(yahoo_symbol: str) -> Dict[str, Any]:
    """
    Pull key fundamental metrics from yfinance + multi-year CAGRs.
    """
    out: Dict[str, Any] = {
        "symbol": yahoo_symbol.replace(".NS", "").replace(".BO", ""),
        "yahoo_symbol": yahoo_symbol,
        "market_cap_cr": None,
        "sector": None,
        "industry": None,
        "pe": None,
        "pb": None,
        "ps": None,
        "peg": None,
        "peg_derived": False,
        "roe": None,
        "roa": None,
        "debt_to_equity": None,
        "current_ratio": None,
        "profit_margin": None,
        "operating_margin": None,
        "revenue_growth": None,
        "earnings_growth": None,
        "revenue_cagr": None,
        "earnings_cagr": None,
        "price_cagr_3y": None,
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

        mcap = info.get("marketCap")
        if mcap:
            out["market_cap_cr"] = round(mcap / 1e7, 2)

        out["sector"] = info.get("sector")
        out["industry"] = info.get("industry")
        out["pe"] = info.get("trailingPE") or info.get("forwardPE")
        out["pb"] = info.get("priceToBook")
        out["ps"] = info.get("priceToSalesTrailing12Months")
        out["peg"] = info.get("pegRatio")
        # Derive PEG when vendor field missing: PE / (EPS growth %)
        if out["peg"] is None and out.get("pe") and out.get("earnings_growth"):
            try:
                eg = float(out["earnings_growth"])
                pe = float(out["pe"])
                # yfinance earningsGrowth is often decimal (0.15 = 15%)
                growth_pct = eg * 100.0 if abs(eg) <= 2 else eg
                if pe > 0 and growth_pct > 1:
                    out["peg"] = round(pe / growth_pct, 2)
                    out["peg_derived"] = True
            except Exception:
                pass
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

        # Multi-year CAGRs from annual financials (best-effort)
        try:
            fin = t.financials
            out["revenue_cagr"] = _series_cagr_from_financials(
                fin, ("total revenue", "operating revenue", "revenue")
            )
            out["earnings_cagr"] = _series_cagr_from_financials(
                fin, ("net income", "net income common stockholders", "reconciled net income")
            )
        except Exception:
            pass

        # Price CAGR as market-performance growth proxy
        out["price_cagr_3y"] = _price_cagr(yahoo_symbol, years=3)

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
        suffixes=("", "_y"),
    )
    if "name" in merged.columns and "name_y" in merged.columns:
        merged = merged.drop(columns=["name_y"])
    return merged
