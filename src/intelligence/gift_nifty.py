"""
GIFT Nifty (ex-SGX Nifty) – pre-open / overnight market tone for NSE.

Use: bias for swing risk (constructive / cautious), NOT stock picking.
Data: best-effort public pages + headline fallback (no paid feed).
"""

from __future__ import annotations

from src.shared.time_ist import format_ist, now_ist

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET
import logging
import re
import requests

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; StockScorecard/1.0; +https://github.com/Sayed632/StockScorecard)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@dataclass
class GiftSnapshot:
    last: Optional[float]
    change_pct: Optional[float]
    change_pts: Optional[float]
    day_high: Optional[float]
    day_low: Optional[float]
    bias: str  # CONSTRUCTIVE | CAUTIOUS | NEUTRAL | UNKNOWN
    bias_pts: int  # for swing score adjust: +2 / 0 / -2
    source: str
    note: str


def _f(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        s = str(x).replace(",", "").replace("%", "").strip()
        return float(s)
    except Exception:
        return None


def _parse_quantsapp(html: str) -> Optional[GiftSnapshot]:
    # Patterns like 23,256.00 +16.00 (+0.07%)
    m = re.search(
        r"(\d{2},\d{3}\.\d{1,2})\s*([+-]?\d+\.?\d*)\s*\(([+-]?\d+\.?\d*)\s*%\)",
        html,
    )
    if not m:
        m = re.search(
            r"GIFT Nifty[^0-9]{0,40}(\d{2},\d{3}\.?\d*)[^0-9%]{0,20}([+-]?\d+\.?\d*)\s*%",
            html,
            re.I,
        )
    last = chg = pct = None
    if m:
        last = _f(m.group(1))
        if m.lastindex and m.lastindex >= 3:
            chg = _f(m.group(2))
            pct = _f(m.group(3))
        elif m.lastindex >= 2:
            pct = _f(m.group(2))
    hi = re.search(r"Day high[^0-9]{0,10}(\d{2},\d{3}\.?\d*)", html, re.I)
    lo = re.search(r"Day low[^0-9]{0,10}(\d{2},\d{3}\.?\d*)", html, re.I)
    if last is None:
        return None
    bias, pts, note = _bias_from_pct(pct)
    return GiftSnapshot(
        last=last,
        change_pct=pct,
        change_pts=chg,
        day_high=_f(hi.group(1)) if hi else None,
        day_low=_f(lo.group(1)) if lo else None,
        bias=bias,
        bias_pts=pts,
        source="quantsapp",
        note=note,
    )


def _bias_from_pct(pct: Optional[float]) -> tuple:
    if pct is None:
        return "UNKNOWN", 0, "No % change parsed"
    if pct >= 0.35:
        return "CONSTRUCTIVE", 2, "GIFT Nifty firm – risk-on tone for new swings"
    if pct >= 0.10:
        return "CONSTRUCTIVE", 1, "GIFT Nifty mildly positive"
    if pct <= -0.35:
        return "CAUTIOUS", -2, "GIFT Nifty weak – prefer WAIT / smaller size"
    if pct <= -0.10:
        return "CAUTIOUS", -1, "GIFT Nifty mildly soft"
    return "NEUTRAL", 0, "GIFT Nifty near flat – stock-specific setups matter more"


def _from_page(url: str, parser) -> Optional[GiftSnapshot]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=18)
        if not r.ok or len(r.text) < 500:
            return None
        return parser(r.text)
    except Exception as e:
        logger.debug("gift page %s: %s", url, e)
        return None


