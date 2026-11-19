#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.intelligence.backtest_engine import format_backtest_telegram, run_backtest
from src.telegram_notify import send_message


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", type=int, default=120, help="Max symbols to sample")
    ap.add_argument("--no-telegram", action="store_true")
    args = ap.parse_args()
    result = run_backtest(max_symbols=args.symbols)
    text = format_backtest_telegram(result)
    print(
        text.replace("<b>", "")
        .replace("</b>", "")
        .replace("<i>", "")
        .replace("</i>", "")
    )
    if not args.no_telegram:
        print("Telegram:", "sent" if send_message(text) else "FAILED")


if __name__ == "__main__":
    main()
