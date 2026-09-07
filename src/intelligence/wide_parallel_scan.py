"""
Wide Parallel Scan – intelligent daily mover capture beyond curated sector lists.

Design (honest limits):
  - True "every NSE stock every second" is not feasible on free Yahoo + GH Actions.
  - We scan the FULL registry (tickers.yaml ≈ 200+) PLUS optional broad list in parallel.
  - Stage 1 (fast): parallel price pull, rank by 1D / 5D / volume surge.
  - Stage 2: top movers get catalyst tags and Telegram "WIDE SCAN" message.

Goal: catch names like sharp day-movers (e.g. HIKAL-style) that curated swing lists may miss.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging
import math
import re

import yaml

from src.data_fetch.prices import fetch_price_history
from src.intelligence.catalysts import format_price

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
TICKERS_YAML = ROOT / "config" / "tickers.yaml"
BROAD_YAML = ROOT / "config" / "broad_universe.yaml"

MAX_WORKERS = 16
TOP_N = 20


@dataclass
class Mover:
    symbol: str
    name: str
    price: float
    ret_1d: float
    ret_5d: Optional[float]
    vol_ratio: Optional[float]
    score: float
    note: str


def _load_symbols() -> List[Tuple[str, str]]:
    """(symbol, name) from tickers.yaml + broad_universe.yaml."""
    seen = set()
    out: List[Tuple[str, str]] = []

    def add(sym: str, name: str = ""):
        sym = (sym or "").strip().upper()
        if not sym or sym in seen:
            return
        seen.add(sym)
        out.append((sym, name or sym))

    if TICKERS_YAML.exists():
        data = yaml.safe_load(TICKERS_YAML.read_text(encoding="utf-8")) or {}
        for row in data.get("tickers") or []:
            add(str(row.get("symbol") or ""), str(row.get("name") or ""))

    if BROAD_YAML.exists():
        data = yaml.safe_load(BROAD_YAML.read_text(encoding="utf-8")) or {}
        for row in data.get("symbols") or []:
            if isinstance(row, str):
                add(row)
            else:
                add(str(row.get("symbol") or ""), str(row.get("name") or ""))

    # Always include sector file symbols (may exceed yaml if sync lagged)
    for p in (ROOT / "src" / "sectors").glob("*.py"):
        text = p.read_text(errors="ignore")
        for m in re.finditer(r'\{"symbol":\s*"([^"]+)",\s*"name":\s*"([^"]+)"', text):
            add(m.group(1), m.group(2))

    return out


def _score_one(sym: str, name: str) -> Optional[Mover]:
    try:
        df = fetch_price_history(sym + ".NS", period="3mo")
        if df is None or len(df) < 8:
            return None
        close = df["close"].astype(float).dropna()
        if len(close) < 8:
            return None
        px = float(close.iloc[-1])
        if math.isnan(px) or px <= 0:
            return None
        prev = float(close.iloc[-2])
        if prev <= 0:
            return None
        r1 = (px / prev - 1.0) * 100.0
        r5 = None
        if len(close) >= 6:
            p5 = float(close.iloc[-6])
            if p5 > 0:
                r5 = (px / p5 - 1.0) * 100.0

        vol_ratio = None
        if "volume" in df.columns:
            vol = df["volume"].astype(float).dropna()
            if len(vol) >= 15:
                avg = float(vol.iloc[-15:-1].mean())
                last = float(vol.iloc[-1])
                if avg > 0:
                    vol_ratio = last / avg

        # Intelligent priority: big day move + volume confirmation, not already dead
        score = 0.0
        notes = []
        if r1 >= 5:
            score += min(r1, 25) * 1.2
            notes.append(f"1D {r1:+.1f}%")
        elif r1 >= 3:
            score += r1
            notes.append(f"1D {r1:+.1f}%")
        else:
            return None  # only surface meaningful day moves

        if r5 is not None and r5 >= 8:
            score += min(r5, 40) * 0.35
            notes.append(f"5D {r5:+.0f}%")

        if vol_ratio is not None and vol_ratio >= 1.5:
            score += min(vol_ratio, 5) * 4
            notes.append(f"Vol {vol_ratio:.1f}x")

        if score < 6:
            return None

        return Mover(
            symbol=sym,
            name=name,
            price=px,
            ret_1d=r1,
            ret_5d=r5,
            vol_ratio=vol_ratio,
            score=score,
            note=" · ".join(notes),
        )
    except Exception as e:
        logger.debug("wide %s: %s", sym, e)
        return None


def run_wide_parallel_scan(
    max_workers: int = MAX_WORKERS,
    top_n: int = TOP_N,
) -> Dict[str, Any]:
    universe = _load_symbols()
    movers: List[Mover] = []

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_score_one, s, n): s for s, n in universe}
        for fut in as_completed(futs):
            m = fut.result()
            if m is not None:
                movers.append(m)

    movers.sort(key=lambda x: -x.score)
    return {
        "scan_time": datetime.now(),
        "universe_size": len(universe),
        "movers_found": len(movers),
        "movers": movers[:top_n],
    }


def format_wide_scan_telegram(result: Optional[Dict[str, Any]] = None) -> str:
    if result is None:
        result = run_wide_parallel_scan()
    now = result["scan_time"].strftime("%d %b %Y | %H:%M IST")
    movers: List[Mover] = result.get("movers") or []

    lines = [
        "<b>🌐 WIDE PARALLEL SCAN</b>",
        now,
        "",
        f"<i>Universe {result.get('universe_size', 0)} names · "
        f"{result.get('movers_found', 0)} day-movers · top {len(movers)}</i>",
        "<i>Intelligent filter: 1D strength + volume. Not every NSE stock tick.</i>",
        "",
    ]

    if not movers:
        lines.append("• No strong day-movers above threshold")
    else:
        lines.append("<b>📈 TODAY’S CAPTURED MOVES</b>")
        for i, m in enumerate(movers, 1):
            lines.append(
                f"{i}. <b>{m.symbol}</b> – {m.name[:40]}"
            )
            lines.append(
                f"   {format_price(m.price)} | {m.note} | score {m.score:.0f}"
            )

    lines.append("")
    lines.append(
        "<i>Parallel scan catches moves outside curated Swing lists. "
        "Verify volume & news. Use stops. StockScorecard</i>"
    )
    return "\n".join(lines)
