"""
India Standard Time helpers for all Telegram messages.

GitHub Actions runners use UTC. Always convert to IST before display
so timestamps match the clock in India (12-hour AM/PM).
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

IST = timezone(timedelta(hours=5, minutes=30))

# Example: 24 Sep 2026 | 1:45 PM IST
DEFAULT_FMT = "%d %b %Y | %-I:%M %p IST"
# macOS/Windows may not support %-I; provide fallbacks below


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


def format_ist(dt: Optional[datetime] = None, fmt: Optional[str] = None) -> str:
    """
    Standard stamp on every Telegram header.
    Default looks like: 24 Sep 2026 | 1:45 PM IST
    """
    local = to_ist(dt)
    if fmt:
        try:
            return local.strftime(fmt)
        except ValueError:
            pass
    # Prefer no leading zero on hour (Linux %-I); fallback #I / manual
    for candidate in (
        "%d %b %Y | %-I:%M %p IST",  # Linux
        "%d %b %Y | %#I:%M %p IST",  # Windows
        "%d %b %Y | %I:%M %p IST",   # zero-padded hour
    ):
        try:
            s = local.strftime(candidate)
            # strip leading zero on hour if present: "01:45 PM" -> "1:45 PM"
            # only in the time portion
            if " | 0" in s and (" AM" in s or " PM" in s):
                s = s.replace(" | 0", " | ", 1)
            return s
        except ValueError:
            continue
    # Ultimate fallback
    h = local.hour % 12 or 12
    ampm = "AM" if local.hour < 12 else "PM"
    return f"{local.day:02d} {local.strftime('%b %Y')} | {h}:{local.minute:02d} {ampm} IST"