def _from_news_rss() -> Optional[GiftSnapshot]:
    """Fallback: infer tone from GIFT Nifty headlines only."""
    url = (
        "https://news.google.com/rss/search?"
        "q=GIFT+Nifty+OR+%22SGX+Nifty%22+India&hl=en-IN&gl=IN&ceid=IN:en"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if not r.ok:
            return None
        root = ET.fromstring(r.content)
        titles = []
        for item in list(root.iter("item"))[:8]:
            t = item.find("title")
            if t is not None and t.text:
                titles.append(t.text)
        if not titles:
            return None
        blob = " ".join(titles).lower()
        pos = len(re.findall(r"surge|jump|rally|gap.?up|higher|firm|positive", blob))
        neg = len(re.findall(r"fall|drop|gap.?down|weak|lower|selloff|caution", blob))
        if pos >= neg + 2:
            bias, pts = "CONSTRUCTIVE", 1
            note = "Headline tone positive (no live quote)"
        elif neg >= pos + 2:
            bias, pts = "CAUTIOUS", -1
            note = "Headline tone soft (no live quote)"
        else:
            bias, pts = "NEUTRAL", 0
            note = "Headline tone mixed (no live quote)"
        return GiftSnapshot(
            last=None,
            change_pct=None,
            change_pts=None,
            day_high=None,
            day_low=None,
            bias=bias,
            bias_pts=pts,
            source="news_rss",
            note=note + " · " + titles[0][:80],
        )
    except Exception as e:
        logger.debug("gift rss: %s", e)
        return None


def fetch_gift_nifty() -> GiftSnapshot:
    snap = _from_page("https://www.quantsapp.com/gift-nifty", _parse_quantsapp)
    if snap:
        return snap

    def parse_generic(html: str) -> Optional[GiftSnapshot]:
        m = re.search(
            r"(\d{2},\d{3}\.\d{1,2}).{0,40}?\(([+-]?\d+\.?\d*)\s*%\)",
            html,
        )
        if not m:
            m = re.search(r"(\d{2},\d{3}\.\d{1,2})\s+([+-]\d+\.?\d*)\s*%", html)
        if not m:
            return None
        last = _f(m.group(1))
        pct = _f(m.group(2))
        bias, pts, note = _bias_from_pct(pct)
        return GiftSnapshot(
            last=last,
            change_pct=pct,
            change_pts=None,
            day_high=None,
            day_low=None,
            bias=bias,
            bias_pts=pts,
            source="public_page",
            note=note,
        )

    for url in (
        "https://www.fnoscan.com/gift-nifty-live",
        "https://stoxpulse.in/gift-nifty",
    ):
        snap = _from_page(url, parse_generic)
        if snap:
            snap.source = url.split("/")[2]
            return snap

    snap = _from_news_rss()
    if snap:
        return snap

    return GiftSnapshot(
        last=None,
        change_pct=None,
        change_pts=None,
        day_high=None,
        day_low=None,
        bias="UNKNOWN",
        bias_pts=0,
        source="none",
        note="Could not fetch GIFT Nifty – no market gate applied",
    )


def gift_swing_bias_pts() -> int:
    """Points to add to swing scores (small)."""
    return fetch_gift_nifty().bias_pts


def format_gift_nifty_telegram(snap: Optional[GiftSnapshot] = None) -> str:
    if snap is None:
        snap = fetch_gift_nifty()
    now = format_ist(now_ist())
    emoji = {
        "CONSTRUCTIVE": "🟢",
        "CAUTIOUS": "🔴",
        "NEUTRAL": "🟡",
        "UNKNOWN": "⚪",
    }.get(snap.bias, "⚪")

    lines = [
        "<b>🌐 GIFT NIFTY – Market Tone</b>",
        now,
        "",
    ]
    if snap.last is not None:
        ch = ""
        if snap.change_pct is not None:
            ch = f" ({snap.change_pct:+.2f}%)"
        elif snap.change_pts is not None:
            ch = f" ({snap.change_pts:+.0f} pts)"
        lines.append(f"• Last: <b>{snap.last:,.2f}</b>{ch}")
    else:
        lines.append("• Last: — (quote unavailable)")
    if snap.day_low is not None and snap.day_high is not None:
        lines.append(f"• Range: {snap.day_low:,.2f} – {snap.day_high:,.2f}")
    lines.append(f"• Bias: {emoji} <b>{snap.bias}</b> (swing adjust {snap.bias_pts:+d} pts)")
    lines.append(f"• {snap.note}")
    lines.append(f"• Source: {snap.source}")
    lines.append("")
    lines.append("<b>How to use</b>")
    lines.append("• CONSTRUCTIVE → allow CONTINUE ideas with normal size")
    lines.append("• CAUTIOUS → prefer WAIT / smaller size / tighter stops")
    lines.append("• Does not pick individual stocks")
    lines.append("")
    lines.append(
        "<i>GIFT Nifty = overnight/pre-open Nifty tone (NSE IX). "
        "Indication only — open can differ. Not advice. StockScorecard</i>"
    )
    return "\n".join(lines)
