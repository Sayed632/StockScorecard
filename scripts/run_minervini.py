#!/usr/bin/env python3
"""Minervini/O'Neil strategy sleeve – separate Telegram message."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.strategies.minervini_oneil import run_minervini_oneil, format_mo_telegram
from src.telegram_notify import send_message


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-telegram", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("  Minervini/O'Neil Strategy – Swing sleeve")
    print("=" * 60)

    result = run_minervini_oneil()
    text = format_mo_telegram(result)
    print(text.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", ""))

    if not args.no_telegram:
        ok = send_message(text)
        print("Telegram:", "sent" if ok else "FAILED")


if __name__ == "__main__":
    main()
