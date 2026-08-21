"""
NSE Corporate Announcements (official exchange filings).

Uses NSE site JSON feed (same data the website shows):
  GET /api/corporate-announcements?index=equities

Not a licensed bulk data product — best-effort session + headers.
Filters to higher-impact subjects for StockScorecard.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any
import logging
import re
import requests

logger = logging.getLogger(__name__)

NSE_HOME = "https://www.nseindia.com"
NSE_ANN_API = "https://www.nseindia.com/api/corporate-announcements?index=equities"

# Subject / text patterns treated as market-relevant
HIGH_IMPACT = [
    r"financial results",
    r"\borders?\b",
    r"bagging",
    r"receiving of orders",
    r"contract",
    r"fund raising",
    r"acquisition",
    r"merger",
    r"amalgamation",
    r"open offer",
    r"buy.?back",
    r"dividend",
    r"bonus",
    r"split",
    r"preferential",
    r"qip\b",
    r"fda",
    r"warning",
    r"penalty",
    r"default",
    r"insolvency",
    r"award",
    r"mou\b",
    r"joint venture",
    r"capacity",
    r"expansion",
]

# Usually noise for trading decisions
LOW_IMPACT = [
    r"trading window",
    r"brsr",
    r"scrutinizer",
    r"newspaper publication",
    r"compliance.?certificate",
    r"regulation 30.*general updates",
]


@dataclass
class NSEAnnouncement:
    symbol: str
    company: str
    subject: str
    detail: str
    when: str
    industry: str = ""
    attachment: str = ""
    impact: str = "medium"  # high / medium / low


def _session() -> requests.Session:
    s = requests.Session()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    s.headers.update(headers)
    try:
        s.get(NSE_HOME, timeout=15)
        s.get(
            f"{NSE_HOME}/companies-listing/corporate-filings-announcements",
            timeout=15,
        )
    except Exception as e:
        logger.warning("NSE session bootstrap: %s", e)
    s.headers["Referer"] = f"{NSE_HOME}/companies-listing/corporate-filings-announcements"
    return s


def _classify(subject: str, detail: str) -> str:
    text = f"{subject} {detail}".lower()
    for pat in LOW_IMPACT:
        if re.search(pat, text, re.I):
            return "low"
    for pat in HIGH_IMPACT:
        if re.search(pat, text, re.I):
            return "high"
    return "medium"


def fetch_nse_announcements(limit: int = 40) -> List[NSEAnnouncement]:
    """Fetch latest equity corporate announcements from NSE."""
    try:
        s = _session()
        r = s.get(NSE_ANN_API, timeout=20)
        if not r.ok:
            logger.warning("NSE announcements HTTP %s", r.status_code)
            return []
        data = r.json()
        if not isinstance(data, list):
            data = data.get("data") or []
    except Exception as e:
        logger.warning("NSE announcements fetch failed: %s", e)
        return []

    out: List[NSEAnnouncement] = []
    for row in data[: max(limit * 2, 40)]:
        sym = (row.get("symbol") or "").strip().upper()
        if not sym:
            continue
        subject = (row.get("desc") or "").strip()
        detail = (row.get("attchmntText") or "").strip()
        impact = _classify(subject, detail)
        out.append(
            NSEAnnouncement(
                symbol=sym,
                company=(row.get("sm_name") or "").strip(),
                subject=subject,
                detail=detail,
                when=(row.get("an_dt") or row.get("exchdisstime") or row.get("sort_date") or ""),
                industry=(row.get("smIndustry") or "").strip(),
                attachment=(row.get("attchmntFile") or "").strip(),
                impact=impact,
            )
        )

    # Prefer high impact first
    rank = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda x: rank.get(x.impact, 9))
    return out[:limit]


def format_nse_section(items: Optional[List[NSEAnnouncement]] = None) -> List[str]:
    if items is None:
        items = fetch_nse_announcements(25)
    lines = ["<b>🏛️ NSE OFFICIAL CATALYSTS</b> <i>(corporate announcements)</i>"]
    high = [i for i in items if i.impact == "high"]
    show = high[:10] if high else items[:8]
    if not show:
        lines.append("• No announcements fetched")
        lines.append("")
        return lines
    for a in show:
        icon = "🔥" if a.impact == "high" else "•"
        subj = a.subject or "Update"
        detail = a.detail
        if len(detail) > 90:
            detail = detail[:87] + "…"
        lines.append(f"{icon} <b>{a.symbol}</b> – {subj}")
        if detail:
            lines.append(f"   {detail}")
    lines.append("<i>Official NSE filings – verify PDF before acting.</i>")
    lines.append("")
    return lines


def format_nse_telegram_message(items: Optional[List[NSEAnnouncement]] = None) -> str:
    if items is None:
        items = fetch_nse_announcements(25)
    now = datetime.now().strftime("%d %b %Y | %H:%M IST")
    lines = [
        "<b>🏛️ NSE Corporate Announcements</b>",
        now,
        "",
        "<i>Official exchange filings (equities). Best-effort public feed.</i>",
        "",
    ]
    lines.extend(format_nse_section(items))
    lines.append("<i>StockScorecard – NSE catalysts</i>")
    return "\n".join(lines)
