#!/usr/bin/env python3
"""Daily digest – one action sheet (also sent with full daily run)."""
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.intelligence.daily_digest import format_daily_digest_telegram
from src.telegram_notify import send_message

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-telegram", action="store_true")
    args = ap.parse_args()
    text = format_daily_digest_telegram()
    print(text.replace("<b>","").replace("</b>","").replace("<i>","").replace("</i>",""))
    if not args.no_telegram:
        print("Telegram:", "sent" if send_message(text) else "FAILED")
if __name__ == "__main__":
    main()
