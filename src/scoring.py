"""
Combine Q / G / V / T into overall score and produce final table.
"""

import pandas as pd
import numpy as np
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from .data_fetch.universe import get_nse_universe, classify_market_cap
from .data_fetch.fundamentals import fetch_basic_fundamentals
from .data_fetch.prices import fetch_price_history
from .factors.quality import score_quality
from .factors.growth import score_growth
from .factors.valuation import score_valuation
from .factors.technical import score_technical


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def compute_overall(q: float, g: float, v: float, t: float, weights: dict) -> float:
    return (
        weights.get("Q", 0.30) * q +
        weights.get("G", 0.25) * g +
        weights.get("V", 0.25) * v +
        weights.get("T", 0.20) * t
    )


def run_scorecard(
    limit: Optional[int] = 40,
    config_path: str = "config.yaml",
    quiet: bool = False
) -> pd.DataFrame:
    """
    Main entry point.
    Fetches universe → fundamentals → prices → scores → returns DataFrame.
    """
    cfg = load_config(config_path)
    weights = cfg.get("factor_weights", {"Q": 0.30, "G": 0.25, "V": 0.25, "T": 0.20})
    large_th = cfg.get("market_cap_buckets", {}).get("large", 20000)
    mid_th = cfg.get("market_cap_buckets", {}).get("mid", 5000)

    if not quiet:
        print(f"[{datetime.now():%H:%M:%S}] Building universe (limit={limit})...")

    universe = get_nse_universe(limit=limit)

    records = []
    total = len(universe)

    for i, row in universe.iterrows():
        symbol = row["symbol"]
        yahoo = row["yahoo_symbol"]
        name = row.get("name", symbol)

        if not quiet:
            print(f"  [{i+1:3d}/{total}] {symbol:<12} ", end="", flush=True)

        # Fundamentals
        fund = fetch_basic_fundamentals(yahoo)
        fund["name"] = name

        # Prices for technicals
        prices = fetch_price_history(yahoo, period="2y")

        # Scores
        q = score_quality(fund)
        g = score_growth(fund)
        v = score_valuation(fund)
        t = score_technical(prices)
        overall = compute_overall(q, g, v, t, weights)

        mcap = fund.get("market_cap_cr")
        bucket = classify_market_cap(mcap, large_th, mid_th)

        rec = {
            "symbol": symbol,
            "name": name,
            "sector": fund.get("sector") or "Unknown",
            "industry": fund.get("industry") or "Unknown",
            "market_cap_cr": mcap,
            "market_cap_bucket": bucket,
            "Overall": round(overall, 1),
            "Q": round(q, 1),
            "G": round(g, 1),
            "V": round(v, 1),
            "T": round(t, 1),
            "pe": fund.get("pe"),
            "pb": fund.get("pb"),
            "roe": fund.get("roe"),
            "debt_to_equity": fund.get("debt_to_equity"),
            "revenue_growth": fund.get("revenue_growth"),
            "earnings_growth": fund.get("earnings_growth"),
        }
        records.append(rec)

        if not quiet:
            print(f"→ Overall {overall:5.1f}  (Q{q:.0f} G{g:.0f} V{v:.0f} T{t:.0f})")

    df = pd.DataFrame(records)
    df = df.sort_values("Overall", ascending=False).reset_index(drop=True)
    return df


def print_summary(df: pd.DataFrame):
    """Pretty print top scores and sector/bucket breakdown."""
    from tabulate import tabulate

    print("\n" + "=" * 80)
    print("TOP 15 STOCKS BY OVERALL SCORE")
    print("=" * 80)
    cols = ["symbol", "name", "market_cap_bucket", "sector", "Overall", "Q", "G", "V", "T"]
    print(tabulate(df[cols].head(15), headers="keys", tablefmt="simple", showindex=False))

    print("\n" + "=" * 80)
    print("AVERAGE SCORE BY MARKET-CAP BUCKET")
    print("=" * 80)
    bucket_avg = df.groupby("market_cap_bucket")[["Overall", "Q", "G", "V", "T"]].mean().round(1)
    print(tabulate(bucket_avg, headers="keys", tablefmt="simple"))

    print("\n" + "=" * 80)
    print("AVERAGE SCORE BY SECTOR (min 1 stock)")
    print("=" * 80)
    sector_avg = (
        df.groupby("sector")[["Overall", "Q", "G", "V", "T"]]
        .mean()
        .round(1)
        .sort_values("Overall", ascending=False)
    )
    print(tabulate(sector_avg, headers="keys", tablefmt="simple"))