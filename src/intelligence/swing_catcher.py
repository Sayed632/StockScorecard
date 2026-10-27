"""
Swing Catcher – primary "do not miss" engine for multi-day swing candidates.

Purpose (user requirement):
  Scan as wide a universe as practical in parallel and surface stocks that
  are entering or continuing a swing move — before they only show as
  parabolic charts on the phone.

Design:
  1) Full merged universe (NSE master + yaml + sectors + IPO + force list)
  2) Parallel light scan (returns, volume, structure)
  3) Rank into:
       🟢 ACTIONABLE SWING  – trend + volume, not fully extended
       👀 BUILDING         – early momentum, watch for trigger
       🔥 EXTENDED         – already ran hard (list for awareness, not chase)

Honest limits: batch jobs, not tick-by-tick; Yahoo rate limits; still need stops.
"""

from __future__ import annotations

from src.shared.time_ist import format_ist, now_ist

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import logging
import math
import os

from src.data_fetch.prices import fetch_price_history
from src.data_fetch.nse_universe import load_merged_universe

logger = logging.getLogger(__name__)

MAX_WORKERS = int(os.getenv("SWING_CATCHER_WORKERS", "22"))
# Cap keeps GH Actions under time limits; raise via env if self-hosted
MAX_SYMBOLS = int(os.getenv("SWING_CATCHER_MAX", "1500"))
TOP_N = 15


@dataclass
class SwingPick:
    symbol: str
    name: str
    price: float
    ret_1d: float
    ret_5d: float
    ret_10d: float
    vol_ratio: float
    near_high_pct: float
    score: float
    bucket: str  # ACTIONABLE | BUILDING | EXTENDED
    reasons: List[str]


def _ret(close, days: int) -> Optional[float]:
    if close is None or len(close) <= days:
        return None
    past = float(close.iloc[-days - 1])
    cur = float(close.iloc[-1])
    if past <= 0 or math.isnan(past) or math.isnan(cur):
        return None
    return (cur / past - 1.0) * 100.0


def _analyse(symbol: str, name: str) -> Optional[SwingPick]:
    try:
        df = fetch_price_history(f"{symbol}.NS", period="6mo")
        if df is None or len(df) < 25:
            df = fetch_price_history(f"{symbol}.BO", period="6mo")
        if df is None or len(df) < 25:
            return None

        close = df["close"].astype(float).dropna()
        if len(close) < 25:
            return None
        px = float(close.iloc[-1])
        if px <= 0 or math.isnan(px):
            return None

        r1 = _ret(close, 1) or 0.0
        r5 = _ret(close, 5)
        r10 = _ret(close, 10)
        if r5 is None or r10 is None:
            return None

        # Minimum swing-like activity
        if r5 < 2.0 and r1 < 1.5 and r10 < 3.0:
            return None

        high60 = float(close.tail(min(60, len(close))).max())
        near = ((high60 - px) / high60 * 100.0) if high60 > 0 else 99.0

        vol_ratio = 1.0
        if "volume" in df.columns:
            vol = df["volume"].astype(float).dropna()
            if len(vol) >= 25:
                avg = float(vol.tail(20).mean())
                recent = float(vol.tail(3).mean())
                if avg > 0:
                    vol_ratio = recent / avg

        ma20 = float(close.tail(20).mean())
        above_ma = px >= ma20 * 0.98

        low5 = float(close.tail(5).min())
        low_prior = float(close.iloc[-10:-5].min()) if len(close) >= 10 else low5
        higher_low = low5 >= low_prior * 0.97

        reasons: List[str] = []
        score = 35.0

        score += max(-12, min(22, r5 * 1.6))
        score += max(-8, min(12, r10 * 0.55))
        score += max(-6, min(14, r1 * 1.2))

        if vol_ratio >= 1.5:
            score += 14
            reasons.append(f"Vol x{vol_ratio:.1f}")
        elif vol_ratio >= 1.15:
            score += 7
            reasons.append(f"Vol x{vol_ratio:.1f}")

        if near <= 3:
            score += 12
            reasons.append("Near 60D high")
        elif near <= 8:
            score += 6
            reasons.append(f"{near:.0f}% off high")

        if above_ma:
            score += 8
            reasons.append("Above 20DMA")
        if higher_low:
            score += 6
            reasons.append("Higher-low")

        if r5 > 0 and r10 > 0:
            score += 6
            reasons.append("5D+10D green")

        # Bucket
        if r10 >= 20 or r5 >= 14 or (r1 >= 8 and r5 >= 8):
            bucket = "EXTENDED"
            score -= 10
            reasons.append("Extended – do not chase blindly")
        elif (
            r5 >= 3.5
            and above_ma
            and vol_ratio >= 1.1
            and near <= 12
            and r10 < 18
        ):
            bucket = "ACTIONABLE"
            reasons.append("Swing structure")
        elif r5 >= 2.0 or (r1 >= 2.5 and vol_ratio >= 1.2):
            bucket = "BUILDING"
            reasons.append("Building momentum")
        else:
            return None

        if score < 52:
            return None

        return SwingPick(
            symbol=symbol,
            name=name,
            price=px,
            ret_1d=r1,
            ret_5d=r5,
            ret_10d=r10,
            vol_ratio=vol_ratio,
            near_high_pct=near,
            score=score,
            bucket=bucket,
            reasons=reasons[:5],
        )
    except Exception as e:
        logger.debug("swing_catcher %s: %s", symbol, e)
        return None


