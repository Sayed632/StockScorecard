"""
Daily Digest – one short "what to do today" summary.

Sent TOGETHER with regular detail messages (not instead of them).
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


def format_daily_digest_telegram() -> str:
    """Build a compact action digest from core layers."""
    now = datetime.now().strftime("%d %b %Y | %H:%M IST")
    lines: List[str] = [
        "<b>📋 StockScorecard DIGEST</b>",
        now,
        "",
        "<i>One-page action sheet. Detail messages follow.</i>",
        "",
    ]

    # 1) Fresh buys
    lines.append("<b>🟢 DO TODAY (Fresh buys)</b>")
    try:
        from src.intelligence.fresh_buys import collect_fresh_buys

        fb = collect_fresh_buys()
        buys = fb.get("buys") or []
        if not buys:
            lines.append("• None — wait for setups")
        else:
            for i, b in enumerate(buys[:6], 1):
                src = "+".join(b.sources) if b.sources else ""
                lines.append(
                    f"{i}. <b>{b.symbol}</b> [{b.confidence}] · hold {b.horizon}"
                    + (f" · {src}" if src else "")
                )
    except Exception as e:
        logger.warning("digest fresh: %s", e)
        lines.append("• (Fresh buys unavailable)")
    lines.append("")

    # 2) Horizon extended / don't chase
    lines.append("<b>🟡 HOLD / don’t chase</b>")
    try:
        from src.intelligence.horizon_monitor import run_horizon_monitor

        hz = run_horizon_monitor(max_rows=30)
        hold = [
            r
            for r in (hz.get("rows") or [])
            if r.action.startswith("🟡") or r.extended
        ][:6]
        if not hold:
            lines.append("• —")
        else:
            names = ", ".join(f"{r.symbol}" for r in hold)
            lines.append(f"• {names}")
            lines.append("<i>Extended / trail only — not fresh buys</i>")
    except Exception as e:
        logger.warning("digest horizon: %s", e)
        lines.append("• —")
    lines.append("")

    # 3) Prefer sectors
    lines.append("<b>📊 Prefer sectors</b>")
    try:
        from src.intelligence.sector_rotation import run_sector_rotation

        sr = run_sector_rotation()
        prefer = []
        for s in sr.get("sectors") or []:
            if s.label.startswith("🟢") or s.label.startswith("🔵"):
                if s.ss_sector not in prefer:
                    prefer.append(s.ss_sector)
            if len(prefer) >= 5:
                break
        if prefer:
            for p in prefer:
                lines.append(f"• {p}")
        else:
            lines.append("• Mixed — no clear leaders")
    except Exception as e:
        logger.warning("digest sector: %s", e)
        lines.append("• (Sector rotation unavailable)")
    lines.append("")

    # 4) FII/DII one-liner
    lines.append("<b>🏦 Flows</b>")
    try:
        from src.shared.fii_dii import fetch_fii_dii

        snap = fetch_fii_dii(include_history=False)
        if snap:
            def fmt(x: float) -> str:
                sign = "+" if x >= 0 else ""
                return f"{sign}{x:,.0f} Cr"

            lines.append(
                f"• FII {fmt(snap.fii_net)} ({snap.fii_bias}) · "
                f"DII {fmt(snap.dii_net)} ({snap.dii_bias})"
            )
            lines.append(f"• <i>{snap.overall_tone}</i>")
        else:
            lines.append("• Data unavailable")
    except Exception as e:
        logger.warning("digest fii: %s", e)
        lines.append("• —")
    lines.append("")

    # 5) Exit alerts if any open positions
    lines.append("<b>🚨 Exit alerts</b>")
    try:
        from src.intelligence.trade_plans import refresh_open_positions

        plans = refresh_open_positions()
        exits = [p for p in plans if p.status == "EXIT_ALERT"]
        if not exits:
            lines.append("• None")
        else:
            for p in exits[:5]:
                lines.append(
                    f"• <b>{p.symbol}</b> – {p.exit_reason or 'Review exit'}"
                )
    except Exception as e:
        logger.warning("digest exits: %s", e)
        lines.append("• None")
    lines.append("")

    lines.append(
        "<i>Details: Fresh Buys, Horizon, Hot, Sector, Flows, "
        "Penny, Multi-bagger, Trade Plans, News…</i>"
    )
    lines.append("<i>StockScorecard – Digest + full messages</i>")
    return "\n".join(lines)
