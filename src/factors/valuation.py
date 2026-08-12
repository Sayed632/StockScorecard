"""
V-Factor: Relative Valuation vs peers / absolute cheapness
Higher score = more attractively valued (cheaper).
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


def score_valuation(row: Dict[str, Any], sector_medians: Dict[str, float] = None) -> float:
    """
    Compute V score 0-100 (higher = cheaper / better value).
    Uses PE, PB, PEG, PS when available.
    """
    scores = []

    # PE (lower better)
    pe = _safe(row.get("pe"))
    if not np.isnan(pe) and pe > 0:
        # 5 → 95, 15 → 70, 30 → 40, 60+ → 10
        s = np.clip(110 - pe * 1.8, 5, 100)
        scores.append(s)

    # Forward PE if available
    fpe = _safe(row.get("forward_pe"))
    if not np.isnan(fpe) and fpe > 0:
        s = np.clip(110 - fpe * 1.6, 5, 100)
        scores.append(s)

    # Price to Book
    pb = _safe(row.get("pb"))
    if not np.isnan(pb) and pb > 0:
        # 0.5 → 95, 2 → 70, 5 → 40, 12+ → 10
        s = np.clip(100 - pb * 8, 5, 100)
        scores.append(s)

    # PEG
    peg = _safe(row.get("peg"))
    if not np.isnan(peg) and peg > 0:
        # 0.5 → 90, 1.0 → 70, 2.0 → 40, 3+ → 15
        s = np.clip(110 - peg * 35, 5, 100)
        scores.append(s)

    # Price to Sales
    ps = _safe(row.get("ps"))
    if not np.isnan(ps) and ps > 0:
        s = np.clip(100 - ps * 12, 5, 100)
        scores.append(s)

    if not scores:
        return 50.0

    return float(np.mean(scores))