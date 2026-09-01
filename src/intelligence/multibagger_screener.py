"""
Multi-Bagger Candidates Screener.

Looks for stocks that *could* compound if trends persist — NOT guaranteed multi-baggers.

Heuristic screen:
  - Prefer mid/small (exclude mega large prices as proxy when mcap missing)
  - Strong 6M and positive 3M momentum
  - Not Extreme-hot only (already ran 200%+) unless still constructive 2W
  - Price not in pure penny band (those go to penny screener)

Label as candidates with risk note.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging
import math
import re

from src.data_fetch.prices import fetch_price_history
from src.intelligence.catalysts import format_price, catalyst_for, build_catalyst_map

logger = logging.getLogger(__name__)

MIN_PRICE = 50.0  # leave true pennies to penny screener
MAX_PRICE = 8000.0  # avoid ultra expensive single-names dominating


@dataclass
class MultiHit:
    symbol: str
    name: str
    sector: str
    price: float
    ret_2w: Optional[float]
    ret_3m: Optional[float]
    ret_6m: Optional[float]
    score: float
    tier: str  # Strong candidate / Watch
    note: str
    catalyst: str = ""


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
    if past <= 0:
        return None
    return (float(close.iloc[-1]) / past - 1.0) * 100.0


def run_multibagger_screener(limit: int = 15) -> Dict[str, Any]:
    cmap = build_catalyst_map()
    hits: List[MultiHit] = []

    for sym, name, sec in _universe():
        try:
            df = fetch_price_history(sym + ".NS", period="1y")
            if df is None or len(df) < 100:
                continue
            cols = {c.lower(): c for c in df.columns}
            ccol = cols.get("close") or cols.get("adj close")
            if not ccol:
                continue
            close = df[ccol].astype(float).dropna()
            if len(close) < 100:
                continue
            px = float(close.iloc[-1])
            if math.isnan(px) or math.isinf(px) or px < MIN_PRICE or px > MAX_PRICE:
                continue

            r2 = _ret(close, 10)
            r3 = _ret(close, 63)
            r6 = _ret(close, 126)
            if r6 is None or (isinstance(r6, float) and math.isnan(r6)) or r6 < 35:
                continue
            if r3 is not None and r3 < -5:
                continue

            score = (r6 or 0) * 0.5 + max(r3 or 0, 0) * 0.35 + max(r2 or 0, 0) * 0.15
            # Prefer defence / growth sectors slightly
            if sec in ("defence_aerospace", "pharmaceuticals", "information_technology", "capital_goods_infra"):
                score += 5

            if r6 >= 70 and (r2 is None or r2 >= 0):
                tier = "🚀 Strong candidate"
                note = "Powerful multi-month trend — still needs pullback/setup to enter"
            elif r6 >= 45:
                tier = "📈 Watch / accumulate zone"
                note = "Elevated 6M strength — wait for base or Horizon 🟢"
            else:
                tier = "👁 Early watch"
                note = "Building multi-month profile"

            if r6 >= 120:
                note += " | Already extended — risk of sharp mean reversion"

            hits.append(
                MultiHit(
                    symbol=sym,
                    name=name,
                    sector=sec,
                    price=px,
                    ret_2w=r2,
                    ret_3m=r3,
                    ret_6m=r6,
                    score=score,
                    tier=tier,
                    note=note,
                    catalyst=catalyst_for(sym, name, sec, cmap),
                )
            )
        except Exception as e:
            logger.debug("multi %s: %s", sym, e)

    hits.sort(key=lambda x: -x.score)
    return {"scan_time": datetime.now(), "hits": hits[:limit], "total": len(hits)}


def format_multibagger_telegram(result: Optional[Dict[str, Any]] = None) -> str:
    if result is None:
        result = run_multibagger_screener()
    now = result["scan_time"].strftime("%d %b %Y | %H:%M IST")
    hits: List[MultiHit] = result.get("hits") or []
    lines = [
        "<b>🚀 MULTI-BAGGER CANDIDATES</b>",
        now,
        "",
        "<i>Heuristic screen (strong multi-month). Not guaranteed multi-baggers.</i>",
        f"<i>{result.get('total', len(hits))} matches · top {len(hits)}</i>",
        "",
    ]
    if not hits:
        lines.append("• No candidates above threshold today")
    else:
        for h in hits:
            parts = []
            def _ok(v):
                return v is not None and not (isinstance(v, float) and math.isnan(v))
            if _ok(h.ret_6m):
                parts.append(f"6M {h.ret_6m:+.0f}%")
            if _ok(h.ret_3m):
                parts.append(f"3M {h.ret_3m:+.0f}%")
            if _ok(h.ret_2w):
                parts.append(f"2W {h.ret_2w:+.0f}%")
            meta = " · ".join(parts)
            lines.append(f"• {h.tier} <b>{h.symbol}</b> – {h.name}")
            lines.append(f"  Price {format_price(h.price)} | {meta}")
            lines.append(f"  Sector: {h.sector}")
            lines.append(f"  📌 {h.catalyst}")
            lines.append(f"  {h.note}")
    lines.append("")
    lines.append(
        "<i>Enter only with setup + stop. Prefer Horizon 🟢 / Fresh Buys. StockScorecard</i>"
    )
    return "\n".join(lines)
