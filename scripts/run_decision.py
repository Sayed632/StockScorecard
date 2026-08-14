#!/usr/bin/env python3
"""
StockScorecard – Main Decision Runner

Usage:
    python scripts/run_decision.py
    python scripts/run_decision.py --no-telegram
    python scripts/run_decision.py --force-frequency 2
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.orchestrator.runner import run_full_scan


def main():
    parser = argparse.ArgumentParser(description="StockScorecard Daily Decision System")
    parser.add_argument("--no-telegram", action="store_true", help="Do not send to Telegram")
    parser.add_argument("--force-frequency", type=int, choices=[1, 2, 3], default=None,
                        help="Force scanning frequency (1/2/3)")
    args = parser.parse_args()

    print("=" * 70)
    print("  StockScorecard  |  Full Decision System")
    print("  Swing + Long-term + Dark Horse | All Sectors Framework")
    print("=" * 70)

    result = run_full_scan(
        send_telegram=not args.no_telegram,
        force_frequency=args.force_frequency,
    )

    print(f"\nSummary:")
    print(f"  Swing ideas     : {len(result.swing_ideas)}")
    print(f"  Long-term ideas : {len(result.long_term_ideas)}")
    print(f"  Dark Horse ideas: {len(result.dark_horse_ideas)}")
    print(f"  Frequency used  : {result.frequency}x")
    print("Done.")


if __name__ == "__main__":
    main()