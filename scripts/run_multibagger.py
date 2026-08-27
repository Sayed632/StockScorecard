#!/usr/bin/env python3
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.intelligence.multibagger_screener import format_multibagger_telegram
from src.telegram_notify import send_message
ap = argparse.ArgumentParser(); ap.add_argument("--no-telegram", action="store_true"); a = ap.parse_args()
t = format_multibagger_telegram(); print(t.replace("<b>","").replace("</b>","").replace("<i>","").replace("</i>",""))
if not a.no_telegram: print("Telegram:", "sent" if send_message(t) else "FAILED")
