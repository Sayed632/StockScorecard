"""
F&O Strike Alert Board – structured index CE/PE bias (tip-channel style, rule-based).

What tip channels often show:
  "Sensex 74600 pe BUY above 363 TG..."

What we can do reliably on free data:
  - Spot (Nifty / Bank Nifty)
  - Nearest ATM strike
  - CE vs PE directional bias from short-term index structure
  - Risk / invalidation style levels on the *index*

What we cannot guarantee without paid option-chain API:
  - Exact live option *premium* (363, 380, …)
  - Greeks / precise TG on premium

Message style is clear and single-update (not spam every tick).
"""

from __future__ import annotations

from src.shared.time_ist import format_ist, now_ist

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import logging
import math

from src.data_fetch.prices import fetch_price_history

logger = logging.getLogger(__name__)


@dataclass
class IndexAlert:
    name: str
    yahoo: str
    spot: float
    ret_intraday_proxy: float  # 1D %
    ret_5d: float
    strike: int
    side: str  # CE | PE | NONE
    bias: str
    trigger_note: str
    invalidation: str
    risk: str


def _round_strike(spot: float, step: int) -> int:
    return int(round(spot / step) * step)


def _analyse_index(name: str, yahoo: str, step: int) -> Optional[IndexAlert]:
    try:
        df = fetch_price_history(yahoo, period="3mo")
        if df is None or len(df) < 15:
            return None
        close = df["close"].astype(float).dropna()
        if len(close) < 15:
            return None
        spot = float(close.iloc[-1])
        if spot <= 0 or math.isnan(spot):
            return None
        r1 = (spot / float(close.iloc[-2]) - 1.0) * 100.0
        r5 = (spot / float(close.iloc[-6]) - 1.0) * 100.0 if len(close) >= 6 else 0.0
        ma5 = float(close.tail(5).mean())
        ma20 = float(close.tail(20).mean())

        strike = _round_strike(spot, step)

        # Directional bias
        side = "NONE"
        bias = "NO CLEAR F&O DIRECTIONAL EDGE"
        trigger_note = "Wait – avoid chasing premiums"
        invalidation = "—"
        risk = "normal"

        # Bearish tilt → PE bias
        if r1 <= -0.35 or (r1 < 0 and spot < ma5 and ma5 <= ma20):
            side = "PE"
            bias = "PUT bias (index soft / below short MAs)"
            trigger_note = (
                f"Watch {name} {strike} PE on your broker · "
                f"prefer strength in premium only if spot stays weak below {spot:.0f}"
            )
            invalidation = f"Spot reclaim & hold above {max(spot, ma5):.0f}"
            risk = "high if index snaps back up (PE premium can crash)"
        # Bullish tilt → CE bias
        elif r1 >= 0.35 or (r1 > 0 and spot > ma5 and ma5 >= ma20):
            side = "CE"
            bias = "CALL bias (index firm / above short MAs)"
            trigger_note = (
                f"Watch {name} {strike} CE on your broker · "
                f"prefer premium only if spot holds above {min(spot, ma5):.0f}"
            )
            invalidation = f"Spot lose & stay below {min(spot, ma5):.0f}"
            risk = "high if index reverses down (CE premium can crash)"
        else:
            risk = "choppy – premium decay risk both sides"

        return IndexAlert(
            name=name,
            yahoo=yahoo,
            spot=spot,
            ret_intraday_proxy=r1,
            ret_5d=r5,
            strike=strike,
            side=side,
            bias=bias,
            trigger_note=trigger_note,
            invalidation=invalidation,
            risk=risk,
        )
    except Exception as e:
        logger.debug("fno strike %s: %s", name, e)
        return None


def run_fno_strike_alerts() -> Dict[str, Any]:
    specs = [
        ("NIFTY", "^NSEI", 50),
        ("BANKNIFTY", "^NSEBANK", 100),
        # Sensex via approximate proxy if available – Yahoo often ^BSESN
        ("SENSEX", "^BSESN", 100),
    ]
    rows: List[IndexAlert] = []
    for name, yf, step in specs:
        row = _analyse_index(name, yf, step)
        if row:
            rows.append(row)
    return {"scan_time": now_ist(), "indices": rows}


def format_fno_strike_alerts_telegram(result: Optional[Dict[str, Any]] = None) -> str:
    if result is None:
        result = run_fno_strike_alerts()
    now = format_ist(result.get("scan_time"))
    lines = [
        "<b>🎯 F&amp;O STRIKE ALERTS</b>",
        now,
        "",
        "<i>Rule-based CE/PE bias from index structure · "
        "Premium entry must be checked on your broker</i>",
        "",
    ]
    rows = result.get("indices") or []
    if not rows:
        lines.append("• Index data unavailable right now")
    for a in rows:
        icon = "🔴" if a.side == "PE" else ("🟢" if a.side == "CE" else "⚪")
        side_txt = a.side if a.side != "NONE" else "—"
        lines.append(
            f"{icon} <b>{a.name} {a.strike} {side_txt}</b>"
        )
        lines.append(
            f"   Spot {a.spot:.2f} · 1D {a.ret_intraday_proxy:+.2f}% · 5D {a.ret_5d:+.2f}%"
        )
        lines.append(f"   Bias: {a.bias}")
        lines.append(f"   {a.trigger_note}")
        lines.append(f"   Invalidation: {a.invalidation}")
        lines.append(f"   Risk: {a.risk}")
        lines.append("")

    lines.append(
        "<b>How this differs from tip channels</b>\n"
        "• We do <b>not</b> invent live premium (e.g. 363→397)\n"
        "• We give <b>strike + side + index levels</b>; you read premium on app\n"
        "• One clear board per run – not 20 spam lines\n"
        "",
    )
    lines.append(
        "<i>F&amp;O can lose money fast. Not advice. Not SEBI recommendation. "
        "StockScorecard</i>"
    )
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3900] + "\n\n… (truncated)"
    return text
