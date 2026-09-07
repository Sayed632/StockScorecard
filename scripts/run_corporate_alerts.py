#!/usr/bin/env python3
"""Dedicated Corporate Alerts Telegram message (NSE filings, story style)."""
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.intelligence.corporate_alerts import format_corporate_alerts_telegram
from src.telegram_notify import send_message

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-telegram", action="store_true")
    args = ap.parse_args()
    text = format_corporate_alerts_telegram()
    plain = text.replace("<b>","").replace("</b>","").replace("<i>","").replace("</i>","")
    print(plain)
    if not args.no_telegram:
        ok = send_message(text)
        print("Telegram:", "sent" if ok else "FAILED")
if __name__ == "__main__":
    main()
