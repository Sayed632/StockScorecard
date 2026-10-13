"""
Rally Detector – stronger, earlier identification of share rallies.

Focus (cash equities, multi-day – not 5m scalping):
  - 3D / 5D / 10D positive momentum
  - Volume expansion vs 20D average
  - Price near 20D/60D highs (breakout / continuation)
  - Higher-low structure (constructive)
  - Split: FRESH RALLY (early) vs EXTENDED RALLY (already ran hard)

Honest limit: still batch-scanned (not tick-by-tick). Better than pure lagging lists.
"""

from __future__ import annotations

from src.shared.time_ist import format_ist, now_ist

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging
import math
import re

import yaml

from src.data_fetch.prices import fetch_price_history
from src.data_fetch.nse_universe import load_merged_universe

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
MAX_WORKERS = 20
TOP_N = 12


@dataclass
class RallyName:
    symbol: str
    name: str
    price: float
    ret_3d: float
    ret_5d: float
    ret_10d: float
    vol_ratio: float
    near_high_pct: float  # 0 = at 60d high
    score: float
    stage: str  # FRESH | CONTINUATION | EXTENDED
    reasons: List[str]


def _load_symbols() -> List[Tuple[str, str]]:
    """Full merged universe (NSE master when available + local lists)."""
    try:
        return load_merged_universe(
            include_nse_master=True,
            include_local_yaml=True,
            include_sectors=True,
        )
    except Exception as e:
        logger.warning("merged universe failed (%s); fallback local only", e)
        return load_merged_universe(include_nse_master=False)


def _ret(close, days: int) -> Optional[float]:
    if close is None or len(close) <= days:
        return None
    past = float(close.iloc[-days - 1])
    cur = float(close.iloc[-1])
    if past <= 0 or math.isnan(past) or math.isnan(cur):
        return None
    return (cur / past - 1.0) * 100.0


def _analyse(symbol: str, name: str) -> Optional[RallyName]:
    try:
        df = fetch_price_history(f"{symbol}.NS", period="6mo")
        if df is None or len(df) < 30:
            df = fetch_price_history(f"{symbol}.BO", period="6mo")
        if df is None or len(df) < 30:
            return None
        close = df["close"].astype(float).dropna()
        if len(close) < 30:
            return None
        vol = None
        if "volume" in df.columns:
            vol = df["volume"].astype(float).dropna()

        px = float(close.iloc[-1])
        r3 = _ret(close, 3)
        r5 = _ret(close, 5)
        r10 = _ret(close, 10)
        if r3 is None or r5 is None or r10 is None:
            return None

        # Must show some positive multi-day bias
        if r5 < 1.5 and r3 < 1.0:
            return None

        high60 = float(close.tail(60).max())
        near = ((high60 - px) / high60 * 100.0) if high60 > 0 else 99.0

        vol_ratio = 1.0
        if vol is not None and len(vol) >= 25:
            avg = float(vol.tail(20).mean())
            recent = float(vol.tail(3).mean())
            if avg > 0:
                vol_ratio = recent / avg

        # Higher-low: last 5d low >= prior 5d low * 0.98
        low_recent = float(close.tail(5).min())
        low_prior = float(close.iloc[-10:-5].min()) if len(close) >= 10 else low_recent
        higher_low = low_recent >= low_prior * 0.98

        reasons = []
        score = 40.0

        # Momentum points
        score += max(-10, min(25, r5 * 1.8))
        score += max(-8, min(18, r3 * 2.0))
        score += max(-8, min(15, r10 * 0.7))

        if vol_ratio >= 1.4:
            score += 12
            reasons.append(f"Vol x{vol_ratio:.1f}")
        elif vol_ratio >= 1.15:
            score += 6
            reasons.append(f"Vol x{vol_ratio:.1f}")

        if near <= 2.0:
            score += 14
            reasons.append("At/near 60D high")
        elif near <= 5.0:
            score += 8
            reasons.append(f"Within {near:.1f}% of high")

        if higher_low:
            score += 8
            reasons.append("Higher-low structure")

        if r3 > 0 and r5 > 0 and r10 > 0:
            score += 10
            reasons.append("3D+5D+10D all green")

        # Stage
        if r10 >= 18 or r5 >= 12:
            stage = "EXTENDED"
            score -= 8  # still list, but marked
            reasons.append("Already extended")
        elif r5 >= 4 and near <= 5 and vol_ratio >= 1.1:
            stage = "CONTINUATION"
            reasons.append("Continuation setup")
        else:
            stage = "FRESH"
            if r5 < 8 and near <= 8:
                score += 5
                reasons.append("Early-stage candidate")

        if score < 55:
            return None

        return RallyName(
            symbol=symbol,
            name=name,
            price=px,
            ret_3d=r3,
            ret_5d=r5,
            ret_10d=r10,
            vol_ratio=vol_ratio,
            near_high_pct=near,
            score=score,
            stage=stage,
            reasons=reasons[:5],
        )
    except Exception as e:
        logger.debug("rally %s: %s", symbol, e)
        return None


def run_rally_detector(max_symbols: int = 1200) -> Dict[str, Any]:
    symbols = _load_symbols()[:max_symbols]
    hits: List[RallyName] = []

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
    fresh = [h for h in hits if h.stage == "FRESH"]
    cont = [h for h in hits if h.stage == "CONTINUATION"]
    ext = [h for h in hits if h.stage == "EXTENDED"]

    return {
        "scan_time": now_ist(),
        "scanned": len(symbols),
        "fresh": fresh[:TOP_N],
        "continuation": cont[:TOP_N],
        "extended": ext[:8],
        "all": hits[: TOP_N + 8],
    }


def format_rally_detector_telegram(result: Optional[Dict[str, Any]] = None) -> str:
    if result is None:
        result = run_rally_detector()
    now = format_ist(result.get("scan_time"))
    lines = [
        "<b>🚀 RALLY DETECTOR</b>",
        now,
        f"<i>Scanned {result.get('scanned', 0)} names · multi-day share rallies</i>",
        "",
        "<b>🌱 FRESH RALLY (earlier stage)</b>",
    ]
    fresh = result.get("fresh") or []
    if not fresh:
        lines.append("• None clear right now")
    else:
        for h in fresh[:8]:
            lines.append(
                f"• <b>{h.symbol}</b> ₹{h.price:.1f} · 5D {h.ret_5d:+.1f}% · 10D {h.ret_10d:+.1f}%"
            )
            lines.append(f"   {', '.join(h.reasons)}")

    lines.append("")
    lines.append("<b>📈 CONTINUATION RALLY</b>")
    cont = result.get("continuation") or []
    if not cont:
        lines.append("• —")
    else:
        for h in cont[:8]:
            lines.append(
                f"• <b>{h.symbol}</b> ₹{h.price:.1f} · 5D {h.ret_5d:+.1f}% · "
                f"vol x{h.vol_ratio:.1f}"
            )

    lines.append("")
    lines.append("<b>🔥 EXTENDED (already ran hard – caution)</b>")
    ext = result.get("extended") or []
    if not ext:
        lines.append("• —")
    else:
        for h in ext[:6]:
            lines.append(
                f"• <b>{h.symbol}</b> · 5D {h.ret_5d:+.1f}% · 10D {h.ret_10d:+.1f}% · late stage"
            )

    lines.append("")
    lines.append(
        "<i>For multi-day equity rallies – not 5m F&amp;O scalps. Not advice. "
        "Use stops. StockScorecard</i>"
    )
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3900] + "\n\n… (truncated)"
    return text
