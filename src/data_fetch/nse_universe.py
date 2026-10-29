"""
Full / broad NSE equity universe loader.

Layout for "scan all stocks → pick rallies":
  1) Refresh symbol master (NSE equity list + local yaml)
  2) Stage A: parallel light price scan (1D/5D/10D + volume)
  3) Stage B: score only top candidates as Fresh / Continuation / Extended
  4) Telegram shortlist

Honest limits: Yahoo rate limits + GH Actions time → we scan as many as practical
per run (configurable), rotating or full list when time allows.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple, Set
import csv
import io
import logging
import re

import requests
import yaml

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "config" / "nse_equity_cache.yaml"

# Public NSE equity list (may occasionally block; fail soft)
NSE_EQUITY_URLS = [
    "https://raw.githubusercontent.com/imanojkumar/NSE-India-All-Stocks-Tickers-Data/main/Ticker_List_NSE_India.csv",
    "https://raw.githubusercontent.com/feroze/YFinance-stock-history/master/EQUITY_L.csv",
    "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv",
    "https://archives.nseindia.com/content/equities/EQUITY_L.csv",
]


def _headers() -> dict:
    return {
        "User-Agent": "Mozilla/5.0 (compatible; StockScorecard/1.2)",
        "Accept": "text/csv,text/plain,*/*",
    }


def fetch_nse_equity_symbols(timeout: int = 45) -> List[Tuple[str, str]]:
    """Return [(SYMBOL, NAME), ...] from NSE equity CSV when reachable."""
    for url in NSE_EQUITY_URLS:
        try:
            r = requests.get(url, headers=_headers(), timeout=timeout)
            if not r.ok or len(r.content) < 500:
                continue
            text = r.content.decode("utf-8", errors="ignore")
            reader = csv.DictReader(io.StringIO(text))
            out: List[Tuple[str, str]] = []
            seen: Set[str] = set()
            for row in reader:
                # Common columns: SYMBOL, NAME OF COMPANY
                sym = (
                    row.get("SYMBOL")
                    or row.get("Symbol")
                    or row.get("symbol")
                    or ""
                ).strip().upper()
                name = (
                    row.get("NAME OF COMPANY")
                    or row.get("NAME")
                    or row.get("Company Name")
                    or sym
                ).strip()
                if not sym or sym in seen:
                    continue
                # skip derivatives-only weird codes
                if re.match(r"^\d+$", sym):
                    continue
                seen.add(sym)
                out.append((sym, name))
            if len(out) > 500:
                logger.info("NSE equity list loaded: %s symbols from %s", len(out), url)
                _save_cache(out)
                return out
        except Exception as e:
            logger.warning("NSE equity fetch %s: %s", url, e)
    return _load_cache()


def _save_cache(rows: List[Tuple[str, str]]) -> None:
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "count": len(rows),
            "symbols": [{"symbol": s, "name": n} for s, n in rows],
        }
        CACHE.write_text(yaml.dump(data, sort_keys=False), encoding="utf-8")
    except Exception as e:
        logger.debug("cache save: %s", e)


def _load_cache() -> List[Tuple[str, str]]:
    if not CACHE.exists():
        return []
    try:
        data = yaml.safe_load(CACHE.read_text(encoding="utf-8")) or {}
        out = []
        for row in data.get("symbols") or []:
            s = str(row.get("symbol") or "").upper()
            if s:
                out.append((s, str(row.get("name") or s)))
        return out
    except Exception:
        return []


def load_merged_universe(
    include_nse_master: bool = True,
    include_local_yaml: bool = True,
    include_sectors: bool = True,
) -> List[Tuple[str, str]]:
    """
    Master list for full-universe style scans.
    Order: NSE master (if any) + tickers.yaml + broad_universe + sector files.
    """
    seen: Set[str] = set()
    out: List[Tuple[str, str]] = []

    def add(sym: str, name: str = ""):
        sym = (sym or "").strip().upper()
        if not sym or sym in seen:
            return
        seen.add(sym)
        out.append((sym, name or sym))

    if include_nse_master:
        for s, n in fetch_nse_equity_symbols():
            add(s, n)

    if include_local_yaml:
        for path in (
            ROOT / "config" / "tickers.yaml",
            ROOT / "config" / "broad_universe.yaml",
        ):
            if not path.exists():
                continue
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            rows = data.get("tickers") or data.get("symbols") or []
            for row in rows:
                if isinstance(row, str):
                    add(row)
                else:
                    add(str(row.get("symbol") or ""), str(row.get("name") or ""))

    if include_sectors:
        for p in (ROOT / "src" / "sectors").glob("*.py"):
            if p.name.startswith("_"):
                continue
            text = p.read_text(errors="ignore")
            for m in re.finditer(
                r'\{"symbol":\s*"([^"]+)",\s*"name":\s*"([^"]+)"', text
            ):
                add(m.group(1), m.group(2))

    # Always force-include recent misses / high-priority
    for s, n in [
        ("CMLL", "Caliber Mining and Logistics Ltd"),
        ("HIKAL", "Hikal Ltd"),
        ("JUSTDIAL", "Just Dial Ltd"),
        ("ONESOURCE", "Onesource Specialty Pharma Ltd"),
    ]:
        add(s, n)

    # Listed IPOs from IPO performance watchlist
    ipo_path = ROOT / "config" / "ipo_watchlist.yaml"
    if ipo_path.exists():
        try:
            data = yaml.safe_load(ipo_path.read_text(encoding="utf-8")) or {}
            for row in data.get("ipos") or []:
                add(str(row.get("symbol") or ""), str(row.get("name") or ""))
        except Exception as e:
            logger.debug("ipo_watchlist merge: %s", e)

    # Pre-IPO file: only status == listed (if symbol provided)
    pre_path = ROOT / "config" / "pre_ipo_watchlist.yaml"
    if pre_path.exists():
        try:
            data = yaml.safe_load(pre_path.read_text(encoding="utf-8")) or {}
            for row in data.get("names") or []:
                if str(row.get("status") or "").lower() != "listed":
                    continue
                sym = str(row.get("symbol") or row.get("nse") or "").upper()
                if sym:
                    add(sym, str(row.get("name") or sym))
        except Exception as e:
            logger.debug("pre_ipo merge: %s", e)

    logger.info("Merged universe size: %s", len(out))
    return out
