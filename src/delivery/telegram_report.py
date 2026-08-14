"""
Telegram Delivery Layer
Produces the exact approved message format.
"""

from src.shared.models import ScanResult, Action
from src.telegram_notify import send_message
from src.shared.fii_dii import fetch_fii_dii, fetch_sector_fpi, format_fii_dii_section, format_sector_fpi_section


def format_report(result: ScanResult) -> str:
    """Build the full Telegram message as per URS."""
    now = result.scan_time.strftime("%d %b %Y | %H:%M IST")

    lines = [
        f"<b>📊 StockScorecard | Daily Decision Report</b>",
        f"{now}",
        f"Scanning Frequency: <b>{result.frequency}x</b>",
        "",
    ]

    # FII / DII institutional flows
    snap = fetch_fii_dii(include_history=True)
    lines.extend(format_fii_dii_section(snap))
    sector_fpi = fetch_sector_fpi()
    lines.extend(format_sector_fpi_section(sector_fpi))

    # Separate penny ideas (extras.penny == True) from normal lists for clarity
    def is_penny(idea) -> bool:
        return bool(idea.extras.get("penny")) if idea.extras else False

    swing_normal = [i for i in result.swing_ideas if not is_penny(i)]
    long_normal = [i for i in result.long_term_ideas if not is_penny(i)]
    dark_normal = [i for i in result.dark_horse_ideas if not is_penny(i)]

    penny_all = (
        [i for i in result.swing_ideas if is_penny(i)]
        + [i for i in result.long_term_ideas if is_penny(i)]
        + [i for i in result.dark_horse_ideas if is_penny(i)]
    )
    # de-dup by symbol keeping highest score
    seen = {}
    for i in penny_all:
        if i.symbol not in seen or i.score > seen[i.symbol].score:
            seen[i.symbol] = i
    penny_ideas = sorted(seen.values(), key=lambda x: x.score, reverse=True)

    # 1. Swing
    lines.append("<b>🟢 SWING TRADE – BUY NOW</b>")
    buy_now = [i for i in swing_normal if i.action == Action.BUY_NOW]
    if buy_now:
        for idea in buy_now:
            lines.append(f"• <b>{idea.symbol}</b> – {idea.reason}")
    else:
        lines.append("• No strong swing buy ideas today")
    lines.append("")

    waits = [i for i in swing_normal if i.action == Action.WAIT]
    if waits:
        lines.append("<b>🟡 SWING – WAIT</b>")
        for idea in waits[:4]:
            lines.append(f"• {idea.symbol} – {idea.reason}")
        lines.append("")

    # 2. Long-term
    lines.append("<b>🔵 LONG-TERM – INVEST</b>")
    invest = [i for i in long_normal if i.action == Action.HOLD_INVEST]
    if invest:
        for idea in invest:
            lines.append(f"• <b>{idea.symbol}</b> – {idea.reason}")
    else:
        lines.append("• No new long-term ideas today")
    lines.append("")

    # 3. Dark Horse
    lines.append("<b>🦄 DARK HORSE IDEAS</b>")
    if dark_normal:
        for idea in dark_normal:
            lines.append(f"• <b>{idea.symbol}</b> – {idea.reason}")
    else:
        lines.append("• No Dark Horse ideas surfaced today")
    lines.append("")

    # 4. Penny Monitor (sector-agnostic)
    lines.append("<b>🪙 PENNY STOCKS MONITOR</b> <i>(High Risk)</i>")
    if penny_ideas:
        for idea in penny_ideas[:8]:
            lines.append(f"• <b>{idea.symbol}</b> – {idea.reason}")
    else:
        lines.append("• No penny setups meeting filters today")
    lines.append("")

    # Sector snapshot
    if result.sector_summary:
        lines.append("<b>📁 SECTOR SNAPSHOT</b>")
        for sec, summary in list(result.sector_summary.items())[:8]:
            lines.append(f"• {sec.replace('_', ' ').title()}: {summary}")
        lines.append("")

    lines.append("<i>This is a decision-support tool. Not investment advice.</i>")
    lines.append("<i>Penny stocks are high risk – use strict position size & stop-loss.</i>")
    lines.append("<i>Always use stop-losses for swing trades.</i>")

    return "\n".join(lines)


def send_daily_report(result: ScanResult) -> bool:
    """Format and send to Telegram."""
    text = format_report(result)
    if len(text) > 4000:
        text = text[:3900] + "\n\n… (truncated)"
    return send_message(text)
