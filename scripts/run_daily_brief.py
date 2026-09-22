#!/usr/bin/env python3
"""Run full scan then send only Daily Brief (or brief after existing pipeline)."""
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-telegram", action="store_true")
    ap.add_argument("--no-ai", action="store_true", help="Rule-based only")
    ap.add_argument("--brief-only", action="store_true",
                    help="Run scan silently and send only Daily Brief")
    args = ap.parse_args()

    from src.orchestrator.runner import run_full_scan
    from src.intelligence.daily_brief import format_daily_brief_telegram
    from src.telegram_notify import send_message

    # Full scan; telegram layers on unless brief-only
    result = run_full_scan(send_telegram=not args.brief_only and not args.no_telegram)
    text = format_daily_brief_telegram(result, use_ai=not args.no_ai)
    print(text.replace("<b>","").replace("</b>","").replace("<i>","").replace("</i>",""))
    if not args.no_telegram:
        # If full pipeline already ran, still send brief; if brief-only, this is the only send
        ok = send_message(text)
        print("Daily Brief Telegram:", "sent" if ok else "FAILED")

if __name__ == "__main__":
    main()
