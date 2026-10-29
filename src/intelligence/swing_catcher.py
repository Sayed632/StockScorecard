"""
Swing Catcher – primary "do not miss" engine for multi-day swing candidates.

Purpose: wide parallel scan → surface swing/rally candidates.
Relaxed thresholds so quiet market days still produce a useful shortlist.
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

MAX_WORKERS = int(os.getenv("SWING_CATCHER_WORKERS", "24"))
MAX_SYMBOLS = int(os.getenv("SWING_CATCHER_MAX", "2200"))
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
    bucket: str
    reasons: List[str]


def _ret(close, days: int) -> Optional[float]:
    if close is None or len(close) <= days:
        return None
    past = float(close.iloc[-days - 1])
    cur = float(close.iloc[-1])
    if past <= 0 or math.isnan(past) or math.isnan(cur):
        return None
    return (cur / past - 1.0) * 100.0


def _analyse(symbol: str, name: str) -> Tuple[Optional[SwingPick], str]:
    """Returns (pick|None, status) status: ok|no_data|flat|low_score"""
    try:
        df = fetch_price_history(f"{symbol}.NS", period="6mo")
        if df is None or len(df) < 20:
            df = fetch_price_history(f"{symbol}.BO", period="6mo")
        if df is None or len(df) < 20:
            return None, "no_data"

        close = df["close"].astype(float).dropna()
        if len(close) < 20:
            return None, "no_data"
        px = float(close.iloc[-1])
        if px <= 0 or math.isnan(px):
            return None, "no_data"

        r1 = _ret(close, 1) or 0.0
        r5 = _ret(close, 5)
        r10 = _ret(close, 10)
        if r5 is None:
            r5 = 0.0
        if r10 is None:
            r10 = 0.0

        # Very weak names only – keep modest movers
        if r5 < 0.8 and r1 < 1.0 and r10 < 1.5:
            return None, "flat"

        high60 = float(close.tail(min(60, len(close))).max())
        near = ((high60 - px) / high60 * 100.0) if high60 > 0 else 99.0

        vol_ratio = 1.0
        if "volume" in df.columns:
            vol = df["volume"].astype(float).dropna()
            if len(vol) >= 20:
                avg = float(vol.tail(20).mean())
                recent = float(vol.tail(3).mean())
                if avg > 0:
                    vol_ratio = recent / avg

        ma20 = float(close.tail(20).mean())
        above_ma = px >= ma20 * 0.97

        reasons: List[str] = []
        score = 40.0
        score += max(-15, min(25, r5 * 2.0))
        score += max(-10, min(15, r10 * 0.6))
        score += max(-8, min(18, r1 * 1.5))

        if vol_ratio >= 1.3:
            score += 12
            reasons.append(f"Vol x{vol_ratio:.1f}")
        elif vol_ratio >= 1.05:
            score += 5
            reasons.append(f"Vol x{vol_ratio:.1f}")

        if near <= 5:
            score += 12
            reasons.append("Near 60D high")
        elif near <= 15:
            score += 5
            reasons.append(f"{near:.0f}% off high")

        if above_ma:
            score += 8
            reasons.append("Above 20DMA")
        if r5 > 0 and r10 > 0:
            score += 5
            reasons.append("5D+10D green")
        if r1 >= 3:
            reasons.append(f"Strong 1D {r1:+.1f}%")

        # Buckets – looser
        if r10 >= 18 or r5 >= 12 or r1 >= 9:
            bucket = "EXTENDED"
            score -= 5
            reasons.append("Extended – caution")
        elif r5 >= 2.5 and above_ma and r10 < 18:
            bucket = "ACTIONABLE"
            if "Swing structure" not in reasons:
                reasons.append("Swing structure")
        elif r5 >= 1.0 or r1 >= 2.0:
            bucket = "BUILDING"
            reasons.append("Building")
        else:
            return None, "flat"

        if score < 45:
            return None, "low_score"

        return (
            SwingPick(
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
            ),
            "ok",
        )
    except Exception as e:
        logger.debug("swing_catcher %s: %s", symbol, e)
        return None, "no_data"


def run_swing_catcher(max_symbols: Optional[int] = None) -> Dict[str, Any]:
    cap = max_symbols or MAX_SYMBOLS
    symbols = load_merged_universe()[:cap]
    hits: List[SwingPick] = []
    stats = {"ok": 0, "no_data": 0, "flat": 0, "low_score": 0}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(_analyse, s, n): s for s, n in symbols}
        for fut in as_completed(futs):
            try:
                row, status = fut.result()
                stats[status] = stats.get(status, 0) + 1
                if row:
                    hits.append(row)
            except Exception:
                stats["no_data"] = stats.get("no_data", 0) + 1

    hits.sort(key=lambda x: -x.score)
    actionable = [h for h in hits if h.bucket == "ACTIONABLE"]
    building = [h for h in hits if h.bucket == "BUILDING"]
    extended = [h for h in hits if h.bucket == "EXTENDED"]

    # Fallback: if no actionable, promote top building by score
    if not actionable and building:
        for h in building[:5]:
            h.bucket = "ACTIONABLE"
            h.reasons = (h.reasons or [])[:4] + ["Promoted from building"]
        actionable = building[:5]
        building = building[5:]

    return {
        "scan_time": now_ist(),
        "scanned": len(symbols),
        "stats": stats,
        "actionable": actionable[:TOP_N],
        "building": building[:TOP_N],
        "extended": extended[:10],
        "total_hits": len(hits),
    }


def format_swing_catcher_telegram(result: Optional[Dict[str, Any]] = None) -> str:
    if result is None:
        result = run_swing_catcher()
    now = format_ist(result.get("scan_time"))
    st = result.get("stats") or {}
    lines = [
        "<b>🎯 SWING CATCHER – Do Not Miss</b>",
        now,
        f"<i>Scanned {result.get('scanned', 0)} · hits {result.get('total_hits', 0)} · "
        f"data-fail {st.get('no_data', 0)} · flat {st.get('flat', 0)}</i>",
        "",
        "<b>🟢 ACTIONABLE SWING</b>",
    ]
    act = result.get("actionable") or []
    if not act:
        lines.append("• None clear right now (market quiet or data thin)")
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
    lines.append("<b>🔥 EXTENDED (awareness – high chase risk)</b>")
    ext = result.get("extended") or []
    if not ext:
        lines.append("• —")
    else:
        for h in ext[:8]:
            lines.append(
                f"• <b>{h.symbol}</b> · 1D {h.ret_1d:+.1f}% · 5D {h.ret_5d:+.1f}% · "
                f"10D {h.ret_10d:+.1f}%"
            )

    lines.append("")
    lines.append(
        "<i>Prefer ACTIONABLE over EXTENDED. Use stops. Not advice. StockScorecard</i>"
    )
    out = "\n".join(lines)
    out = chr(10).join(lines)
    if len(out) > 4000:
        out = out[:3900] + chr(10) + chr(10) + "… (truncated)"
    return out
