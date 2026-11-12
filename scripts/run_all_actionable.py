#!/usr/bin/env python3
"""
Single entry: run actionable StockScorecard flows in order and send Telegram.

Does not replace individual crons — use for one-click / one morning pack.
Continues on failure so one broken module does not stop the rest.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# (name, cmd, timeout_seconds)
STEPS = [
    ("GIFT Nifty", [sys.executable, "scripts/run_gift_nifty.py"], 180),
    ("Wide Parallel Scan", [sys.executable, "scripts/run_wide_scan.py"], 1200),
    ("Rising Stocks", [sys.executable, "scripts/run_rising_stocks.py"], 1200),
    ("Wide Scan Next-Day Plan", [sys.executable, "scripts/run_wide_scan_followup.py"], 600),
    ("Swing Catcher", [sys.executable, "scripts/run_swing_catcher.py"], 900),
    # Full sector decision is heavy — allow up to 40 minutes
    ("Daily Decision (+ Brief)", [sys.executable, "scripts/run_decision.py"], 2400),
    ("Peer Watch", [sys.executable, "scripts/run_peer_watch.py"], 600),
    ("Context Intelligence", [sys.executable, "scripts/run_context_intelligence.py"], 300),
    ("News layer", [sys.executable, "scripts/run_news.py"], 300),
]


def main() -> int:
    print("StockScorecard — ALL ACTIONABLE (sequential)\n")
    results = []
    for name, cmd, limit in STEPS:
        print(f"\n======== {name} (timeout {limit}s) ========")
        t0 = time.time()
        try:
            r = subprocess.run(
                cmd,
                cwd=str(ROOT),
                timeout=limit,
            )
            ok = r.returncode == 0
            elapsed = time.time() - t0
            results.append((name, ok, elapsed, r.returncode))
            print(
                f"→ {name}: {'OK' if ok else 'FAIL'} ({r.returncode}) in {elapsed:.0f}s"
            )
        except subprocess.TimeoutExpired:
            elapsed = time.time() - t0
            results.append((name, False, elapsed, -1))
            print(f"→ {name}: TIMEOUT after {elapsed:.0f}s (limit {limit}s)")
        except Exception as e:
            results.append((name, False, 0.0, -2))
            print(f"→ {name}: ERROR {e}")

    ok_n = sum(1 for _, ok, _, _ in results if ok)
    summary = (
        f"<b>⚡ ALL ACTIONABLE — run complete</b>\n"
        f"{ok_n}/{len(results)} steps OK\n\n"
    )
    for name, ok, sec, code in results:
        mark = "✅" if ok else "❌"
        extra = " timeout" if code == -1 else ""
        summary += f"{mark} {name} ({sec:.0f}s){extra}\n"
    summary += (
        "\n<i>Individual messages above (if secrets OK). "
        "Not advice. StockScorecard</i>"
    )
    try:
        from src.telegram_notify import send_message

        send_message(summary)
    except Exception as e:
        print("summary telegram failed", e)
        print(summary)

    # Soft success: majority OK so artifact commit can still run
    if ok_n >= max(1, len(results) - 2):
        return 0
    return 1 if ok_n < len(results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
