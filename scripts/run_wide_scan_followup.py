#!/usr/bin/env python3
"""Next-session plan for yesterday's wide-scan movers."""
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.intelligence.wide_scan_followup import format_followup_telegram, load_watch
from src.telegram_notify import send_message

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-telegram", action="store_true")
    args = ap.parse_args()
    w = load_watch()
    print("Watch file:", "yes" if w else "EMPTY", "items", (w or {}).get("count"))
    text = format_followup_telegram()
    plain = text.replace("<b>","").replace("</b>","").replace("<i>","").replace("</i>","")
    print(plain)
    if not args.no_telegram:
        print("Telegram:", "sent" if send_message(text) else "FAILED")
if __name__ == "__main__":
    main()
