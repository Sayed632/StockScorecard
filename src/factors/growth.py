"""
G-Factor: Historical Financial Performance & Growth Trend
Higher score = stronger & more consistent growth.
"""

import numpy as np
from typing import Dict, Any


def _safe(val, default=np.nan):
    try:
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return default
        return float(val)
    except Exception:
        return default


def score_growth(row: Dict[str, Any]) -> float:
    """
    Compute G score 0-100.
    Uses yfinance growth fields + margin quality as proxy for trend.
    """
    scores = []

    # Revenue growth (YoY)
    rg = _safe(row.get("revenue_growth"))
    if not np.isnan(rg):
        # -20% → 0, 0% → 40, 15% → 75, 40%+ → 100
        s = np.clip((rg + 0.15) / 0.55 * 100, 0, 100)
        scores.append(s)

    # Earnings growth
    eg = _safe(row.get("earnings_growth"))
    if not np.isnan(eg):
        s = np.clip((eg + 0.20) / 0.70 * 100, 0, 100)
        scores.append(s)

    # Profit margin level (quality of growth)
    pm = _safe(row.get("profit_margin"))
    if not np.isnan(pm):
        s = np.clip((pm + 0.05) / 0.30 * 100, 0, 100)
        scores.append(s * 0.7)  # slightly lower weight

    # Operating margin
    om = _safe(row.get("operating_margin"))
    if not np.isnan(om):
        s = np.clip((om + 0.05) / 0.35 * 100, 0, 100)
        scores.append(s * 0.7)

    if not scores:
        return 50.0

    return float(np.mean(scores))