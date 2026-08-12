#!/usr/bin/env python3
"""
CLI entry point for StockScorecard.

Usage:
    python scripts/run_scorecard.py
    python scripts/run_scorecard.py --limit 30
    python scripts/run_scorecard.py --limit 50 --output data/my_scores.csv
    python scripts/run_scorecard.py --limit 40 --telegram
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

# Allow running from project root
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.scoring import run_scorecard, print_summary, load_config
from src.telegram_notify import send_scorecard_report


def main():
    parser = argparse.ArgumentParser(description="Q-G-V-T Stock Scorecard for Indian equities")
    parser.add_argument("--limit", type=int, default=30, help="Max number of stocks to score (default 30)")
    parser.add_argument("--output", type=str, default=None, help="CSV output path")
    parser.add_argument("--quiet", action="store_true", help="Less verbose output")
    parser.add_argument("--telegram", action="store_true", help="Send report to Telegram channel @nsepyscan")
    args = parser.parse_args()

    print("=" * 70)
    print("  StockScorecard  |  Q-G-V-T Four Factor Model")
    print("  Inspired by Moneycontrol / MarketsMojo style scores")
    print("=" * 70)
    print(f"Started : {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"Limit   : {args.limit} stocks")
    if args.telegram:
        print("Telegram: ON → @nsepyscan")
    print()

    df = run_scorecard(limit=args.limit, quiet=args.quiet)

    if df.empty:
        print("No data returned. Check internet / Yahoo Finance availability.")
        sys.exit(1)

    print_summary(df)

    # Save CSV
    out_path = args.output
    if out_path is None:
        out_dir = Path("data")
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / f"scorecard_{datetime.now():%Y%m%d}.csv"

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"\nSaved full results → {out_path}")
    print(f"Total stocks scored : {len(df)}")

    # Telegram delivery
    if args.telegram:
        print("\nSending report to Telegram channel @nsepyscan ...")
        ok = send_scorecard_report(df)
        if ok:
            print("✅ Report posted successfully to the channel.")
        else:
            print("❌ Failed to post to Telegram. Check bot permissions.")

    print("Done.")


if __name__ == "__main__":
    main()
