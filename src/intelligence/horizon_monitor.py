"""
Horizon Monitor – multi-timeframe momentum + position policy.

Answers: buy / hold for X weeks / sell or avoid (extended).
Does NOT claim 95% accuracy — uses rule strength High/Med/Low + optional P≈.

Horizons (trading days approx):
  2W ~10d, 1M ~21d, 3M ~63d, 6M ~126d
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
import logging
import re

import pandas as pd

from src.data_fetch.prices import fetch_price_history
from src.intelligence.catalysts import build_catalyst_map, catalyst_for, format_price

logger = logging.getLogger(__name__)


@dataclass
class HorizonRow:
    symbol: str
    name: str
    sector: str
    price: float
    ret_2w: Optional[float]
    ret_1m: Optional[float]
    ret_3m: Optional[float]
    ret_6m: Optional[float]
    action: str  # BUY / HOLD / SELL_AVOID / WATCH
    horizon_weeks: str
    confidence: str  # High / Medium / Low
    reason: str
    extended: bool = False
    catalyst: str = ""


def _load_universe() -> List[Tuple[str, str, str]]:
    rows = []
    seen = set()
    for p in Path("src/sectors").glob("*.py"):
        text = p.read_text(errors="ignore")
        for m in re.finditer(r'\{"symbol":\s*"([^"]+)",\s*"name":\s*"([^"]+)"', text):
            sym, name = m.group(1), m.group(2)
            if sym not in seen:
                seen.add(sym)
                rows.append((sym, name, p.stem))
    return rows


def _rets(close: pd.Series) -> Dict[str, Optional[float]]:
    out: Dict[str, Optional[float]] = {"2w": None, "1m": None, "3m": None, "6m": None}
    n = len(close)
    last = float(close.iloc[-1])
    for key, days in [("2w", 10), ("1m", 21), ("3m", 63), ("6m", 126)]:
        if n > days:
            past = float(close.iloc[-days - 1])
            if past > 0:
                out[key] = (last / past - 1.0) * 100.0
    return out


def _policy(r: Dict[str, Optional[float]], symbol: str) -> Tuple[str, str, str, str, bool]:
    """
    Returns action, horizon_weeks, confidence, reason, extended.
    Extended = very strong 6M already; late entry risk high for fresh BUY.
    """
    r2, r1, r3, r6 = r.get("2w"), r.get("1m"), r.get("3m"), r.get("6m")
    extended = r6 is not None and r6 >= 80

    # Cooling: big 6M but weak recent
    cooling = (
        r6 is not None
        and r6 >= 50
        and r2 is not None
        and r2 < -3
        and (r3 is None or r3 < 5)
    )

    # Fresh multi-week strength without extreme extension
    fresh = (
        r2 is not None
        and r1 is not None
        and r2 >= 5
        and r1 >= 8
        and (r6 is None or r6 < 80)
    )

    # Trend intact intermediate
    trend_ok = r3 is not None and r3 >= 10 and r6 is not None and r6 >= 25

    if cooling:
        return (
            "🔴 SELL/AVOID",
            "0 – exit / trail",
            "Medium",
            "Strong past move but multi-week cooling — protect gains",
            extended,
        )

    if extended and r2 is not None and r2 < 2:
        return (
            "🟡 HOLD / TRAIL",
            "1–2 weeks max (tight trail)",
            "Low",
            f"Very extended (~{r6:.0f}% 6M) — no fresh BUY; trail only",
            True,
        )

    if extended and r2 is not None and r2 >= 5:
        return (
            "🟡 HOLD (extended)",
            "1–2 weeks",
            "Low",
            f"Still strong short-term but ~{r6:.0f}% 6M — late entry risk",
            True,
        )

    if fresh and trend_ok:
        return (
            "🟢 BUY",
            "2–4 weeks",
            "High",
            "Multi-week strength + intermediate trend; not extremely extended",
            False,
        )

    if fresh:
        return (
            "🟢 BUY",
            "1–3 weeks",
            "Medium",
            "Multi-week momentum constructive",
            False,
        )

    if trend_ok and (r2 is None or r2 >= -2):
        return (
            "🟡 HOLD",
            "2–4 weeks",
            "Medium",
            "Intermediate trend intact — hold / pullback buys only",
            extended,
        )

    if r6 is not None and r6 >= 45 and (r2 is None or r2 >= 0):
        return (
            "⚪ WATCH",
            "n/a",
            "Low",
            "Strong 6M history — wait for pullback or new base",
            extended,
        )

    return (
        "⚪ WATCH",
        "n/a",
        "Low",
        "No clear multi-week edge",
        extended,
    )


def run_horizon_monitor(max_rows: int = 25) -> Dict[str, Any]:
    universe = _load_universe()
    cmap = build_catalyst_map()
    rows: List[HorizonRow] = []

    for sym, name, sec in universe:
        try:
            df = fetch_price_history(sym + ".NS", period="1y")
            if df is None or len(df) < 30:
                continue
            cols = {c.lower(): c for c in df.columns}
            close_c = cols.get("close") or cols.get("adj close")
            if not close_c:
                continue
            close = df[close_c].astype(float)
            r = _rets(close)
            action, horizon, conf, reason, ext = _policy(r, sym)
            rows.append(
                HorizonRow(
                    symbol=sym,
                    name=name,
                    sector=sec,
                    price=float(close.iloc[-1]),
                    ret_2w=r.get("2w"),
                    ret_1m=r.get("1m"),
                    ret_3m=r.get("3m"),
                    ret_6m=r.get("6m"),
                    action=action,
                    horizon_weeks=horizon,
                    confidence=conf,
                    reason=reason,
                    extended=ext,
                    catalyst=catalyst_for(sym, name, sec, cmap),
                )
            )
        except Exception as e:
            logger.debug("horizon %s: %s", sym, e)

    # Sort: BUY first, then by 2w momentum, then 6m
    def rank(x: HorizonRow):
        pri = 0 if x.action.startswith("🟢") else 1 if x.action.startswith("🟡") else 2 if x.action.startswith("🔴") else 3
        return (pri, -(x.ret_2w or -999), -(x.ret_6m or -999))

    rows.sort(key=rank)
    return {
        "scan_time": datetime.now(),
        "rows": rows[:max_rows],
        "all_count": len(rows),
    }


def format_horizon_telegram(result: Optional[Dict[str, Any]] = None) -> str:
    if result is None:
        result = run_horizon_monitor()
    now = result["scan_time"].strftime("%d %b %Y | %H:%M IST")
    lines = [
        "<b>⏱ Horizon Monitor</b> – multi-week / multi-month",
        now,
        "",
        "<i>Buy / Hold X weeks / Sell — rule-based. Not 95% guarantees.</i>",
        "",
    ]

    buys = [r for r in result["rows"] if r.action.startswith("🟢")]
    holds = [r for r in result["rows"] if r.action.startswith("🟡")]
    sells = [r for r in result["rows"] if r.action.startswith("🔴")]
    watch = [r for r in result["rows"] if r.action.startswith("⚪")]

    def fmt(r: HorizonRow) -> str:
        parts = []
        if r.ret_2w is not None:
            parts.append(f"2W {r.ret_2w:+.0f}%")
        if r.ret_1m is not None:
            parts.append(f"1M {r.ret_1m:+.0f}%")
        if r.ret_6m is not None:
            parts.append(f"6M {r.ret_6m:+.0f}%")
        meta = " · ".join(parts)
        return (
            f"• <b>{r.symbol}</b> [{r.confidence}] hold {r.horizon_weeks}\n"
            f"  Price {format_price(r.price)} | {meta}\n"
            f"  📌 {r.catalyst}\n"
            f"  {r.reason}"
        )

    lines.append("<b>🟢 BUY (multi-week setup)</b>")
    if buys:
        for r in buys[:8]:
            lines.append(fmt(r))
    else:
        lines.append("• None — wait for fresh multi-week strength")
    lines.append("")

    lines.append("<b>🟡 HOLD / TRAIL</b>")
    if holds:
        for r in holds[:8]:
            lines.append(fmt(r))
    else:
        lines.append("• —")
    lines.append("")

    if sells:
        lines.append("<b>🔴 SELL / AVOID (cooling)</b>")
        for r in sells[:6]:
            lines.append(fmt(r))
        lines.append("")

    # Spotlight extended 6M names (OFSS-like)
    ext = [r for r in result["rows"] if r.extended or (r.ret_6m and r.ret_6m >= 45)]
    if ext:
        lines.append("<b>📈 Strong 6M names (often too extended for fresh BUY)</b>")
        for r in sorted(ext, key=lambda x: -(x.ret_6m or 0))[:12]:
            e = " EXT" if r.extended else ""
            lines.append(
                f"• {r.symbol} 6M {r.ret_6m:+.0f}% | 2W {r.ret_2w:+.0f}%{'' if r.ret_2w is not None else ''} | {r.action}{e}"
            )
        lines.append("")

    lines.append(
        "<i>Confidence = rule strength (High/Med/Low), not prediction accuracy. "
        "StockScorecard – Horizon Monitor</i>"
    )
    return "\n".join(lines)
