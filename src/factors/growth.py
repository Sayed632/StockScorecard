"""
G-Factor: Historical Financial Performance & Growth Trend
Higher score = stronger & more consistent growth.

Includes:
  - YoY revenue / earnings growth (near-term)
  - Multi-year revenue / earnings CAGR (durability)
  - 3Y price CAGR (market-recognised compounding; secondary)
  - Margin quality
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


def _cagr_to_score(cagr: float, floor: float = -0.10, good: float = 0.18) -> float:
    """Map CAGR decimal to 0-100. ~18% CAGR → high score."""
    # floor → 0, 0 → ~35, good → ~80, 2*good → 100
    return float(np.clip((cagr - floor) / (good - floor + 0.12) * 85 + 10, 0, 100))


def score_growth(row: Dict[str, Any]) -> float:
    """
    Compute G score 0-100.
    Multi-year CAGR gets meaningful weight when present so one hot year
    cannot fully dominate the growth picture.
    """
    scores = []
    weights = []

    # --- Near-term YoY ---
    rg = _safe(row.get("revenue_growth"))
    if not np.isnan(rg):
        s = np.clip((rg + 0.15) / 0.55 * 100, 0, 100)
        scores.append(s)
        weights.append(1.0)

    eg = _safe(row.get("earnings_growth"))
    if not np.isnan(eg):
        s = np.clip((eg + 0.20) / 0.70 * 100, 0, 100)
        scores.append(s)
        weights.append(1.0)

    # --- Multi-year CAGR (strengthens long-term growth quality) ---
    rev_cagr = _safe(row.get("revenue_cagr"))
    if not np.isnan(rev_cagr):
        scores.append(_cagr_to_score(rev_cagr))
        weights.append(1.35)  # durable sales compounding

    earn_cagr = _safe(row.get("earnings_cagr"))
    if not np.isnan(earn_cagr):
        scores.append(_cagr_to_score(earn_cagr, floor=-0.15, good=0.20))
        weights.append(1.35)  # durable profit compounding

    # Price CAGR: secondary (can reflect re-rating, not only ops)
    px_cagr = _safe(row.get("price_cagr_3y"))
    if not np.isnan(px_cagr):
        scores.append(_cagr_to_score(px_cagr, floor=-0.15, good=0.22))
        weights.append(0.55)

    # --- Margin quality ---
    pm = _safe(row.get("profit_margin"))
    if not np.isnan(pm):
        s = np.clip((pm + 0.05) / 0.30 * 100, 0, 100)
        scores.append(s * 0.7)
        weights.append(0.7)

    om = _safe(row.get("operating_margin"))
    if not np.isnan(om):
        s = np.clip((om + 0.05) / 0.35 * 100, 0, 100)
        scores.append(s * 0.7)
        weights.append(0.7)

    if not scores:
        return 50.0

    w = np.array(weights, dtype=float)
    s = np.array(scores, dtype=float)
    return float(np.average(s, weights=w))
