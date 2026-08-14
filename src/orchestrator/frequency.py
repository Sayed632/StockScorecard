"""
Automatic scanning frequency decision (URS 3.8 – Option A).
"""

from datetime import datetime
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


def decide_scanning_frequency(
    volatility_high: bool = False,
    results_season: bool = False,
    major_event: bool = False,          # budget, policy, etc.
    heavy_news_density: bool = False,
) -> Tuple[int, str]:
    """
    Returns (frequency, reason).
    1 = normal (post-close)
    2 = elevated (pre-open + post-close)
    3 = high impact
    """
    score = 0
    reasons = []

    if volatility_high:
        score += 2
        reasons.append("high volatility")
    if results_season:
        score += 2
        reasons.append("results season")
    if major_event:
        score += 3
        reasons.append("major policy/event")
    if heavy_news_density:
        score += 1
        reasons.append("high news density")

    if score >= 4:
        freq = 3
        label = "High Impact"
    elif score >= 2:
        freq = 2
        label = "Elevated"
    else:
        freq = 1
        label = "Normal"

    reason = f"{label} ({', '.join(reasons) if reasons else 'standard conditions'})"
    logger.info(f"Scanning frequency decided: {freq}x – {reason}")
    return freq, reason


def is_results_season(today: datetime = None) -> bool:
    """Rough heuristic: results season months in India."""
    today = today or datetime.now()
    # Typical peak: Apr-May, Jul-Aug, Oct-Nov, Jan-Feb
    return today.month in {1, 2, 4, 5, 7, 8, 10, 11}


def get_scan_slots(frequency: int) -> list:
    """Return recommended IST time slots for the given frequency."""
    if frequency == 1:
        return ["15:45-16:15 IST (Post-close)"]
    if frequency == 2:
        return ["08:45-09:10 IST (Pre-open)", "15:45-16:15 IST (Post-close)"]
    return [
        "08:45-09:10 IST (Pre-open)",
        "12:30-13:00 IST (Mid-session check)",
        "15:45-16:15 IST (Post-close)",
    ]