"""
Profit Opportunity Scanner.

Reads existing StockScorecard layers + market context and lists
possible profitable stocks with clear reasons.

Sources combined:
  - Fresh Buys (Horizon + Minervini)
  - Horizon 🟢 / strong multi-week
  - Sector Rotation Leading/Improving
  - Hot Stocks (constructive, not only Extreme chase)
  - Multi-bagger candidates
  - FII/DII tone (boost/penalise)
  - Simple value-chain / theme links (EV, defence, pharma, banks, etc.)

Not guarantees — ranked opportunity list with reasons.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
import logging

logger = logging.getLogger(__name__)

# Theme → related sectors (value-chain / spillover)
THEME_LINKS: Dict[str, List[str]] = {
    "automobile_ev": ["automobile_ev", "metals_mining", "chemicals", "energy_oil_gas_power"],
    "defence_aerospace": ["defence_aerospace", "capital_goods_infra", "metals_mining"],
    "pharmaceuticals": ["pharmaceuticals", "chemicals"],
    "information_technology": ["information_technology", "telecom"],
    "banks_financials": ["banks_financials", "realty"],
    "metals_mining": ["metals_mining", "capital_goods_infra", "automobile_ev"],
    "capital_goods_infra": ["capital_goods_infra", "metals_mining", "energy_oil_gas_power"],
    "energy_oil_gas_power": ["energy_oil_gas_power", "capital_goods_infra"],
}


@dataclass
class Opportunity:
    symbol: str
    name: str
    score: float
    reasons: List[str] = field(default_factory=list)
    sectors: Set[str] = field(default_factory=set)
    action_hint: str = "WATCH"


def _add(
    bag: Dict[str, Opportunity],
    symbol: str,
    name: str,
    pts: float,
    reason: str,
    sector: str = "",
    hint: str = "",
):
    sym = (symbol or "").upper().strip()
    if not sym:
        return
    if sym not in bag:
        bag[sym] = Opportunity(symbol=sym, name=name or sym, score=0.0)
    o = bag[sym]
    o.score += pts
    if reason and reason not in o.reasons:
        o.reasons.append(reason)
    if sector:
        o.sectors.add(sector)
    if name and o.name == o.symbol:
        o.name = name
    if hint and o.action_hint == "WATCH":
        o.action_hint = hint
    if hint == "BUY" or (hint == "ACCUMULATE" and o.action_hint == "WATCH"):
        o.action_hint = hint


def collect_opportunities(limit: int = 18) -> Dict[str, Any]:
    bag: Dict[str, Opportunity] = {}
    prefer_sectors: Set[str] = set()
    fii_note = "mixed"
    fii_pts = 0.0

    # --- FII/DII ---
    try:
        from src.shared.fii_dii import fetch_fii_dii

        snap = fetch_fii_dii(include_history=False)
        if snap:
            fii_pts, fii_note = snap.swing_bias_points()
            fii_note = f"{snap.overall_tone} (Swing bias {fii_pts:+.0f})"
    except Exception as e:
        logger.warning("opp fii: %s", e)

    # --- Sector rotation → preferred themes ---
    try:
        from src.intelligence.sector_rotation import run_sector_rotation

        sr = run_sector_rotation()
        for s in sr.get("sectors") or []:
            if s.label.startswith("🟢") or s.label.startswith("🔵"):
                prefer_sectors.add(s.ss_sector)
                # spillover sectors
                for linked in THEME_LINKS.get(s.ss_sector, [s.ss_sector]):
                    prefer_sectors.add(linked)
    except Exception as e:
        logger.warning("opp sector: %s", e)

    # --- Fresh buys (highest weight) ---
    try:
        from src.intelligence.fresh_buys import collect_fresh_buys

        fb = collect_fresh_buys()
        for b in fb.get("buys") or []:
            pts = 25.0 + (10 if b.confidence == "High" else 5 if b.confidence == "Medium" else 0)
            pts += fii_pts * 0.3
            _add(
                bag,
                b.symbol,
                b.name,
                pts,
                f"Fresh Buy [{b.confidence}] · {b.horizon}",
                hint="BUY",
            )
            if b.detail:
                _add(bag, b.symbol, b.name, 0, b.detail[:80])
    except Exception as e:
        logger.warning("opp fresh: %s", e)

    # --- Horizon 🟢 ---
    try:
        from src.intelligence.horizon_monitor import run_horizon_monitor

        hz = run_horizon_monitor(max_rows=35)
        for r in hz.get("rows") or []:
            if r.action.startswith("🟢"):
                pts = 18.0 + (8 if r.confidence == "High" else 4)
                if r.sector in prefer_sectors:
                    pts += 8
                    reason_sec = f"In preferred sector ({r.sector})"
                else:
                    reason_sec = r.sector
                _add(
                    bag,
                    r.symbol,
                    r.name,
                    pts,
                    f"Horizon 🟢 {r.confidence} · {r.horizon_weeks}",
                    r.sector,
                    "BUY",
                )
                _add(bag, r.symbol, r.name, 0, reason_sec)
            elif r.action.startswith("🟡") and r.sector in prefer_sectors and not r.extended:
                _add(
                    bag,
                    r.symbol,
                    r.name,
                    8.0,
                    f"Horizon HOLD in strong sector · trail/pullback",
                    r.sector,
                    "ACCUMULATE",
                )
    except Exception as e:
        logger.warning("opp horizon: %s", e)

    # --- Hot (warm/hot only; extreme only if in prefer sector) ---
    try:
        from src.intelligence.hot_stocks import run_hot_stocks

        hot = run_hot_stocks(limit=20)
        for s in hot.get("stocks") or []:
            if s.heat.startswith("🔥"):
                if s.sector not in prefer_sectors:
                    continue
                _add(
                    bag,
                    s.symbol,
                    s.name,
                    6.0,
                    f"Extreme hot but sector preferred — pullback only",
                    s.sector,
                    "WATCH",
                )
            elif s.heat.startswith("♨️") or s.heat.startswith("🌶"):
                pts = 10.0 if s.sector in prefer_sectors else 5.0
                _add(
                    bag,
                    s.symbol,
                    s.name,
                    pts,
                    f"{s.heat} multi-month · {s.sector}",
                    s.sector,
                    "ACCUMULATE" if s.sector in prefer_sectors else "WATCH",
                )
    except Exception as e:
        logger.warning("opp hot: %s", e)

    # --- Multi-bagger candidates ---
    try:
        from src.intelligence.multibagger_screener import run_multibagger_screener

        mb = run_multibagger_screener(limit=12)
        for h in mb.get("hits") or []:
            pts = 12.0 if "Strong" in h.tier else 7.0
            if h.sector in prefer_sectors:
                pts += 6
            _add(
                bag,
                h.symbol,
                h.name,
                pts,
                f"Multi-bagger screen: {h.tier}",
                h.sector,
                "ACCUMULATE",
            )
    except Exception as e:
        logger.warning("opp multi: %s", e)

    # --- Value-chain bonus: symbols already in bag whose sector is linked to leaders ---
    for o in list(bag.values()):
        for sec in o.sectors:
            if sec in prefer_sectors:
                o.score += 3
                if "Preferred theme / value-chain" not in o.reasons:
                    o.reasons.append("Preferred theme / value-chain")
                break

    ranked = sorted(bag.values(), key=lambda x: -x.score)
    return {
        "scan_time": datetime.now(),
        "opportunities": ranked[:limit],
        "prefer_sectors": sorted(prefer_sectors),
        "fii_note": fii_note,
        "total": len(ranked),
    }


def format_profit_opportunity_telegram(result: Optional[Dict[str, Any]] = None) -> str:
    if result is None:
        result = collect_opportunities()
    now = result["scan_time"].strftime("%d %b %Y | %H:%M IST")
    opps: List[Opportunity] = result.get("opportunities") or []
    prefer = result.get("prefer_sectors") or []

    lines = [
        "<b>💰 PROFIT OPPORTUNITIES</b>",
        now,
        "",
        "<i>Combines Fresh Buys · Horizon · Sector · Hot · Multi-bagger · FII tone</i>",
        "<i>Possible profitable names — not guarantees. Use stops.</i>",
        "",
    ]

    if prefer:
        lines.append("<b>📊 Preferred themes (market + rotation)</b>")
        lines.append("• " + ", ".join(prefer[:8]))
        lines.append("")

    lines.append(f"<b>🏦 Flows:</b> <i>{result.get('fii_note', '—')}</i>")
    lines.append("")

    buys = [o for o in opps if o.action_hint == "BUY"]
    acc = [o for o in opps if o.action_hint == "ACCUMULATE"]
    watch = [o for o in opps if o.action_hint == "WATCH"]

    def block(title: str, items: List[Opportunity], n: int = 8):
        lines.append(f"<b>{title}</b>")
        if not items:
            lines.append("• —")
        else:
            for i, o in enumerate(items[:n], 1):
                why = "; ".join(o.reasons[:3])
                if len(why) > 120:
                    why = why[:117] + "…"
                lines.append(f"{i}. <b>{o.symbol}</b> – {o.name}")
                lines.append(f"   Score {o.score:.0f} · {why}")
        lines.append("")

    block("🟢 Higher conviction (act on setup)", buys)
    block("🟡 Accumulate / pullback", acc, 6)
    block("⚪ Watch only", watch, 5)

    lines.append(
        "<i>EV example: strong auto theme can lift battery/metals names in preferred list. "
        "StockScorecard – Profit Opportunities</i>"
    )
    return "\n".join(lines)
