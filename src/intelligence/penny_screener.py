"""
Penny Stocks Screener – dedicated high-risk list.

Criteria (approx):
  - Last price under PENNY_PRICE_MAX (default ₹50)
  - Optional: also include names under ₹100 with micro momentum
  - Prefer positive 2W/1M and non-trivial volume trend when available

NOT investment advice. High risk of total loss.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging
import re

from src.data_fetch.prices import fetch_price_history
from src.intelligence.catalysts import format_price, catalyst_for, build_catalyst_map

logger = logging.getLogger(__name__)

PENNY_PRICE_MAX = 50.0
NEAR_PENNY_MAX = 100.0  # secondary band


@dataclass
class PennyHit:
    symbol: str
    name: str
    sector: str
    price: float
    ret_2w: Optional[float]
    ret_1m: Optional[float]
    ret_3m: Optional[float]
    score: float
    band: str  # Penny / Near-penny
    note: str
    catalyst: str = ""


def _universe() -> List[Tuple[str, str, str]]:
    out, seen = [], set()
    # Prefer penny_monitor list first
    pm = Path("src/sectors/penny_monitor.py")
    if pm.exists():
        text = pm.read_text(errors="ignore")
        for m in re.finditer(r'\{"symbol":\s*"([^"]+)",\s*"name":\s*"([^"]+)"', text):
            if m.group(1) not in seen:
                seen.add(m.group(1))
                out.append((m.group(1), m.group(2), "penny_monitor"))
    for p in Path("src/sectors").glob("*.py"):
        if p.name == "penny_monitor.py":
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
    if past <= 0:
        return None
    return (float(close.iloc[-1]) / past - 1.0) * 100.0


def run_penny_screener(limit: int = 15) -> Dict[str, Any]:
    cmap = build_catalyst_map()
    hits: List[PennyHit] = []

    for sym, name, sec in _universe():
        try:
            df = fetch_price_history(sym + ".NS", period="6mo")
            if df is None or len(df) < 25:
                continue
            cols = {c.lower(): c for c in df.columns}
            ccol = cols.get("close") or cols.get("adj close")
            if not ccol:
                continue
            close = df[ccol].astype(float)
            px = float(close.iloc[-1])
            if px <= 0 or px > NEAR_PENNY_MAX:
                continue

            r2, r1, r3 = _ret(close, 10), _ret(close, 21), _ret(close, 63)
            score = 0.0
            if r2 is not None:
                score += max(min(r2, 25), -10)
            if r1 is not None:
                score += max(min(r1, 30), -15) * 0.7
            if r3 is not None and r3 > 0:
                score += min(r3, 40) * 0.3
            if px <= PENNY_PRICE_MAX:
                band = "🪙 Penny"
                score += 5
            else:
                band = "🪙 Near-penny"
                score += 1

            note = "High risk — liquidity & governance risk elevated"
            if r2 is not None and r2 >= 8 and (r1 is None or r1 >= 0):
                note = "Short-term momentum in penny band — still high risk"
            elif r1 is not None and r1 < -10:
                note = "Weak recent trend — avoid chasing"

            hits.append(
                PennyHit(
                    symbol=sym,
                    name=name,
                    sector=sec,
                    price=px,
                    ret_2w=r2,
                    ret_1m=r1,
                    ret_3m=r3,
                    score=score,
                    band=band,
                    note=note,
                    catalyst=catalyst_for(sym, name, sec, cmap),
                )
            )
        except Exception as e:
            logger.debug("penny %s: %s", sym, e)

    hits.sort(key=lambda x: -x.score)
    return {"scan_time": datetime.now(), "hits": hits[:limit], "total": len(hits)}


def format_penny_telegram(result: Optional[Dict[str, Any]] = None) -> str:
    if result is None:
        result = run_penny_screener()
    now = result["scan_time"].strftime("%d %b %Y | %H:%M IST")
    hits: List[PennyHit] = result.get("hits") or []
    lines = [
        "<b>🪙 PENNY STOCKS SCREENER</b>",
        now,
        "",
        f"<i>Price ≤ ₹{NEAR_PENNY_MAX:.0f} (true penny ≤ ₹{PENNY_PRICE_MAX:.0f}). Very high risk.</i>",
        f"<i>{result.get('total', len(hits))} matches · showing top {len(hits)}</i>",
        "",
    ]
    if not hits:
        lines.append("• No names in penny price band with data today")
    else:
        for h in hits:
            parts = []
            if h.ret_2w is not None:
                parts.append(f"2W {h.ret_2w:+.0f}%")
            if h.ret_1m is not None:
                parts.append(f"1M {h.ret_1m:+.0f}%")
            meta = " · ".join(parts) if parts else "—"
            lines.append(f"• {h.band} <b>{h.symbol}</b> – {h.name}")
            lines.append(f"  Price {format_price(h.price)} | {meta}")
            lines.append(f"  📌 {h.catalyst}")
            lines.append(f"  {h.note}")
    lines.append("")
    lines.append("<i>Not advice. Size small or skip. StockScorecard</i>")
    return "\n".join(lines)
