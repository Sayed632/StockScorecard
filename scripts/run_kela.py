#!/usr/bin/env python3
"""Run Madhusudan Kela strategy sleeve and send separate Telegram message."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.strategies.madhusudan_kela import run_kela_strategy, format_kela_telegram
from src.telegram_notify import send_message


def main():
    parser = argparse.ArgumentParser(description="Madhusudan Kela strategy sleeve")
    parser.add_argument("--no-telegram", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("  Madhusudan Kela's Strategy – Multi-year sleeve")
    print("=" * 60)

    result = run_kela_strategy()
    text = format_kela_telegram(result)
    plain = (
        text.replace("<b>", "").replace("</b>", "")
        .replace("<i>", "").replace("</i>", "")
    )
    print(plain)

    if not args.no_telegram:
        ok = send_message(text)
        print("Telegram:", "sent" if ok else "FAILED")
    else:
        print("Telegram skipped")


if __name__ == "__main__":
    main()