def run_swing_catcher(max_symbols: Optional[int] = None) -> Dict[str, Any]:
    cap = max_symbols or MAX_SYMBOLS
    symbols = load_merged_universe()[:cap]
    hits: List[SwingPick] = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(_analyse, s, n): s for s, n in symbols}
        for fut in as_completed(futs):
            try:
                row = fut.result()
                if row:
                    hits.append(row)
            except Exception:
                pass

    hits.sort(key=lambda x: -x.score)
    actionable = [h for h in hits if h.bucket == "ACTIONABLE"]
    building = [h for h in hits if h.bucket == "BUILDING"]
    extended = [h for h in hits if h.bucket == "EXTENDED"]

    return {
        "scan_time": now_ist(),
        "scanned": len(symbols),
        "actionable": actionable[:TOP_N],
        "building": building[:TOP_N],
        "extended": extended[:10],
        "total_hits": len(hits),
    }


def format_swing_catcher_telegram(result: Optional[Dict[str, Any]] = None) -> str:
    if result is None:
        result = run_swing_catcher()
    now = format_ist(result.get("scan_time"))
    lines = [
        "<b>🎯 SWING CATCHER – Do Not Miss</b>",
        now,
        f"<i>Scanned {result.get('scanned', 0)} names · "
        f"{result.get('total_hits', 0)} passed filters</i>",
        "",
        "<b>🟢 ACTIONABLE SWING</b>",
    ]
    act = result.get("actionable") or []
    if not act:
        lines.append("• None clear right now")
    else:
        for h in act[:10]:
            lines.append(
                f"• <b>{h.symbol}</b> ₹{h.price:.1f} · "
                f"1D {h.ret_1d:+.1f}% · 5D {h.ret_5d:+.1f}% · 10D {h.ret_10d:+.1f}%"
            )
            lines.append(f"   {', '.join(h.reasons)}")

    lines.append("")
    lines.append("<b>👀 BUILDING (watch)</b>")
    bld = result.get("building") or []
    if not bld:
        lines.append("• —")
    else:
        for h in bld[:8]:
            lines.append(
                f"• <b>{h.symbol}</b> ₹{h.price:.1f} · 5D {h.ret_5d:+.1f}% · "
                f"vol x{h.vol_ratio:.1f}"
            )

    lines.append("")
    lines.append("<b>🔥 EXTENDED (awareness only – high chase risk)</b>")
    ext = result.get("extended") or []
    if not ext:
        lines.append("• —")
    else:
        for h in ext[:6]:
            lines.append(
                f"• <b>{h.symbol}</b> · 5D {h.ret_5d:+.1f}% · 10D {h.ret_10d:+.1f}%"
            )

    lines.append("")
    lines.append(
        "<i>Purpose: reduce missed multi-day swings. Not advice. "
        "Use stops. Prefer ACTIONABLE over EXTENDED. StockScorecard</i>"
    )
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3900] + "\n\n… (truncated)"
    return text
