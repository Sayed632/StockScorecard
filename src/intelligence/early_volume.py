"""
Early Volume — Claudeown idea, StockScorecard implementation.

Flag unusual volume vs recent average before price is fully extended.
Complements Wide scan (which often catches moves after large % gains).
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
OUT = ROOT / "config" / "early_volume_latest.json"

MAX_WORKERS = 14
TOP_N = 15
MIN_VOL_RATIO = 2.5
MAX_1D_FOR_EARLY = 8.0  # if already up a lot, it's late (wide-scan territory)


@dataclass
class Hit:
    symbol: str
    name: str
    price: float
    ret_1d: float
    vol_ratio: float
    score: float


def _one(sym: str, name: str) -> Optional[Hit]:
    try:
        df = fetch_price_history(f"{sym}.NS", period="1mo")
        if df is None or len(df) < 15:
            df = fetch_price_history(f"{sym}.BO", period="1mo")
        if df is None or len(df) < 15:
            return None
        close = df["close" if "close" in df.columns else "Close"].astype(float)
        vol = df["volume" if "volume" in df.columns else "Volume"].astype(float)
        px = float(close.iloc[-1])
        if px <= 0 or math.isnan(px):
            return None
        r1 = (px / float(close.iloc[-2]) - 1) * 100
        v_today = float(vol.iloc[-1])
        v_avg = float(vol.iloc[-11:-1].mean())
        if v_avg <= 0 or v_today <= 0:
            return None
        ratio = v_today / v_avg
        if ratio < MIN_VOL_RATIO:
            return None
        if r1 > MAX_1D_FOR_EARLY:
            return None  # already extended on price — leave to wide scan
        if r1 < -3:
            return None
        score = ratio * 10 + max(r1, 0) * 1.5
        return Hit(sym.upper(), name or sym, px, r1, ratio, score)
    except Exception:
        return None


def run_early_volume(max_symbols: int = 800) -> Dict[str, Any]:
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
                "ret_1d": h.ret_1d,
                "vol_ratio": round(h.vol_ratio, 2),
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


def format_early_volume_telegram(payload: Optional[Dict[str, Any]] = None) -> str:
    if payload is None:
        payload = run_early_volume()
    lines = [
        "<b>📢 EARLY VOLUME</b> <i>(Claudeown idea → StockScorecard)</i>",
        payload.get("saved_at") or format_ist(),
        f"<i>Vol ≥ {MIN_VOL_RATIO}x recent avg · 1D ≤ {MAX_1D_FOR_EARLY}% (not already extended)</i>",
        "",
    ]
    items = payload.get("items") or []
    if not items:
        lines.append("• No early-volume names right now")
    else:
        for i, it in enumerate(items, 1):
            lines.append(
                f"{i}. <b>{it['symbol']}</b> – {(it.get('name') or '')[:28]}\n"
                f"   ₹{it['price']:.2f} · 1D {it['ret_1d']:+.1f}% · "
                f"Vol {it['vol_ratio']}x"
            )
    lines.append("")
    lines.append("<i>Earlier heads-up than top gainers · Not advice · StockScorecard</i>")
    return "\n".join(lines)
