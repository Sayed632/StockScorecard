"""
Telegram Delivery Layer
Produces the exact approved message format.
"""

from datetime import datetime
from typing import Optional
from src.shared.models import ScanResult, Action
from src.telegram_notify import send_message
import os


def format_report(result: ScanResult) -> str:
    """Build the full Telegram message as per URS."""
    now = result.scan_time.strftime("%d %b %Y | %H:%M IST")

    lines = [
        f"<b>📊 StockScorecard | Daily Decision Report</b>",
        f"{now}",
        f"Scanning Frequency: <b>{result.frequency}x</b>",
        "",
    ]

    # 1. Swing
    lines.append("<b>🟢 SWING TRADE – BUY NOW</b>")
    buy_now = [i for i in result.swing_ideas if i.action == Action.BUY_NOW]
    if buy_now:
        for idea in buy_now:
            lines.append(f"• <b>{idea.symbol}</b> – {idea.reason}")
    else:
        lines.append("• No strong swing buy ideas today")
    lines.append("")

    # Wait section (optional, short)
    waits = [i for i in result.swing_ideas if i.action == Action.WAIT]
    if waits:
        lines.append("<b>🟡 SWING – WAIT</b>")
        for idea in waits[:4]:
            lines.append(f"• {idea.symbol} – {idea.reason}")
        lines.append("")

    # 2. Long-term
    lines.append("<b>🔵 LONG-TERM – INVEST</b>")
    if result.long_term_ideas:
        for idea in result.long_term_ideas:
            lines.append(f"• <b>{idea.symbol}</b> – {idea.reason}")
    else:
        lines.append("• No new long-term ideas today")
    lines.append("")

    # 3. Dark Horse
    lines.append("<b>🦄 DARK HORSE IDEAS</b>")
    if result.dark_horse_ideas:
        for idea in result.dark_horse_ideas:
            lines.append(f"• <b>{idea.symbol}</b> – {idea.reason}")
    else:
        lines.append("• No Dark Horse ideas surfaced today")
    lines.append("")

    # Sector snapshot
    if result.sector_summary:
        lines.append("<b>📁 SECTOR SNAPSHOT</b>")
        for sec, summary in list(result.sector_summary.items())[:6]:
            lines.append(f"• {sec.replace('_', ' ').title()}: {summary}")
        lines.append("")

    lines.append("<i>This is a decision-support tool. Not investment advice.</i>")
    lines.append("<i>Always use stop-losses for swing trades.</i>")

    return "\n".join(lines)


def send_daily_report(result: ScanResult) -> bool:
    """Format and send to Telegram."""
    text = format_report(result)
    if len(text) > 4000:
        text = text[:3900] + "\n\n… (truncated)"
    return send_message(text)