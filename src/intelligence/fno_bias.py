"""
F&O Decision Support (bias + risk) – NOT automated trading.

Phase 1 (free data):
  - Index bias: Nifty 50 / Bank Nifty trend & momentum
  - Stock F&O bias: liquid names – direction from price trend/volume
  - Risk flags: stretched move, weak structure
  - Optional AI plain-language brief if OPENAI/XAI key present

Important:
  - No strike/premium/Greeks guarantees (needs live option chain API for that)
  - High risk product – educational decision support only
  - Never place orders from this output automatically
"""

from __future__ import annotations

from src.shared.time_ist import format_ist, now_ist

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging
import math
import os
import re

import requests

from src.data_fetch.prices import fetch_price_history

logger = logging.getLogger(__name__)

# Liquid / widely traded F&O-style names (curated; expand over time)
FNO_STOCKS = [
    ("RELIANCE", "Reliance Industries"),
    ("TCS", "Tata Consultancy Services"),
    ("INFY", "Infosys"),
    ("HDFCBANK", "HDFC Bank"),
    ("ICICIBANK", "ICICI Bank"),
    ("SBIN", "State Bank of India"),
    ("BHARTIARTL", "Bharti Airtel"),
    ("ITC", "ITC"),
    ("LT", "Larsen & Toubro"),
    ("AXISBANK", "Axis Bank"),
    ("KOTAKBANK", "Kotak Mahindra Bank"),
    ("HINDUNILVR", "Hindustan Unilever"),
    ("BAJFINANCE", "Bajaj Finance"),
    ("MARUTI", "Maruti Suzuki"),
    ("TATAMOTORS", "Tata Motors"),
    ("TMPV", "Tata Motors PV"),
    ("SUNPHARMA", "Sun Pharma"),
    ("TATASTEEL", "Tata Steel"),
    ("JSWSTEEL", "JSW Steel"),
    ("NTPC", "NTPC"),
    ("POWERGRID", "Power Grid"),
    ("ULTRACEMCO", "UltraTech Cement"),
    ("ASIANPAINT", "Asian Paints"),
    ("TITAN", "Titan"),
    ("ADANIENT", "Adani Enterprises"),
    ("ADANIPORTS", "Adani Ports"),
    ("HAL", "Hindustan Aeronautics"),
    ("BEL", "Bharat Electronics"),
    ("DIVISLAB", "Divi's Labs"),
    ("LAURUSLABS", "Laurus Labs"),
]


@dataclass
class FnoBias:
    symbol: str
    name: str
    kind: str  # index | stock
    price: float
    ret_1d: float
    ret_5d: float
    bias: str  # BULLISH | BEARISH | NEUTRAL
    idea: str  # e.g. "Call bias" / "Put bias" / "Avoid directional"
    risk: str
    score: float


def _trend_bias(df) -> Optional[FnoBias]:
    return None  # placeholder signature


def _analyse(symbol: str, name: str, kind: str, yahoo: str) -> Optional[FnoBias]:
    try:
        df = fetch_price_history(yahoo, period="3mo")
        if df is None or len(df) < 25:
            return None
        close = df["close"].astype(float).dropna()
        if len(close) < 25:
            return None
        px = float(close.iloc[-1])
        if px <= 0 or math.isnan(px):
            return None
        r1 = (px / float(close.iloc[-2]) - 1.0) * 100.0
        r5 = (px / float(close.iloc[-6]) - 1.0) * 100.0 if len(close) >= 6 else 0.0

        # Simple structure: vs 20DMA and 5D momentum
        ma20 = float(close.tail(20).mean())
        ma50 = float(close.tail(50).mean()) if len(close) >= 50 else ma20
        above20 = px >= ma20
        above50 = px >= ma50

        score = 50.0
        if above20:
            score += 12
        else:
            score -= 12
        if above50:
            score += 10
        else:
            score -= 10
        score += max(-15, min(15, r5 * 1.2))
        score += max(-8, min(8, r1 * 0.8))

        if score >= 62:
            bias = "BULLISH"
            idea = "Call / futures long bias (if liquid)"
        elif score <= 38:
            bias = "BEARISH"
            idea = "Put / futures short bias (if liquid)"
        else:
            bias = "NEUTRAL"
            idea = "Avoid fresh directional F&O – wait"

        # Risk flags
        risks = []
        if abs(r5) >= 12:
            risks.append("stretched 5D move")
        if abs(r1) >= 4:
            risks.append("volatile day")
        if bias != "NEUTRAL" and abs(score - 50) < 15:
            risks.append("weak edge")
        risk = ", ".join(risks) if risks else "normal"

        return FnoBias(
            symbol=symbol,
            name=name,
            kind=kind,
            price=px,
            ret_1d=r1,
            ret_5d=r5,
            bias=bias,
            idea=idea,
            risk=risk,
            score=score,
        )
    except Exception as e:
        logger.debug("fno %s: %s", symbol, e)
        return None


