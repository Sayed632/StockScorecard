"""
Steady Climber — Claudeown idea, StockScorecard implementation.

Prefer smooth multi-month uptrends (high R² on log price) over spike-and-crash.
Complements Raising (short multi-day) with a slower quality trend screen.
"""

from __future__ import annotations

from src.shared.time_ist import format_ist, now_ist

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import logging
import math

from src.data_fetch.prices import fetch_price_history
from src.data_fetch.nse_universe import load_merged_universe

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "config" / "steady_climber_latest.json"

MAX_WORKERS = 12
TOP_N = 15
MIN_R2 = 0.75
MIN_RET_60 = 12.0  # ~3 month style window using 60 sessions
MAX_1D = 10.0


@dataclass
class Hit:
    symbol: str
    name: str
    price: float
    ret_60: float
    r2: float
    score: float


def _r2_log_trend(closes) -> Optional[float]:
    """R² of linear fit on log prices over the series."""
    import numpy as np

    y = np.log(closes.astype(float).values)
    n = len(y)
    if n < 40:
        return None
    x = np.arange(n, dtype=float)
    # linear regression
    xm, ym = x.mean(), y.mean()
    num = ((x - xm) * (y - ym)).sum()
    den = ((x - xm) ** 2).sum()
    if den <= 0:
        return None
    slope = num / den
    intercept = ym - slope * xm
    pred = intercept + slope * x
    ss_res = ((y - pred) ** 2).sum()
    ss_tot = ((y - ym) ** 2).sum()
    if ss_tot <= 0:
        return None
    return float(1.0 - ss_res / ss_tot)


def _one(sym: str, name: str) -> Optional[Hit]:
    try:
        df = fetch_price_history(f"{sym}.NS", period="6mo")
        if df is None or len(df) < 50:
            df = fetch_price_history(f"{sym}.BO", period="6mo")
        if df is None or len(df) < 50:
            return None
        c = df["close" if "close" in df.columns else "Close"].astype(float).dropna()
        if len(c) < 50:
            return None
        px = float(c.iloc[-1])
        if px < 20 or math.isnan(px):
            return None
        r1 = (px / float(c.iloc[-2]) - 1) * 100
        if r1 > MAX_1D:
            return None
        window = c.iloc[-61:] if len(c) >= 61 else c
        ret_60 = (float(window.iloc[-1]) / float(window.iloc[0]) - 1) * 100
        if ret_60 < MIN_RET_60:
            return None
        r2 = _r2_log_trend(window)
        if r2 is None or r2 < MIN_R2:
            return None
        score = r2 * 50 + min(ret_60, 80) * 0.4
        return Hit(sym.upper(), name or sym, px, ret_60, r2, score)
    except Exception:
        return None


def run_steady_climber(max_symbols: int = 700) -> Dict[str, Any]:
    try:
        uni = load_merged_universe()[:max_symbols]
    except Exception:
        uni = []
    hits: List[Hit] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(_one, s, n): s for s, n in uni}
        for fut in as_completed(futs):
            h = fut.result()
            if h:
                hits.append(h)
    hits.sort(key=lambda x: -x.score)
    top = hits[:TOP_N]
    payload = {
        "saved_at": format_ist(),
        "universe": len(uni),
        "candidates": len(hits),
        "items": [
            {
                "symbol": h.symbol,
                "name": h.name,
                "price": h.price,
                "ret_60": round(h.ret_60, 1),
                "r2": round(h.r2, 3),
                "score": round(h.score, 1),
            }
            for h in top
        ],
    }
    try:
        OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as e:
        logger.debug("save: %s", e)
    return payload


def format_steady_climber_telegram(payload: Optional[Dict[str, Any]] = None) -> str:
    if payload is None:
        payload = run_steady_climber()
    lines = [
        "<b>📈 STEADY CLIMBER</b> <i>(Claudeown idea → StockScorecard)</i>",
        payload.get("saved_at") or format_ist(),
        f"<i>Smooth trend R²≥{MIN_R2} · ~60d return ≥{MIN_RET_60}% · not a 1D spike</i>",
        "",
    ]
    items = payload.get("items") or []
    if not items:
        lines.append("• No steady climbers matched")
    else:
        for i, it in enumerate(items, 1):
            lines.append(
                f"{i}. <b>{it['symbol']}</b> – {(it.get('name') or '')[:28]}\n"
                f"   ₹{it['price']:.2f} · ~60d {it['ret_60']:+.1f}% · R² {it['r2']}"
            )
    lines.append("")
    lines.append("<i>Quality uptrend screen · Not advice · StockScorecard</i>")
    return "\n".join(lines)
