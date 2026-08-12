"""
Telegram delivery for StockScorecard reports.
Posts formatted Q-G-V-T score summaries to a channel.

Credentials are read from environment variables (never hardcoded):
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID   (e.g. @nsepyscan or -100xxxxxxxxxx)
"""

import os
import requests
from typing import Optional
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()  # loads .env if present


def _get_credentials():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    return token, chat_id


def send_message(
    text: str,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
    parse_mode: str = "HTML",
    disable_preview: bool = True,
) -> bool:
    """Send a text message to the Telegram channel. Returns True on success."""
    token, default_chat = _get_credentials()
    bot_token = bot_token or token
    chat_id = chat_id or default_chat

    if not bot_token or not chat_id:
        print("Telegram credentials missing. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_preview,
    }
    try:
        resp = requests.post(url, json=payload, timeout=30)
        data = resp.json()
        if data.get("ok"):
            return True
        print(f"Telegram error: {data.get('description')}")
        return False
    except Exception as e:
        print(f"Telegram send failed: {e}")
        return False


def format_scorecard_report(df: pd.DataFrame, max_rows: int = 12) -> str:
    """Create a clean, readable HTML report for Telegram."""
    now = datetime.now().strftime("%d %b %Y, %H:%M IST")

    lines = [
        f"<b>📊 StockScorecard Report</b>",
        f"<i>{now}</i>",
        "",
        "<b>🏆 Top Stocks by Overall Score</b>",
        "<pre>",
    ]

    lines.append(f"{'Sym':<11} {'Cap':<5} {'Ovr':>5} {'Q':>4} {'G':>4} {'V':>4} {'T':>4}")
    lines.append("-" * 40)

    top = df.head(max_rows)
    for _, r in top.iterrows():
        sym = str(r["symbol"])[:10]
        bucket = str(r.get("market_cap_bucket", ""))[:4]
        lines.append(
            f"{sym:<11} {bucket:<5} {r['Overall']:>5.1f} "
            f"{r['Q']:>4.0f} {r['G']:>4.0f} {r['V']:>4.0f} {r['T']:>4.0f}"
        )

    lines.append("</pre>")
    lines.append("")

    if "market_cap_bucket" in df.columns:
        lines.append("<b>📦 Avg Score by Market Cap</b>")
        bucket_avg = (
            df.groupby("market_cap_bucket")[["Overall", "Q", "G", "V", "T"]]
            .mean()
            .round(1)
        )
        for bucket, row in bucket_avg.iterrows():
            lines.append(
                f"• <b>{bucket}</b>: Overall {row['Overall']}  "
                f"(Q{row['Q']} G{row['G']} V{row['V']} T{row['T']})"
            )
        lines.append("")

    if "sector" in df.columns:
        lines.append("<b>🏭 Top Sectors by Avg Overall</b>")
        sector_avg = (
            df.groupby("sector")["Overall"]
            .mean()
            .round(1)
            .sort_values(ascending=False)
            .head(6)
        )
        for sector, score in sector_avg.items():
            if sector and sector != "Unknown":
                lines.append(f"• {sector}: <b>{score}</b>")

    lines.append("")
    lines.append("<i>Q=Quality  G=Growth  V=Valuation  T=Technical</i>")
    lines.append("<i>Higher V = cheaper valuation</i>")
    lines.append("")
    lines.append("🔗 Full CSV available from local run / repo")

    return "\n".join(lines)


def send_scorecard_report(
    df: pd.DataFrame,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
    max_rows: int = 12,
) -> bool:
    """Format and send the full scorecard report to Telegram."""
    if df is None or df.empty:
        return send_message("⚠️ StockScorecard: No data to report.", bot_token, chat_id)

    text = format_scorecard_report(df, max_rows=max_rows)

    if len(text) > 4000:
        text = text[:3900] + "\n\n… (truncated)"

    return send_message(text, bot_token, chat_id)
