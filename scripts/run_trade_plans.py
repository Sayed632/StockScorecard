#!/usr/bin/env python3
"""Trade plans / open positions monitor."""
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.intelligence.trade_plans import format_trade_plans_telegram, mark_open, mark_closed
from src.telegram_notify import send_message

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-telegram", action="store_true")
    ap.add_argument("--mark-open", type=str, help="Symbol to mark as OPEN")
    ap.add_argument("--mark-closed", type=str, help="Symbol to mark CLOSED")
    args = ap.parse_args()
    if args.mark_open:
        print("mark open", args.mark_open, mark_open(args.mark_open))
    if args.mark_closed:
        print("mark closed", args.mark_closed, mark_closed(args.mark_closed))
    text = format_trade_plans_telegram()
    print(text.replace("<b>","").replace("</b>","").replace("<i>","").replace("</i>",""))
    if not args.no_telegram:
        print("Telegram:", "sent" if send_message(text) else "FAILED")
if __name__ == "__main__":
    main()
