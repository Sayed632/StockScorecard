#!/usr/bin/env python3
"""News intelligence layer – market-moving headlines."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.intelligence.news_layer import fetch_market_news, format_news_telegram_message
from src.telegram_notify import send_message


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-telegram", action="store_true")
    args = parser.parse_args()

    items = fetch_market_news()
    text = format_news_telegram_message(items)
    print(text.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", ""))
    if not args.no_telegram:
        print("Telegram:", "sent" if send_message(text) else "FAILED")


if __name__ == "__main__":
    main()
