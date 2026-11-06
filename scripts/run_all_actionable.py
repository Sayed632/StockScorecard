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

# Order: market tone → captures → decisions → context
STEPS = [
    ("GIFT Nifty", [sys.executable, "scripts/run_gift_nifty.py"]),
    ("Wide Parallel Scan", [sys.executable, "scripts/run_wide_scan.py"]),
    ("Wide Scan Next-Day Plan", [sys.executable, "scripts/run_wide_scan_followup.py"]),
    ("Swing Catcher", [sys.executable, "scripts/run_swing_catcher.py"]),
    ("Daily Decision (+ Brief)", [sys.executable, "scripts/run_decision.py"]),
    ("Peer Watch", [sys.executable, "scripts/run_peer_watch.py"]),
    ("Context Intelligence", [sys.executable, "scripts/run_context_intelligence.py"]),
    ("News layer", [sys.executable, "scripts/run_news.py"]),
]


def main() -> int:
    print("StockScorecard — ALL ACTIONABLE (sequential)\n")
    results = []
    for name, cmd in STEPS:
        print(f"\n======== {name} ========")
        t0 = time.time()
        try:
            r = subprocess.run(
                cmd,
                cwd=str(ROOT),
                timeout=900,
            )
            ok = r.returncode == 0
            results.append((name, ok, time.time() - t0, r.returncode))
            print(f"→ {name}: {'OK' if ok else 'FAIL'} ({r.returncode}) in {time.time()-t0:.0f}s")
        except subprocess.TimeoutExpired:
            results.append((name, False, 900, -1))
            print(f"→ {name}: TIMEOUT")
        except Exception as e:
            results.append((name, False, 0, -2))
            print(f"→ {name}: ERROR {e}")

    ok_n = sum(1 for _, ok, _, _ in results if ok)
    summary = (
        f"<b>⚡ ALL ACTIONABLE — run complete</b>\n"
        f"{ok_n}/{len(results)} steps OK\n\n"
    )
    for name, ok, sec, code in results:
        mark = "✅" if ok else "❌"
        summary += f"{mark} {name} ({sec:.0f}s)\n"
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

    return 0 if ok_n == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
