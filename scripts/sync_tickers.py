#!/usr/bin/env python3
"""
Sync config/tickers.yaml with all sector/strategy universe lists.

- Scans src/sectors/*.py and src/strategies/*.py for {"symbol","name"} entries
- Adds any new symbols to the registry
- Keeps existing status / last_checked / notes
- Does not delete symbols (safe; manual remove if needed)
"""

from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TICKERS_PATH = ROOT / "config" / "tickers.yaml"
SCAN_DIRS = [ROOT / "src" / "sectors", ROOT / "src" / "strategies"]


def discover() -> dict[str, dict]:
    found: dict[str, dict] = {}
    pattern = re.compile(r'\{"symbol":\s*"([^"]+)",\s*"name":\s*"([^"]+)"')
    for d in SCAN_DIRS:
        if not d.exists():
            continue
        for path in sorted(d.glob("*.py")):
            text = path.read_text(errors="ignore")
            rel = str(path.relative_to(ROOT))
            for m in pattern.finditer(text):
                sym = m.group(1).strip().upper()
                name = m.group(2).strip()
                if not sym:
                    continue
                if sym not in found:
                    found[sym] = {"name": name, "sources": [rel]}
                else:
                    if name and found[sym]["name"] == sym:
                        found[sym]["name"] = name
                    if rel not in found[sym]["sources"]:
                        found[sym]["sources"].append(rel)
    return found


def load_registry() -> dict:
    if not TICKERS_PATH.exists():
        return {
            "version": 1,
            "description": "Master ticker registry for StockScorecard.",
            "yahoo_suffix": ".NS",
            "tickers": [],
        }
    with TICKERS_PATH.open() as f:
        return yaml.safe_load(f) or {}


def save_registry(data: dict) -> None:
    TICKERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TICKERS_PATH.open("w") as f:
        yaml.dump(data, f, sort_keys=False, allow_unicode=True, width=120)


def sync() -> tuple[int, int, list[str]]:
    data = load_registry()
    existing = {row["symbol"].upper(): row for row in (data.get("tickers") or []) if row.get("symbol")}
    discovered = discover()

    added = []
    # Update sources/names for existing; add new
    for sym, info in sorted(discovered.items()):
        if sym in existing:
            row = existing[sym]
            # refresh name if richer
            if info["name"] and row.get("name") in (None, "", sym):
                row["name"] = info["name"]
            # merge sources
            srcs = list(row.get("sources") or [])
            for s in info["sources"]:
                if s not in srcs:
                    srcs.append(s)
            row["sources"] = srcs
        else:
            existing[sym] = {
                "symbol": sym,
                "name": info["name"],
                "sources": info["sources"],
                "status": "unknown",
                "last_checked": None,
                "notes": "added by sync",
            }
            added.append(sym)

    data["tickers"] = [existing[k] for k in sorted(existing.keys())]
    data["last_sync"] = datetime.now().isoformat(timespec="seconds")
    save_registry(data)
    return len(discovered), len(added), added


def main():
    total_discovered, n_added, added = sync()
    print(f"Discovered in code: {total_discovered}")
    print(f"Newly added to registry: {n_added}")
    if added:
        print("New symbols:")
        for s in added:
            print(f"  + {s}")
    else:
        print("No new symbols.")
    print(f"Registry → {TICKERS_PATH}")


if __name__ == "__main__":
    main()
