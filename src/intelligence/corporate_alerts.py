"""
Corporate Alerts – dedicated Telegram message focused on company events.

Same data source as NSE catalysts (official filings), but formatted like a
news ticker: one company → one clear story line (orders, LOA, FDA, JV,
fund raise, production, launches).

Explicit focus message – not mixed into scores.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
import logging
import re

from src.intelligence.nse_announcements import (
    NSEAnnouncement,
    fetch_nse_announcements,
    HIGH_IMPACT,
)

logger = logging.getLogger(__name__)

# Extra patterns for announcement-style channels (product / ops / L1)
EXTRA_ALERT = [
    r"letter of award",
    r"\bloa\b",
    r"lowest bidder",
    r"\bl1\b",
    r"purchase order",
    r"\bpo\b",
    r"commercial production",
    r"commenced.*production",
    r"launched",
    r"launch of",
    r"inaugurat",
    r"inspection",
    r"us\s*fda",
    r"production of",
    r"crude steel",
    r"supply contract",
    r"board.*consider",
    r"fund.?rais",
    r"joint venture",
    r"\bjv\b",
]


def _is_alert_worthy(a: NSEAnnouncement) -> bool:
    if a.impact == "high":
        return True
    if a.impact == "low":
        return False
    text = f"{a.subject} {a.detail}".lower()
    for pat in EXTRA_ALERT:
        if re.search(pat, text, re.I):
            return True
    return False


def _story_line(a: NSEAnnouncement) -> str:
    """One readable line: Company : event summary."""
    company = (a.company or a.symbol or "").strip()
    if company and not company.upper().endswith("LTD") and "LIMITED" not in company.upper():
        # keep as-is; many filings already have full name
        pass
    body = (a.detail or "").strip() or (a.subject or "").strip()
    # Prefer subject if detail is empty/short; prefer detail for story
    if a.subject and a.detail and len(a.detail) > 40:
        # Avoid repeating subject if detail already complete
        body = a.detail.strip()
        if a.subject.lower() not in body.lower()[:80]:
            body = f"{a.subject.strip()} — {body}"
    elif a.subject:
        body = a.subject.strip()

    body = re.sub(r"\s+", " ", body).strip()
    if len(body) > 320:
        body = body[:317] + "…"

    name = company if company else a.symbol
    return f"<b>{name}</b> : {body}"


def collect_corporate_alerts(limit: int = 15) -> List[NSEAnnouncement]:
    items = fetch_nse_announcements(limit=50)
    alerts = [a for a in items if _is_alert_worthy(a)]
    # de-dupe by symbol+subject prefix
    seen = set()
    out: List[NSEAnnouncement] = []
    for a in alerts:
        key = (a.symbol, (a.subject or "")[:60].lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(a)
        if len(out) >= limit:
            break
    return out


def format_corporate_alerts_telegram(
    items: Optional[List[NSEAnnouncement]] = None,
) -> str:
    if items is None:
        items = collect_corporate_alerts(15)
    now = datetime.now().strftime("%d %b %Y | %H:%M IST")

    lines = [
        "<b>📢 CORPORATE ALERTS</b>",
        now,
        "",
        "<i>Company events from official NSE filings — orders, LOA, FDA, JV, fund raise, production.</i>",
        "",
    ]

    if not items:
        lines.append("• No high-relevance corporate alerts fetched right now")
        lines.append("")
        lines.append("<i>Feed depends on NSE public API availability.</i>")
    else:
        for a in items:
            lines.append(f"• {_story_line(a)}")
            lines.append("")  # spacing like news channels

    lines.append(
        "<i>Verify attachment/PDF on NSE before acting. Not investment advice. StockScorecard</i>"
    )
    return "\n".join(lines)
