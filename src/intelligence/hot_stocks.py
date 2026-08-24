"""
Hot Stocks – separate list of strong multi-month momentum names.

These are NOT automatic BUY signals. Many are extended.
Purpose: surface OFSS-like / HFCL-like movers so they are never "missed".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
import logging
import re

from src.data_fetch.prices import fetch_price_history

logger = logging.getLogger(__name__)

# Thresholds for "Hot"
HOT_6M_MIN = 45.0  # % over ~6 months
HOT_3M_MIN = 25.0  # alternative if 6M data weak but 3M strong


@dataclass
class HotStock:
    symbol: str
    name: str
    sector: str
    price: float
    ret_2w: Optional[float]
    ret_1m: Optional[float]
    ret_3m: Optional[float]
    ret_6m: Optional[float]
    heat: str  # 🔥 Extreme / ♨️ Hot / 🌶 Warm
    note: str


def _universe() -> List[Tuple[str, str, str]]:
    out, seen = [], set()
    for p in Path("src/sectors").glob("*.py"):
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


def run_hot_stocks(limit: int = 20) -> Dict[str, Any]:
    hot: List[HotStock] = []
    for sym, name, sec in _universe():
        try:
            df = fetch_price_history(sym + ".NS", period="1y")
            if df is None or len(df) < 40:
                continue
            cols = {c.lower(): c for c in df.columns}
            ccol = cols.get("close") or cols.get("adj close")
            if not ccol:
                continue
            close = df[ccol].astype(float)
            r2 = _ret(close, 10)
            r1 = _ret(close, 21)
            r3 = _ret(close, 63)
            r6 = _ret(close, 126)
            if r6 is None and r3 is None:
                continue
            # Qualify
            if r6 is not None and r6 >= HOT_6M_MIN:
                pass
            elif r3 is not None and r3 >= HOT_3M_MIN and (r6 is None or r6 >= 20):
                pass
            else:
                continue

            if r6 is not None and r6 >= 100:
                heat = "🔥 Extreme"
                note = "Very extended — monitor only, not a fresh buy"
            elif r6 is not None and r6 >= 70:
                heat = "♨️ Hot"
                note = "Strong 6M trend — trail/watch, late entry risk"
            else:
                heat = "🌶 Warm"
                note = "Elevated multi-month momentum"

            # recent cooling note
            if r2 is not None and r2 < -5:
                note += " | 2W cooling"

            hot.append(
                HotStock(
                    symbol=sym,
                    name=name,
                    sector=sec,
                    price=float(close.iloc[-1]),
                    ret_2w=r2,
                    ret_1m=r1,
                    ret_3m=r3,
                    ret_6m=r6,
                    heat=heat,
                    note=note,
                )
            )
        except Exception as e:
            logger.debug("hot %s: %s", sym, e)

    hot.sort(key=lambda x: -(x.ret_6m if x.ret_6m is not None else x.ret_3m or 0))
    return {"scan_time": datetime.now(), "stocks": hot[:limit], "total_hot": len(hot)}


def format_hot_telegram(result: Optional[Dict[str, Any]] = None) -> str:
    if result is None:
        result = run_hot_stocks()
    now = result["scan_time"].strftime("%d %b %Y | %H:%M IST")
    lines = [
        "<b>🔥 HOT STOCKS</b> – strong multi-month movers",
        now,
        "",
        "<i>Separate list (OFSS-like). Not automatic BUY signals.</i>",
        f"<i>Found {result.get('total_hot', len(result['stocks']))} hot names in universe.</i>",
        "",
    ]
    stocks: List[HotStock] = result.get("stocks") or []
    if not stocks:
        lines.append("• No hot stocks above threshold right now")
    else:
        for s in stocks:
            parts = []
            if s.ret_6m is not None:
                parts.append(f"6M {s.ret_6m:+.0f}%")
            if s.ret_3m is not None:
                parts.append(f"3M {s.ret_3m:+.0f}%")
            if s.ret_2w is not None:
                parts.append(f"2W {s.ret_2w:+.0f}%")
            meta = " · ".join(parts)
            lines.append(f"• {s.heat} <b>{s.symbol}</b> – {s.name}")
            lines.append(f"  {meta} | {s.sector}")
            lines.append(f"  {s.note}")
    lines.append("")
    lines.append("<i>Use Horizon Monitor for buy/hold/sell. Hot list = visibility only.</i>")
    lines.append("<i>StockScorecard – Hot Stocks</i>")
    return "\n".join(lines)
