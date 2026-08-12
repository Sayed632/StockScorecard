"""
Q-Factor: Financial Strength & Quality of Earnings
Higher score = stronger balance sheet / better quality.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any


def _safe(val, default=np.nan):
    try:
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return default
        return float(val)
    except Exception:
        return default


def score_quality(row: Dict[str, Any], peer_stats: Dict[str, Any] = None) -> float:
    """
    Compute Q score 0-100 for a single stock.
    Components (simplified transparent version):
      - ROE
      - ROA
      - Debt to Equity (lower better)
      - Current Ratio
      - Profit Margin
      - Operating Margin
    Each component is ranked / winsorized and averaged.
    """
    scores = []

    # 1. ROE (higher better) - typical good > 15%
    roe = _safe(row.get("roe"))
    if not np.isnan(roe):
        # Map -20% → 0, 0% → 30, 15% → 70, 30%+ → 100
        s = np.clip((roe + 0.05) / 0.35 * 100, 0, 100)
        scores.append(s)

    # 2. ROA
    roa = _safe(row.get("roa"))
    if not np.isnan(roa):
        s = np.clip((roa + 0.02) / 0.20 * 100, 0, 100)
        scores.append(s)

    # 3. Debt to Equity (lower better)
    de = _safe(row.get("debt_to_equity"))
    if not np.isnan(de):
        # 0 → 100, 50 → 70, 100 → 40, 200+ → 0
        s = np.clip(100 - (de / 2.5), 0, 100)
        scores.append(s)

    # 4. Current Ratio (higher better, ideal ~1.5-3)
    cr = _safe(row.get("current_ratio"))
    if not np.isnan(cr):
        if cr < 0.8:
            s = 20
        elif cr < 1.2:
            s = 50
        elif cr < 2.5:
            s = 85
        else:
            s = 70  # too high cash can be inefficient
        scores.append(s)

    # 5. Profit Margin
    pm = _safe(row.get("profit_margin"))
    if not np.isnan(pm):
        s = np.clip((pm + 0.02) / 0.25 * 100, 0, 100)
        scores.append(s)

    # 6. Operating Margin
    om = _safe(row.get("operating_margin"))
    if not np.isnan(om):
        s = np.clip((om + 0.02) / 0.30 * 100, 0, 100)
        scores.append(s)

    if not scores:
        return 50.0  # neutral if no data

    return float(np.mean(scores))