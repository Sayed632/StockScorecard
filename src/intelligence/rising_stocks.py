"""
Rising Stocks flow – multi-day price strength (not only 1-day spikes).

Complements Wide Parallel Scan:
  - Wide scan  → sharp 1D + volume bursts
  - Rising     → 5D / ~10D grind higher, still constructive

Free Yahoo + parallel pull; top list to Telegram.
"""

from __future__ import annotations

from src.shared.time_ist import format_ist, now_ist

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import logging
import math

from src.data_fetch.prices import fetch_price_history
from src.data_fetch.nse_universe import load_merged_universe

logger = logging.getLogger(__name__)

MAX_WORKERS = 16
TOP_N = 15


@dataclass
class Riser:
    symbol: str
    name: str
    price: float
    ret_1d: float
    ret_5d: float
    ret_10d: float
    score: float


def _metrics(symbol: str, name: str) -> Optional[Riser]:
    try:
        df = fetch_price_history(f"{symbol}.NS", period="1mo")
        if df is None or len(df) < 12:
            df = fetch_price_history(f"{symbol}.BO", period="1mo")
        if df is None or len(df) < 12:
            return None
        c = df["close"].astype(float).dropna()
        if len(c) < 12:
            return None
        px = float(c.iloc[-1])
        if px <= 0 or math.isnan(px):
            return None
        r1 = (px / float(c.iloc[-2]) - 1) * 100
        r5 = (px / float(c.iloc[-6]) - 1) * 100 if len(c) >= 6 else 0.0
        r10 = (px / float(c.iloc[-11]) - 1) * 100 if len(c) >= 11 else r5
        # Rising criteria: multi-day up, not only a one-day spike
        if r5 < 5 and r10 < 8:
            return None
        if r10 < 0:
            return None
        # Prefer grind: reward 5D/10D more than pure 1D blow-off
        score = r5 * 1.4 + r10 * 1.0 + max(r1, 0) * 0.35
        # Soft-penalize absurd data
        if r1 > 40 or r5 > 80:
            score *= 0.3
        return Riser(
            symbol=symbol,
            name=name or symbol,
            price=px,
            ret_1d=r1,
            ret_5d=r5,
            ret_10d=r10,
            score=score,
        )
    except Exception:
        return None


def run_rising_stocks(max_symbols: int = 900) -> Dict[str, Any]:
    try:
        universe = load_merged_universe()
    except Exception:
        universe = []
    if len(universe) > max_symbols:
        universe = universe[:max_symbols]

    risers: List[Riser] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(_metrics, s, n): s for s, n in universe}
        for fut in as_completed(futs):
            got = fut.result()
            if got:
                risers.append(got)

    risers.sort(key=lambda x: -x.score)
    top = risers[:TOP_N]
    return {
        "scan_time": now_ist(),
        "universe_size": len(universe),
        "candidates": len(risers),
        "top": top,
    }


def format_rising_stocks_telegram(result: Optional[Dict[str, Any]] = None) -> str:
    if result is None:
        result = run_rising_stocks()
    now = format_ist(result.get("scan_time"))
    top: List[Riser] = result.get("top") or []
    lines = [
        "<b>📈 RISING STOCKS</b> <i>(multi-day strength)</i>",
        now,
        f"<i>Universe {result.get('universe_size', 0)} · "
        f"{result.get('candidates', 0)} passed 5D/10D filters · top {len(top)}</i>",
        "",
        "<b>👩 Simple</b>",
        "• These are <b>rising over several days</b>, not only today’s spike",
        "• Different from 🌐 Wide Scan (1D burst)",
        "• Still not auto-buy — use stops / Next-Day style caution",
        "",
    ]
    if not top:
        lines.append("• No names cleared multi-day filters")
    else:
        for i, m in enumerate(top, 1):
            lines.append(
                f"{i}. <b>{m.symbol}</b> – {m.name[:36]}\n"
                f"   ₹{m.price:.2f} · 1D {m.ret_1d:+.1f}% · "
                f"5D {m.ret_5d:+.1f}% · ~10D {m.ret_10d:+.1f}%"
            )
    lines.append("")
    lines.append(
        "<i>Criteria: multi-day rise (5D/10D). Complements Wide Scan. "
        "Not advice. StockScorecard</i>"
    )
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3900] + "\n\n… (truncated)"
    return text
