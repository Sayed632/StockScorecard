"""
Wide-scan follow-up: Day-0 capture → next session monitor → recommendation.

Flow:
  1) Wide Parallel Scan (evening) saves top movers to data/wide_scan_watch.json
  2) Next trading morning: re-fetch prices vs capture price
  3) Telegram: CONTINUE / WAIT_PULLBACK / FADE / SKIP

Honest: not a broker order system; decision-support only.
"""

from __future__ import annotations

from src.shared.time_ist import format_ist, now_ist

from dataclasses import dataclass, asdict
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import logging
import math

from src.data_fetch.prices import fetch_price_history

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
WATCH_PATH = ROOT / "config" / "wide_scan_watch.json"
MAX_WATCH = 15


@dataclass
class WatchItem:
    symbol: str
    name: str
    capture_price: float
    capture_ret_1d: float
    capture_ret_5d: Optional[float]
    capture_vol_ratio: Optional[float]
    capture_score: float
    captured_at: str  # ISO date IST calendar day


@dataclass
class FollowRec:
    symbol: str
    name: str
    capture_price: float
    now_price: float
    change_pct: float  # vs capture
    ret_1d: float
    action: str  # CONTINUE | WAIT_PULLBACK | FADE | SKIP
    reason: str


def save_watch_from_movers(movers: List[Any], captured_at: Optional[datetime] = None) -> Path:
    """
    Persist top movers from a wide-scan result.
    `movers` items need: symbol, name, price, ret_1d, ret_5d, vol_ratio, score
    """
    when = captured_at or now_ist()
    day = when.strftime("%Y-%m-%d") if hasattr(when, "strftime") else str(when)[:10]
    items: List[Dict[str, Any]] = []
    for m in movers[:MAX_WATCH]:
        try:
            items.append(
                {
                    "symbol": str(getattr(m, "symbol", "")).upper(),
                    "name": str(getattr(m, "name", "")),
                    "capture_price": float(getattr(m, "price", 0) or 0),
                    "capture_ret_1d": float(getattr(m, "ret_1d", 0) or 0),
                    "capture_ret_5d": getattr(m, "ret_5d", None),
                    "capture_vol_ratio": getattr(m, "vol_ratio", None),
                    "capture_score": float(getattr(m, "score", 0) or 0),
                    "captured_at": day,
                }
            )
        except Exception:
            continue
    payload = {
        "saved_at": format_ist(when),
        "captured_day": day,
        "count": len(items),
        "items": items,
    }
    WATCH_PATH.parent.mkdir(parents=True, exist_ok=True)
    WATCH_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Wide-scan watch saved: %s names → %s", len(items), WATCH_PATH)
    return WATCH_PATH


def load_watch() -> Dict[str, Any]:
    if not WATCH_PATH.exists():
        return {}
    try:
        return json.loads(WATCH_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("load watch: %s", e)
        return {}


def _price_now(symbol: str) -> Optional[tuple]:
    """Return (price, ret_1d) or None."""
    try:
        df = fetch_price_history(f"{symbol}.NS", period="1mo")
        if df is None or len(df) < 3:
            df = fetch_price_history(f"{symbol}.BO", period="1mo")
        if df is None or len(df) < 2:
            return None
        close = df["close"].astype(float).dropna()
        px = float(close.iloc[-1])
        if px <= 0 or math.isnan(px):
            return None
        prev = float(close.iloc[-2])
        r1 = (px / prev - 1.0) * 100.0 if prev > 0 else 0.0
        return px, r1
    except Exception:
        return None


def evaluate_watch(watch: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    watch = watch if watch is not None else load_watch()
    items = watch.get("items") or []
    recs: List[FollowRec] = []
    for it in items:
        sym = str(it.get("symbol") or "").upper()
        if not sym:
            continue
        cap = float(it.get("capture_price") or 0)
        got = _price_now(sym)
        if not got or cap <= 0:
            continue
        px, r1 = got
        chg = (px / cap - 1.0) * 100.0
        cap_1d = float(it.get("capture_ret_1d") or 0)

        # Recommendation rules (next session after a surge day)
        if chg <= -5:
            action = "FADE"
            reason = f"Gave back {chg:.1f}% vs capture – momentum may have failed"
        elif chg <= -2:
            action = "WAIT_PULLBACK"
            reason = f"Cooling {chg:.1f}% from capture – wait for hold/base"
        elif r1 <= -3 and chg < 2:
            action = "FADE"
            reason = f"Weak today ({r1:+.1f}%) after prior surge"
        elif chg >= 3 and r1 >= 0:
            action = "CONTINUE"
            reason = f"Holding strength (+{chg:.1f}% vs capture, 1D {r1:+.1f}%)"
        elif -2 < chg < 3 and r1 > -2:
            action = "WAIT_PULLBACK"
            reason = "Sideways after surge – better entry on constructive pullback"
        elif cap_1d >= 12 and chg > 0:
            action = "SKIP"
            reason = "Prior day was very extended – avoid chasing residual"
        else:
            action = "WAIT_PULLBACK"
            reason = "No clear continuation yet"

        recs.append(
            FollowRec(
                symbol=sym,
                name=str(it.get("name") or sym),
                capture_price=cap,
                now_price=px,
                change_pct=chg,
                ret_1d=r1,
                action=action,
                reason=reason,
            )
        )

    # Order: CONTINUE first, then WAIT, then FADE/SKIP
    order = {"CONTINUE": 0, "WAIT_PULLBACK": 1, "FADE": 2, "SKIP": 3}
    recs.sort(key=lambda x: (order.get(x.action, 9), -x.change_pct))

    return {
        "scan_time": now_ist(),
        "captured_day": watch.get("captured_day"),
        "watched": len(items),
        "evaluated": len(recs),
        "recs": recs,
    }


def format_followup_telegram(result: Optional[Dict[str, Any]] = None) -> str:
    if result is None:
        result = evaluate_watch()
    now = format_ist(result.get("scan_time"))
    day = result.get("captured_day") or "?"
    lines = [
        "<b>📋 WIDE SCAN → NEXT-DAY PLAN</b>",
        now,
        f"<i>Monitoring movers captured on {day} · "
        f"{result.get('evaluated', 0)}/{result.get('watched', 0)} priced</i>",
        "",
    ]
    recs: List[FollowRec] = result.get("recs") or []
    if not recs:
        lines.append("• No watchlist yet. Run <b>Wide Parallel Scan</b> first (evening).")
        lines.append("")
        lines.append("<i>StockScorecard</i>")
        return "\n".join(lines)

    groups = [
        ("🟢 CONTINUE (strength holding)", "CONTINUE"),
        ("🟡 WAIT PULLBACK (prefer better entry)", "WAIT_PULLBACK"),
        ("🔴 FADE / weak (avoid new buys)", "FADE"),
        ("⚪ SKIP (too extended / unclear)", "SKIP"),
    ]
    for title, key in groups:
        bucket = [r for r in recs if r.action == key]
        lines.append(f"<b>{title}</b>")
        if not bucket:
            lines.append("• —")
        else:
            for r in bucket[:8]:
                lines.append(
                    f"• <b>{r.symbol}</b> ₹{r.now_price:.2f} "
                    f"(vs capture ₹{r.capture_price:.2f}, {r.change_pct:+.1f}%)"
                )
                lines.append(f"   {r.reason}")
        lines.append("")

    lines.append(
        "<i>Plan from yesterday’s movers — not auto-buy. "
        "Use stops. Prefer CONTINUE only with your own risk limit. StockScorecard</i>"
    )
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3900] + "\n\n… (truncated)"
    return text
