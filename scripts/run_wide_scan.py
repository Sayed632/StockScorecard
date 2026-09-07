#!/usr/bin/env python3
"""Wide parallel day-mover scan across full registry + broad universe."""
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.intelligence.wide_parallel_scan import format_wide_scan_telegram
from src.telegram_notify import send_message

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-telegram", action="store_true")
    args = ap.parse_args()
    text = format_wide_scan_telegram()
    print(text.replace("<b>","").replace("</b>","").replace("<i>","").replace("</i>",""))
    if not args.no_telegram:
        print("Telegram:", "sent" if send_message(text) else "FAILED")
if __name__ == "__main__":
    main()
