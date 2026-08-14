"""
FII / DII Monitor + sector FPI allocation + Swing bias helpers.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
import requests
import logging

logger = logging.getLogger(__name__)

API_LATEST = "https://fii-diidata.mrchartist.com/api/data"
API_HISTORY = "https://fii-diidata.mrchartist.com/api/history"
API_SECTORS = "https://fii-diidata.mrchartist.com/api/sectors"

# Map our scanner sector keys -> API sector name fragments
SECTOR_NAME_MAP = {
    "pharmaceuticals": ["healthcare", "pharma"],
    "banks_financials": ["financial services", "financial"],
    "information_technology": ["information technology", "it", "technology"],
    "automobile_ev": ["automobile", "auto"],
    "defence_aerospace": ["capital goods", "industrials", "defence"],
    "chemicals": ["chemicals", "materials", "commodities"],
    "fmcg": ["fmcg", "consumer", "fast moving"],
    "metals_mining": ["metals", "mining"],
    "energy_oil_gas_power": ["oil", "gas", "energy", "power"],
    "capital_goods_infra": ["capital goods", "construction", "infrastructure"],
    "realty": ["realty", "real estate"],
    "telecom": ["telecommunication", "telecom"],
    "media": ["media", "entertainment"],
    "textiles": ["textiles", "consumer discretionary"],
    "others_residual": ["services", "consumer services"],
}


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
    history_nets: Optional[List[Dict[str, Any]]] = None

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
        if self.fii_net < -2000 and self.dii_net > 1000:
            return "FII selling absorbed by DII"
        if self.fii_net > 1000 and self.dii_net > 500:
            return "Both FII & DII supportive"
        if self.fii_net < -2000 and self.dii_net < 0:
            return "Broad institutional selling"
        if self.fii_net > 0 and self.dii_net < -500:
            return "FII buying, DII light"
        return "Mixed / balanced flows"

    def swing_bias_points(self) -> Tuple[float, str]:
        """
        Points to add to Swing scores (can be negative).
        Strong FII selling → penalise swing aggressiveness.
        FII+DII buying → mild boost.
        """
        pts = 0.0
        reasons = []

        if self.fii_net <= -3000:
            pts -= 8
            reasons.append("heavy FII selling")
        elif self.fii_net <= -1000:
            pts -= 4
            reasons.append("FII selling")
        elif self.fii_net >= 2000:
            pts += 5
            reasons.append("strong FII buying")
        elif self.fii_net >= 500:
            pts += 2
            reasons.append("FII buying")

        if self.dii_net >= 3000:
            pts += 3
            reasons.append("strong DII buying")
        elif self.dii_net >= 1000:
            pts += 1
            reasons.append("DII buying")
        elif self.dii_net <= -2000:
            pts -= 3
            reasons.append("DII selling")

        # Cap
        pts = max(-10.0, min(8.0, pts))
        reason = ", ".join(reasons) if reasons else "neutral flows"
        return pts, reason


@dataclass
class SectorFPI:
    name: str
    aum_pct: float
    fortnight_cr: float
    one_year_cr: float
    last_date: str = ""
    fii_own: Optional[float] = None
    alpha: Optional[float] = None


def fetch_fii_dii(include_history: bool = True) -> Optional[FIIDIISnapshot]:
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


def fetch_sector_fpi() -> List[SectorFPI]:
    """NSDL fortnightly FPI sector allocation (when available)."""
    try:
        r = requests.get(API_SECTORS, timeout=15)
        r.raise_for_status()
        rows = r.json()
        out: List[SectorFPI] = []
        if not isinstance(rows, list):
            return out
        for row in rows:
            out.append(SectorFPI(
                name=str(row.get("name", "")),
                aum_pct=float(row.get("aumPct") or 0),
                fortnight_cr=float(row.get("fortnightCr") or 0),
                one_year_cr=float(row.get("oneYearCr") or 0),
                last_date=str(row.get("lastDate") or ""),
                fii_own=row.get("fiiOwn"),
                alpha=row.get("alpha"),
            ))
        # Sort by fortnight flow descending
        out.sort(key=lambda x: x.fortnight_cr, reverse=True)
        return out
    except Exception as e:
        logger.warning(f"Sector FPI fetch failed: {e}")
        return []


def match_sector_fpi(sector_key: str, sectors: List[SectorFPI]) -> Optional[SectorFPI]:
    keys = SECTOR_NAME_MAP.get(sector_key, [sector_key.replace("_", " ")])
    for s in sectors:
        name_l = s.name.lower()
        for k in keys:
            if k.lower() in name_l:
                return s
    return None


def sector_swing_adjustment(sector_key: str, sectors: List[SectorFPI]) -> Tuple[float, str]:
    """
    Extra swing points from sector FPI fortnight flow.
    Strong inflows → boost; strong outflows → penalise.
    """
    s = match_sector_fpi(sector_key, sectors)
    if not s:
        return 0.0, ""

    pts = 0.0
    if s.fortnight_cr >= 3000:
        pts = 4
        reason = f"FPI inflow {s.name} +{s.fortnight_cr:,.0f} Cr"
    elif s.fortnight_cr >= 1000:
        pts = 2
        reason = f"FPI inflow {s.name} +{s.fortnight_cr:,.0f} Cr"
    elif s.fortnight_cr <= -3000:
        pts = -4
        reason = f"FPI outflow {s.name} {s.fortnight_cr:,.0f} Cr"
    elif s.fortnight_cr <= -1000:
        pts = -2
        reason = f"FPI outflow {s.name} {s.fortnight_cr:,.0f} Cr"
    else:
        reason = f"FPI flat {s.name}"
        pts = 0
    return pts, reason


def format_fii_dii_section(snap: Optional[FIIDIISnapshot]) -> List[str]:
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
    bias_pts, bias_reason = snap.swing_bias_points()

    lines.append(f"• Date: <b>{snap.date}</b>")
    lines.append(f"• FII Net: {fii_emoji} <b>{fmt(snap.fii_net)}</b> ({snap.fii_bias})")
    lines.append(f"• DII Net: {dii_emoji} <b>{fmt(snap.dii_net)}</b> ({snap.dii_bias})")
    lines.append(f"• Tone: <i>{snap.overall_tone}</i>")
    lines.append(f"• Swing bias: <b>{bias_pts:+.0f}</b> pts ({bias_reason})")

    if snap.history_nets:
        recent = []
        for h in snap.history_nets[:3]:
            d = h.get("date", "")
            fn, dn = h.get("fii_net"), h.get("dii_net")
            if fn is None or dn is None:
                continue
            recent.append(f"{d}: FII {fmt(float(fn))} | DII {fmt(float(dn))}")
        if recent:
            lines.append("• Recent:")
            for r in recent:
                lines.append(f"  – {r}")
    lines.append("")
    return lines


def format_sector_fpi_section(sectors: List[SectorFPI], top_n: int = 6) -> List[str]:
    lines = ["<b>🌍 SECTOR FPI ALLOCATION</b>"]
    if not sectors:
        lines.append("• Sector FPI data unavailable")
        lines.append("")
        return lines

    lines.append("<i>Fortnight FPI flow (₹ Cr) – top inflows / outflows</i>")
    # Top inflows
    inflows = [s for s in sectors if s.fortnight_cr > 0][: top_n // 2 or 3]
    outflows = sorted([s for s in sectors if s.fortnight_cr < 0], key=lambda x: x.fortnight_cr)[: top_n // 2 or 3]

    if inflows:
        lines.append("• Inflows:")
        for s in inflows:
            lines.append(f"  🟢 {s.name}: +{s.fortnight_cr:,.0f} Cr (AUM {s.aum_pct:.1f}%)")
    if outflows:
        lines.append("• Outflows:")
        for s in outflows:
            lines.append(f"  🔴 {s.name}: {s.fortnight_cr:,.0f} Cr (AUM {s.aum_pct:.1f}%)")

    if sectors and sectors[0].last_date:
        lines.append(f"<i>As of {sectors[0].last_date}</i>")
    lines.append("")
    return lines
