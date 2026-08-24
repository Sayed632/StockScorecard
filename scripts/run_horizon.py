#!/usr/bin/env python3
"""Horizon Monitor – multi-week buy/hold/sell policy."""
import argparse
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.intelligence.horizon_monitor import run_horizon_monitor, format_horizon_telegram
from src.telegram_notify import send_message

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--no-telegram", action="store_true")
    args = p.parse_args()
    result = run_horizon_monitor()
    text = format_horizon_telegram(result)
    print(text.replace("<b>","").replace("</b>","").replace("<i>","").replace("</i>",""))
    if not args.no_telegram:
        print("Telegram:", "sent" if send_message(text) else "FAILED")

if __name__ == "__main__":
    main()