def run_fno_bias(max_stocks: int = 12) -> Dict[str, Any]:
    indices = [
        ("NIFTY", "Nifty 50", "^NSEI"),
        ("BANKNIFTY", "Bank Nifty", "^NSEBANK"),
    ]
    index_rows: List[FnoBias] = []
    for sym, name, yf in indices:
        row = _analyse(sym, name, "index", yf)
        if row:
            index_rows.append(row)

    stock_rows: List[FnoBias] = []
    for sym, name in FNO_STOCKS:
        # try .NS then bare via prices helper
        row = _analyse(sym, name, "stock", f"{sym}.NS")
        if row:
            stock_rows.append(row)

    # Prefer clear biases; sort by |score-50|
    stock_rows.sort(key=lambda x: -abs(x.score - 50))
    stock_rows = stock_rows[:max_stocks]

    bullish = [x for x in stock_rows if x.bias == "BULLISH"]
    bearish = [x for x in stock_rows if x.bias == "BEARISH"]
    neutral = [x for x in stock_rows if x.bias == "NEUTRAL"]

    return {
        "scan_time": now_ist(),
        "indices": index_rows,
        "bullish": bullish[:6],
        "bearish": bearish[:6],
        "neutral": neutral[:4],
        "all_stocks": stock_rows,
    }


def format_fno_bias_rule(result: Dict[str, Any]) -> str:
    now = format_ist(result["scan_time"])
    lines = [
        "<b>📉 F&amp;O BIAS BOARD</b>",
        now,
        "",
        "<i>Decision support only · High risk · Not order advice</i>",
        "<i>No strikes/premiums here – use broker option chain before trading</i>",
        "",
        "<b>INDEX BIAS</b>",
    ]
    for x in result.get("indices") or []:
        icon = "🟢" if x.bias == "BULLISH" else ("🔴" if x.bias == "BEARISH" else "⚪")
        lines.append(
            f"{icon} <b>{x.symbol}</b> {x.bias} · 1D {x.ret_1d:+.1f}% · 5D {x.ret_5d:+.1f}%"
        )
        lines.append(f"   → {x.idea} · risk: {x.risk}")

    lines.append("")
    lines.append("<b>🟢 STOCK CALL / LONG BIAS</b>")
    bull = result.get("bullish") or []
    if not bull:
        lines.append("• None with clear edge")
    else:
        for x in bull:
            lines.append(
                f"• <b>{x.symbol}</b> · sc {x.score:.0f} · 5D {x.ret_5d:+.1f}% · {x.risk}"
            )

    lines.append("")
    lines.append("<b>🔴 STOCK PUT / SHORT BIAS</b>")
    bear = result.get("bearish") or []
    if not bear:
        lines.append("• None with clear edge")
    else:
        for x in bear:
            lines.append(
                f"• <b>{x.symbol}</b> · sc {x.score:.0f} · 5D {x.ret_5d:+.1f}% · {x.risk}"
            )

    lines.append("")
    lines.append("<b>⚪ STAY SIDEWAYS / SKIP</b>")
    neu = result.get("neutral") or []
    if not neu:
        lines.append("• —")
    else:
        for x in neu[:4]:
            lines.append(f"• {x.symbol}")

    lines.append("")
    lines.append(
        "<i>F&amp;O can lose capital quickly. Size small, use stops, prefer liquid strikes near ATM. "
        "StockScorecard F&amp;O module – not SEBI advice.</i>"
    )
    return "\n".join(lines)


def _optional_ai(result: Dict[str, Any], base: str) -> Optional[str]:
    api_key = (
        os.getenv("OPENAI_API_KEY")
        or os.getenv("XAI_API_KEY")
        or os.getenv("GROK_API_KEY")
        or ""
    ).strip()
    if not api_key:
        return None

    if os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY"):
        url = "https://api.x.ai/v1/chat/completions"
        model = os.getenv("XAI_MODEL", "grok-2-latest")
    else:
        url = "https://api.openai.com/v1/chat/completions"
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Compact packet for model
    packet = {
        "indices": [
            {"symbol": x.symbol, "bias": x.bias, "ret_1d": x.ret_1d, "ret_5d": x.ret_5d, "idea": x.idea, "risk": x.risk}
            for x in (result.get("indices") or [])
        ],
        "bullish": [x.symbol for x in (result.get("bullish") or [])],
        "bearish": [x.symbol for x in (result.get("bearish") or [])],
    }
    system = (
        "You are an Indian markets F&O risk coach. Rewrite the bias board in clear Telegram HTML "
        "(only <b> <i>). Do NOT invent strikes, premiums, or targets. Stress risk. Under 3200 chars. "
        "End with: Not investment advice. F&O can cause rapid losses."
    )
    try:
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": f"Data:\n{packet}\n\nDraft:\n{base}"},
                ],
                "temperature": 0.2,
                "max_tokens": 900,
            },
            timeout=40,
        )
        if not r.ok:
            return None
        text = r.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if len(text) < 40:
            return None
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.I | re.S)
        if "F&O" not in text.upper() and "F&amp;O" not in text:
            text = "<b>📉 F&amp;O BIAS BOARD</b> <i>(AI-assisted)</i>\n" + text
        return text
    except Exception as e:
        logger.warning("F&O AI brief failed: %s", e)
        return None


def format_fno_bias_telegram(use_ai: bool = True) -> str:
    result = run_fno_bias()
    base = format_fno_bias_rule(result)
    if use_ai:
        polished = _optional_ai(result, base)
        if polished:
            return polished
    return base
