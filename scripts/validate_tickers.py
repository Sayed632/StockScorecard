#!/usr/bin/env python3
"""
Weekly ticker maintenance.

- Loads config/tickers.yaml
- Checks each symbol via Yahoo (.NS)
- Marks: ok | not_found | no_price | error
- Writes report to data/ticker_validation_YYYYMMDD.csv
- Updates status/last_checked in config/tickers.yaml
- Optional Telegram summary
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TICKERS_PATH = ROOT / "config" / "tickers.yaml"
OUT_DIR = ROOT / "data"


def load_registry() -> dict:
    with TICKERS_PATH.open() as f:
        return yaml.safe_load(f)


def save_registry(data: dict) -> None:
    with TICKERS_PATH.open("w") as f:
        yaml.dump(data, f, sort_keys=False, allow_unicode=True, width=120)


def check_symbol(symbol: str, suffix: str = ".NS") -> tuple[str, str]:
    """Return (status, notes)."""
    import yfinance as yf

    yahoo = symbol + suffix
    try:
        t = yf.Ticker(yahoo)
        # fast_info / history
        hist = t.history(period="5d")
        if hist is None or len(hist) == 0:
            # try info
            info = {}
            try:
                info = t.info or {}
            except Exception:
                pass
            if not info.get("regularMarketPrice") and not info.get("currentPrice"):
                return "not_found", f"No history/price for {yahoo}"
            return "ok", "info only"
        last = float(hist["Close"].iloc[-1])
        return "ok", f"last={last:.2f}"
    except Exception as e:
        msg = str(e)[:120]
        if "delisted" in msg.lower() or "not found" in msg.lower():
            return "not_found", msg
        return "error", msg


def main():
    parser = argparse.ArgumentParser(description="Validate StockScorecard tickers")
    parser.add_argument("--telegram", action="store_true", help="Send summary to Telegram")
    parser.add_argument("--limit", type=int, default=0, help="Limit symbols (debug)")
    parser.add_argument("--sync", action="store_true", help="Sync registry from sector/strategy files first")
    args = parser.parse_args()

    if args.sync:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "sync_tickers", ROOT / "scripts" / "sync_tickers.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        n_disc, n_add, added = mod.sync()
        print(f"Sync: discovered={n_disc} added={n_add} {added[:10] if added else []}")

    data = load_registry()
    suffix = data.get("yahoo_suffix", ".NS")
    tickers = data.get("tickers") or []
    if args.limit:
        tickers = tickers[: args.limit]

    now = datetime.now()
    rows = []
    counts = {"ok": 0, "not_found": 0, "no_price": 0, "error": 0, "unknown": 0}

    print(f"Validating {len(tickers)} tickers…")
    for i, row in enumerate(tickers, 1):
        sym = row["symbol"]
        status, notes = check_symbol(sym, suffix)
        row["status"] = status
        row["last_checked"] = now.isoformat(timespec="seconds")
        row["notes"] = notes
        counts[status] = counts.get(status, 0) + 1
        rows.append({
            "symbol": sym,
            "name": row.get("name", ""),
            "status": status,
            "notes": notes,
            "checked_at": row["last_checked"],
        })
        if i % 25 == 0:
            print(f"  …{i}/{len(tickers)}")

    # persist registry
    data["tickers"] = tickers  # full list was mutated if limit=0; if limited, only partial — reload safe path
    if not args.limit:
        save_registry(data)

    OUT_DIR.mkdir(exist_ok=True)
    out_csv = OUT_DIR / f"ticker_validation_{now.strftime('%Y%m%d')}.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["symbol", "name", "status", "notes", "checked_at"])
        w.writeheader()
        w.writerows(rows)

    summary = (
        f"Ticker validation {now.strftime('%d %b %Y')}\n"
        f"Total: {len(rows)} | OK: {counts.get('ok',0)} | "
        f"Not found: {counts.get('not_found',0)} | Error: {counts.get('error',0)}"
    )
    print(summary)
    print(f"Report → {out_csv}")

    problems = [r for r in rows if r["status"] != "ok"]
    if problems:
        print("Problems:")
        for r in problems[:30]:
            print(f"  {r['symbol']}: {r['status']} – {r['notes']}")

    if args.telegram:
        try:
            from src.telegram_notify import send_message
            lines = [
                "<b>🛠 Ticker maintenance (weekly)</b>",
                now.strftime("%d %b %Y | %H:%M IST"),
                "",
                f"Total checked: <b>{len(rows)}</b>",
                f"✅ OK: {counts.get('ok',0)}",
                f"❌ Not found: {counts.get('not_found',0)}",
                f"⚠️ Error: {counts.get('error',0)}",
                "",
            ]
            if problems:
                lines.append("<b>Needs attention</b>")
                for r in problems[:15]:
                    lines.append(f"• <b>{r['symbol']}</b> – {r['status']}: {r['notes'][:80]}")
            else:
                lines.append("All tickers OK.")
            lines.append("")
            lines.append("<i>StockScorecard – config/tickers.yaml</i>")
            send_message("\n".join(lines))
            print("Telegram sent")
        except Exception as e:
            print("Telegram failed:", e)

    # exit non-zero if many failures (useful in CI)
    bad = counts.get("not_found", 0) + counts.get("error", 0)
    if bad > max(5, len(rows) * 0.15):
        sys.exit(1)


if __name__ == "__main__":
    main()
