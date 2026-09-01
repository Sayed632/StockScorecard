"""
Early Move Alert – scan for stocks that *may* be set up before a larger move.

Combines:
  - Multi-week performance (2W / 1M constructive, not fully extended)
  - Price near recent highs (breakout zone) with volume expansion
  - Quarterly / results catalysts (NSE announcements + news keywords)

Honest limit: this is an early-warning screen, NOT a guarantee of price increase.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging
import math
import re

from src.data_fetch.prices import fetch_price_history
from src.intelligence.catalysts import format_price, catalyst_for, build_catalyst_map

logger = logging.getLogger(__name__)


@dataclass
class EarlyAlert:
    symbol: str
    name: str
    sector: str
    price: float
    score: float
    ret_2w: Optional[float]
    ret_1m: Optional[float]
    near_high_pct: Optional[float]  # distance to 60d high, 0 = at high
    vol_ratio: Optional[float]  # recent vol / avg vol
    reasons: List[str]
    results_flag: bool


def _universe() -> List[Tuple[str, str, str]]:
    out, seen = [], set()
    for p in Path("src/sectors").glob("*.py"):
        if p.name.startswith("penny"):
            continue
        text = p.read_text(errors="ignore")
        for m in re.finditer(r'\{"symbol":\s*"([^"]+)",\s*"name":\s*"([^"]+)"', text):
            if m.group(1) not in seen:
                seen.add(m.group(1))
                out.append((m.group(1), m.group(2), p.stem))
    return out


def _ret(close, days: int) -> Optional[float]:
    if len(close) <= days:
        return None
    past = float(close.iloc[-days - 1])
    if past <= 0 or math.isnan(past):
        return None
    cur = float(close.iloc[-1])
    if math.isnan(cur):
        return None
    return (cur / past - 1.0) * 100.0


def _results_symbols() -> set:
    """Symbols mentioned in recent results-related news / NSE high-impact text."""
    found: set = set()
    try:
        from src.intelligence.nse_announcements import fetch_recent_announcements

        rows = fetch_recent_announcements(limit=40) or []
        for r in rows:
            subj = (r.get("subject") or r.get("desc") or "").lower()
            if any(k in subj for k in ("result", "financial", "quarter", "earnings", "profit")):
                sym = (r.get("symbol") or r.get("sm_symbol") or "").upper().strip()
                if sym:
                    found.add(sym)
    except Exception as e:
        logger.debug("nse results symbols: %s", e)

    try:
        from src.intelligence.news_layer import collect_news_items

        items = collect_news_items(max_items=30) or []
        for it in items:
            title = (getattr(it, "title", None) or (it.get("title") if isinstance(it, dict) else "") or "").lower()
            if any(k in title for k in ("result", "quarter", "earnings", "q1", "q2", "q3", "q4", "profit")):
                # crude ticker match from title words
                for word in re.findall(r"\b[A-Z]{2,12}\b", getattr(it, "title", None) or (it.get("title") if isinstance(it, dict) else "") or ""):
                    if len(word) >= 3:
                        found.add(word)
    except Exception as e:
        logger.debug("news results symbols: %s", e)
    return found


def run_early_move_alert(limit: int = 12) -> Dict[str, Any]:
    cmap = build_catalyst_map()
    results_syms = _results_symbols()
    alerts: List[EarlyAlert] = []

    for sym, name, sec in _universe():
        try:
            df = fetch_price_history(sym + ".NS", period="6mo")
            if df is None or len(df) < 40:
                continue
            close = df["close"].astype(float).dropna()
            if len(close) < 40:
                continue
            px = float(close.iloc[-1])
            if math.isnan(px) or px <= 0:
                continue

            r2 = _ret(close, 10)
            r1 = _ret(close, 21)
            # skip already extreme runners (chasing)
            if r1 is not None and r1 > 45:
                continue
            # want constructive, not collapsing
            if r2 is not None and r2 < -8:
                continue

            window = close.iloc[-60:] if len(close) >= 60 else close
            hi = float(window.max())
            if hi <= 0 or math.isnan(hi):
                continue
            near_high = (hi - px) / hi * 100.0  # 0 = at high

            vol_ratio = None
            if "volume" in df.columns:
                vol = df["volume"].astype(float).dropna()
                if len(vol) >= 25:
                    avg = float(vol.iloc[-25:-5].mean()) if len(vol) >= 25 else float(vol.mean())
                    recent = float(vol.iloc[-5:].mean())
                    if avg > 0:
                        vol_ratio = recent / avg

            score = 0.0
            reasons: List[str] = []

            # Near 60d high (setup / breakout zone)
            if near_high <= 3:
                score += 25
                reasons.append(f"Within {near_high:.1f}% of 60d high")
            elif near_high <= 7:
                score += 15
                reasons.append(f"Near highs ({near_high:.1f}% below 60d high)")

            # Constructive multi-week performance
            if r2 is not None and 0 <= r2 <= 15:
                score += 12
                reasons.append(f"2W +{r2:.0f}% (steady, not blow-off)")
            if r1 is not None and 5 <= r1 <= 30:
                score += 15
                reasons.append(f"1M +{r1:.0f}% constructive trend")

            # Volume expansion
            if vol_ratio is not None and vol_ratio >= 1.4:
                score += 12
                reasons.append(f"Volume expanding ({vol_ratio:.1f}x avg)")

            # Results / quarterly catalyst
            results_flag = sym.upper() in results_syms or any(
                sym.upper() in s for s in results_syms
            )
            if results_flag:
                score += 18
                reasons.append("Results / quarterly catalyst in recent flow")

            # Sector preference mild boost
            if sec in ("defence_aerospace", "pharmaceuticals", "information_technology", "capital_goods_infra", "banks_financials"):
                score += 4

            if score < 28 or not reasons:
                continue

            alerts.append(
                EarlyAlert(
                    symbol=sym,
                    name=name,
                    sector=sec,
                    price=px,
                    score=score,
                    ret_2w=r2,
                    ret_1m=r1,
                    near_high_pct=near_high,
                    vol_ratio=vol_ratio,
                    reasons=reasons[:4],
                    results_flag=results_flag,
                )
            )
        except Exception as e:
            logger.debug("early %s: %s", sym, e)

    alerts.sort(key=lambda a: -a.score)
    return {
        "scan_time": datetime.now(),
        "alerts": alerts[:limit],
        "total": len(alerts),
        "results_hits": len(results_syms),
    }


def format_early_move_telegram(result: Optional[Dict[str, Any]] = None) -> str:
    if result is None:
        result = run_early_move_alert()
    now = result["scan_time"].strftime("%d %b %Y | %H:%M IST")
    alerts: List[EarlyAlert] = result.get("alerts") or []

    lines = [
        "<b>⚡ EARLY MOVE ALERTS</b>",
        now,
        "",
        "<i>Setups that may move soon — performance + results catalysts.</i>",
        "<i>Not a guarantee of price increase. Use stops.</i>",
        "",
    ]

    if not alerts:
        lines.append("• No early setups above threshold today")
    else:
        for i, a in enumerate(alerts, 1):
            tag = " 📰 Results" if a.results_flag else ""
            parts = []
            if a.ret_2w is not None:
                parts.append(f"2W {a.ret_2w:+.0f}%")
            if a.ret_1m is not None:
                parts.append(f"1M {a.ret_1m:+.0f}%")
            meta = " · ".join(parts) if parts else "—"
            lines.append(f"{i}. <b>{a.symbol}</b> – {a.name}{tag}")
            lines.append(f"   Price {format_price(a.price)} | {meta} | score {a.score:.0f}")
            for r in a.reasons[:3]:
                lines.append(f"   • {r}")
            lines.append(f"   Sector: {a.sector}")

    lines.append("")
    lines.append(
        f"<i>Scanned for near-high + volume + results flags "
        f"({result.get('results_hits', 0)} results-linked symbols in news/NSE). "
        "StockScorecard</i>"
    )
    return "\n".join(lines)
