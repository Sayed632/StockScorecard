"""
Screener Insights – quarterly growth, quality ratios, pledge risk, pros/cons.

Uses SCREENER_EMAIL + SCREENER_PASSWORD. Telegram message for swing / long-term context.
"""

from __future__ import annotations

from src.shared.time_ist import format_ist, now_ist

from typing import Any, Dict, List, Optional
import logging

from src.data_fetch.screener_client import ScreenerSnapshot, fetch_many, screener_creds

logger = logging.getLogger(__name__)

# Mix of swing momentum names + quality long-term names
DEFAULT_SYMBOLS = [
    "LAURUSLABS", "DIVISLAB", "SOLARINDS", "HAL", "BEL", "RELIANCE", "TCS",
    "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "ITC", "LT", "SUNPHARMA",
    "TATASTEEL", "JSWSTEEL", "ADANIENT", "MARUTI", "BAJFINANCE", "NTPC",
]


def _swing_score(s: ScreenerSnapshot) -> float:
    sc = 50.0
    if s.profit_growth_qoq is not None:
        sc += max(-20, min(25, s.profit_growth_qoq * 0.5))
    if s.sales_growth_qoq is not None:
        sc += max(-10, min(15, s.sales_growth_qoq * 0.35))
    if s.pledge_pct is not None and s.pledge_pct >= 20:
        sc -= 15
    if s.cons:
        sc -= min(10, len(s.cons) * 2)
    return sc


def _lt_score(s: ScreenerSnapshot) -> float:
    sc = 50.0
    if s.roe is not None:
        sc += max(-15, min(20, (s.roe - 10) * 1.2))
    if s.roce is not None:
        sc += max(-10, min(15, (s.roce - 10) * 0.9))
    if s.debt_to_equity is not None:
        if s.debt_to_equity > 1.5:
            sc -= 12
        elif s.debt_to_equity < 0.5:
            sc += 8
    if s.promoter_pct is not None and s.promoter_pct >= 50:
        sc += 5
    if s.pledge_pct is not None and s.pledge_pct >= 10:
        sc -= 10
    if s.sales_growth_yoy is not None:
        sc += max(-10, min(15, s.sales_growth_yoy * 0.2))
    return sc


def run_screener_insights(
    symbols: Optional[List[str]] = None,
    limit: int = 18,
) -> Dict[str, Any]:
    user, pwd = screener_creds()
    snaps = fetch_many(symbols or DEFAULT_SYMBOLS, limit=limit)
    ok = [s for s in snaps if s.ok]

    swing_rank = sorted(ok, key=_swing_score, reverse=True)
    lt_rank = sorted(ok, key=_lt_score, reverse=True)
    risk = [
        s for s in ok
        if (s.pledge_pct is not None and s.pledge_pct >= 15)
        or (s.debt_to_equity is not None and s.debt_to_equity >= 2)
    ]

    return {
        "scan_time": now_ist(),
        "credentials": bool(user and pwd),
        "fetched": len(ok),
        "attempted": len(snaps),
        "swing_rank": swing_rank[:8],
        "lt_rank": lt_rank[:8],
        "risk": risk[:6],
        "all": ok,
    }


def format_screener_insights_telegram(result: Optional[Dict[str, Any]] = None) -> str:
    if result is None:
        result = run_screener_insights()
    now = format_ist(result.get("scan_time"))
    lines = [
        "<b>📋 SCREENER INSIGHTS</b>",
        now,
        "",
        f"<i>Login: {'configured' if result.get('credentials') else 'missing'} · "
        f"parsed {result.get('fetched')}/{result.get('attempted')} companies</i>",
        "",
        "<b>🟢 SWING CONTEXT (results / QoQ momentum)</b>",
    ]
    swing = result.get("swing_rank") or []
    if not swing:
        lines.append("• No data (check Screener secrets or site access)")
    else:
        for s in swing[:6]:
            bits = []
            if s.profit_growth_qoq is not None:
                bits.append(f"Pat QoQ {s.profit_growth_qoq:+.0f}%")
            if s.sales_growth_qoq is not None:
                bits.append(f"Sales QoQ {s.sales_growth_qoq:+.0f}%")
            if s.pe is not None:
                bits.append(f"PE {s.pe:.0f}")
            lines.append(
                f"• <b>{s.symbol}</b> – {', '.join(bits) if bits else 'ratios ok'}"
            )
            if s.pros:
                lines.append(f"   ✅ {s.pros[0][:90]}")

    lines.append("")
    lines.append("<b>🔵 LONG-TERM QUALITY (ROE / ROCE / debt)</b>")
    lt = result.get("lt_rank") or []
    if not lt:
        lines.append("• —")
    else:
        for s in lt[:6]:
            bits = []
            if s.roe is not None:
                bits.append(f"ROE {s.roe:.0f}%")
            if s.roce is not None:
                bits.append(f"ROCE {s.roce:.0f}%")
            if s.debt_to_equity is not None:
                bits.append(f"D/E {s.debt_to_equity:.2f}")
            if s.promoter_pct is not None:
                bits.append(f"Prom {s.promoter_pct:.0f}%")
            lines.append(
                f"• <b>{s.symbol}</b> – {', '.join(bits) if bits else 'see page'}"
            )

    risk = result.get("risk") or []
    lines.append("")
    lines.append("<b>⚠️ RISK FLAGS (pledge / high debt)</b>")
    if not risk:
        lines.append("• None in scanned set")
    else:
        for s in risk:
            bits = []
            if s.pledge_pct is not None:
                bits.append(f"Pledge {s.pledge_pct:.0f}%")
            if s.debt_to_equity is not None:
                bits.append(f"D/E {s.debt_to_equity:.2f}")
            if s.cons:
                bits.append(s.cons[0][:60])
            lines.append(f"• <b>{s.symbol}</b> – {', '.join(bits)}")

    lines.append("")
    lines.append(
        "<i>Screener fundamentals (lagging). Combine with price action & NSE news. "
        "Not advice. StockScorecard</i>"
    )
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3900] + "\n\n… (truncated)"
    return text
