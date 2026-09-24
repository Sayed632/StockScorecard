"""
India Standard Time helpers for all Telegram messages.

GitHub Actions runners use UTC. Always convert to IST before display
so timestamps are not labeled IST while showing UTC clock.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

IST = timezone(timedelta(hours=5, minutes=30))


def now_ist() -> datetime:
    """Current time in Asia/Kolkata (IST)."""
    return datetime.now(IST)


def to_ist(dt: Optional[datetime] = None) -> datetime:
    """
    Convert any datetime to IST.
    Naive datetimes are treated as UTC (typical on CI runners).
    """
    if dt is None:
        return now_ist()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)


def format_ist(dt: Optional[datetime] = None, fmt: str = "%d %b %Y | %H:%M IST") -> str:
    """Standard stamp used on every Telegram message header."""
    return to_ist(dt).strftime(fmt)
