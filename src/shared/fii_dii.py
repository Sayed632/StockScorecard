"""
FII / DII Monitor
Fetches latest institutional flow data (cash market) from free public API.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import requests
import logging

logger = logging.getLogger(__name__)

API_LATEST = "https://fii-diidata.mrchartist.com/api/data"
API_HISTORY = "https://fii-diidata.mrchartist.com/api/history"


@dataclass
class FIIDIISnapshot:
    date: str
    fii_buy: float
    fii_sell: float
    fii_net: float
    dii_buy: float
    dii_sell: float
    dii_net: float
    sentiment_score: Optional[float] = None
    source: str = ""
    updated_at: str = ""
    history_nets: Optional[List[Dict[str, Any]]] = None  # last few days

    @property
    def fii_bias(self) -> str:
        if self.fii_net > 500:
            return "Buying"
        if self.fii_net < -500:
            return "Selling"
        return "Neutral"

    @property
    def dii_bias(self) -> str:
        if self.dii_net > 500:
            return "Buying"
        if self.dii_net < -500:
            return "Selling"
        return "Neutral"

    @property
    def overall_tone(self) -> str:
        # Simple combined view
        if self.fii_net < -2000 and self.dii_net > 1000:
            return "FII selling absorbed by DII"
        if self.fii_net > 1000 and self.dii_net > 500:
            return "Both FII & DII supportive"
        if self.fii_net < -2000 and self.dii_net < 0:
            return "Broad institutional selling"
        if self.fii_net > 0 and self.dii_net < -500:
            return "FII buying, DII light"
        return "Mixed / balanced flows"


def fetch_fii_dii(include_history: bool = True) -> Optional[FIIDIISnapshot]:
    """Fetch latest FII/DII cash market data."""
    try:
        r = requests.get(API_LATEST, timeout=15)
        r.raise_for_status()
        d = r.json()

        history = None
        if include_history:
            try:
                h = requests.get(API_HISTORY, timeout=15)
                if h.ok:
                    rows = h.json()
                    # Expect list newest first; keep last 5
                    if isinstance(rows, list):
                        history = []
                        for row in rows[:5]:
                            history.append({
                                "date": row.get("date") or row.get("d"),
                                "fii_net": row.get("fii_net") or row.get("fn"),
                                "dii_net": row.get("dii_net") or row.get("dn"),
                            })
            except Exception as e:
                logger.warning(f"FII/DII history fetch failed: {e}")

        return FIIDIISnapshot(
            date=str(d.get("date", "")),
            fii_buy=float(d.get("fii_buy") or 0),
            fii_sell=float(d.get("fii_sell") or 0),
            fii_net=float(d.get("fii_net") or 0),
            dii_buy=float(d.get("dii_buy") or 0),
            dii_sell=float(d.get("dii_sell") or 0),
            dii_net=float(d.get("dii_net") or 0),
            sentiment_score=d.get("sentiment_score"),
            source=str(d.get("_source", "")),
            updated_at=str(d.get("_updated_at", "")),
            history_nets=history,
        )
    except Exception as e:
        logger.error(f"FII/DII fetch failed: {e}")
        return None


def format_fii_dii_section(snap: Optional[FIIDIISnapshot]) -> List[str]:
    """Return Telegram HTML lines for FII/DII section."""
    lines = ["<b>🏦 FII / DII MONITOR</b>"]
    if not snap:
        lines.append("• Data unavailable today")
        lines.append("")
        return lines

    def fmt(x: float) -> str:
        sign = "+" if x >= 0 else ""
        return f"{sign}{x:,.0f} Cr"

    fii_emoji = "🟢" if snap.fii_net > 500 else ("🔴" if snap.fii_net < -500 else "⚪")
    dii_emoji = "🟢" if snap.dii_net > 500 else ("🔴" if snap.dii_net < -500 else "⚪")

    lines.append(f"• Date: <b>{snap.date}</b>")
    lines.append(f"• FII Net: {fii_emoji} <b>{fmt(snap.fii_net)}</b> ({snap.fii_bias})")
    lines.append(f"• DII Net: {dii_emoji} <b>{fmt(snap.dii_net)}</b> ({snap.dii_bias})")
    lines.append(f"• Tone: <i>{snap.overall_tone}</i>")

    if snap.history_nets:
        recent = []
        for h in snap.history_nets[:3]:
            d = h.get("date", "")
            fn = h.get("fii_net")
            dn = h.get("dii_net")
            if fn is None or dn is None:
                continue
            recent.append(f"{d}: FII {fmt(float(fn))} | DII {fmt(float(dn))}")
        if recent:
            lines.append("• Recent:")
            for r in recent:
                lines.append(f"  – {r}")

    lines.append("")
    return lines
