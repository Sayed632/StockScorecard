"""
V-Factor: Relative Valuation vs peers / absolute cheapness
Higher score = more attractively valued (cheaper).

PEG is weighted more when available (growth-adjusted PE).
"""

import numpy as np
from typing import Dict, Any, Optional, Tuple


def _safe(val, default=np.nan):
    try:
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return default
        return float(val)
    except Exception:
        return default


def peg_label(peg: Optional[float]) -> str:
    """Human band for Telegram / reasons."""
    if peg is None:
        return ""
    try:
        p = float(peg)
    except Exception:
        return ""
    if p <= 0:
        return ""
    if p < 1.0:
        return "PEG cheap vs growth"
    if p < 1.5:
        return "PEG reasonable"
    if p < 2.5:
        return "PEG rich"
    return "PEG expensive"


def score_valuation(row: Dict[str, Any], sector_medians: Dict[str, float] = None) -> float:
    """
    Compute V score 0-100 (higher = cheaper / better value).
    Uses PE, PB, PEG, PS when available. PEG gets higher weight.
    """
    scores = []
    weights = []

    pe = _safe(row.get("pe"))
    if not np.isnan(pe) and pe > 0:
        s = np.clip(110 - pe * 1.8, 5, 100)
        scores.append(s)
        weights.append(1.0)

    fpe = _safe(row.get("forward_pe"))
    if not np.isnan(fpe) and fpe > 0:
        s = np.clip(110 - fpe * 1.6, 5, 100)
        scores.append(s)
        weights.append(0.9)

    pb = _safe(row.get("pb"))
    if not np.isnan(pb) and pb > 0:
        s = np.clip(100 - pb * 8, 5, 100)
        scores.append(s)
        weights.append(0.85)

    # PEG – growth-adjusted (higher weight)
    peg = _safe(row.get("peg"))
    if not np.isnan(peg) and peg > 0:
        # 0.5 → ~92, 1.0 → 75, 1.5 → 57, 2.0 → 40, 3+ → ~15
        s = np.clip(110 - peg * 35, 5, 100)
        scores.append(s)
        weights.append(1.45)

    ps = _safe(row.get("ps"))
    if not np.isnan(ps) and ps > 0:
        s = np.clip(100 - ps * 12, 5, 100)
        scores.append(s)
        weights.append(0.7)

    if not scores:
        return 50.0

    return float(np.average(np.array(scores), weights=np.array(weights)))
