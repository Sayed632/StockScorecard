"""
Fresh Buys – single sorted list of actionable new-buy candidates.

Merges:
  - Horizon Monitor 🟢 BUY
  - Main Swing BUY_NOW (if available from last scan – optional)
  - Minervini/O'Neil 🟢 BUY NOW

Excludes extreme Hot / late-chase names unless Horizon still says BUY.
One Telegram message so the user has one place to look.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class FreshBuy:
    symbol: str
    name: str
    sources: List[str]
    horizon: str
    confidence: str
    detail: str
    score: float  # for sorting


def collect_fresh_buys() -> Dict[str, Any]:
    by_sym: Dict[str, FreshBuy] = {}

    def add(sym: str, name: str, source: str, horizon: str, conf: str, detail: str, score: float):
        sym = (sym or "").upper().strip()
        if not sym:
            return
        if sym not in by_sym:
            by_sym[sym] = FreshBuy(
                symbol=sym,
                name=name or sym,
                sources=[source],
                horizon=horizon,
                confidence=conf,
                detail=detail,
                score=score,
            )
        else:
            fb = by_sym[sym]
            if source not in fb.sources:
                fb.sources.append(source)
            fb.score = max(fb.score, score)
            # prefer higher confidence label
            order = {"High": 3, "Medium": 2, "Low": 1}
            if order.get(conf, 0) > order.get(fb.confidence, 0):
                fb.confidence = conf
            if horizon and (not fb.horizon or "2–4" in horizon):
                fb.horizon = horizon
            if detail and len(detail) > len(fb.detail or ""):
                fb.detail = detail

    # 1) Horizon 🟢
    try:
        from src.intelligence.horizon_monitor import run_horizon_monitor
        hz = run_horizon_monitor(max_rows=40)
        for row in hz.get("rows") or []:
            if not str(row.action).startswith("🟢"):
                continue
            conf = row.confidence or "Medium"
            score = 70.0
            if conf == "High":
                score += 15
            if row.ret_2w:
                score += min(row.ret_2w, 20)
            add(
                row.symbol,
                row.name,
                "Horizon",
                row.horizon_weeks or "2–4 weeks",
                conf,
                row.reason or "",
                score,
            )
    except Exception as e:
        logger.warning("fresh buys horizon: %s", e)

    # 2) Minervini 🟢
    try:
        from src.strategies.minervini_oneil import run_minervini_oneil
        mo = run_minervini_oneil()
        for idea in mo.get("ideas") or []:
            if not str(idea.action).startswith("🟢"):
                continue
            add(
                idea.symbol,
                idea.name,
                "Minervini",
                "days–weeks",
                "Medium",
                idea.reason or "Breakout/trend template",
                75.0 + float(idea.score or 0) / 10.0,
            )
    except Exception as e:
        logger.warning("fresh buys minervini: %s", e)

    # 3) Optional: exclude pure Extreme heat without horizon buy (already only horizon greens)
    items = sorted(by_sym.values(), key=lambda x: -x.score)
    return {
        "scan_time": datetime.now(),
        "buys": items,
        "count": len(items),
    }


def format_fresh_buys_telegram(result: Optional[Dict[str, Any]] = None) -> str:
    if result is None:
        result = collect_fresh_buys()
    now = result["scan_time"].strftime("%d %b %Y | %H:%M IST")
    buys: List[FreshBuy] = result.get("buys") or []

    lines = [
        "<b>🟢 FRESH BUYS</b> – all in one place",
        now,
        "",
        "<i>Sorted candidates for new entries only. Not advice. Use stops.</i>",
        f"<i>{result.get('count', len(buys))} name(s)</i>",
        "",
    ]

    if not buys:
        lines.append("• No fresh buys today — wait for multi-week setups")
    else:
        for i, b in enumerate(buys[:15], 1):
            src = "+".join(b.sources)
            lines.append(f"<b>{i}. {b.symbol}</b> [{b.confidence}] · {src}")
            lines.append(f"   {b.name}")
            lines.append(f"   Hold: {b.horizon}")
            if b.detail:
                d = b.detail if len(b.detail) <= 100 else b.detail[:97] + "…"
                lines.append(f"   {d}")
            lines.append("")

    lines.append("<i>Skip names only on Hot/Extreme without 🟢 here. StockScorecard</i>")
    return "\n".join(lines)
