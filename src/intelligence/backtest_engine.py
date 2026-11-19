"""
Automated backtesting for Raising / Filtered style rules.

What it does:
  - Samples NSE universe symbols
  - Walks daily history (~1y)
  - Emits a signal when Raising gates fire (5D>=8% OR 10D>=12%)
  - Classifies EXTENDED (1D>=12% or 5D>=22%)
  - Measures forward returns +1d / +3d / +5d / +10d
  - Summarises win rates and average returns

Also supports appending live alerts to data/alert_history.jsonl
for future outcome tracking.

Not advice. Past results ≠ future performance. Yahoo data gaps apply.
"""

from __future__ import annotations

from src.shared.time_ist import format_ist, now_ist

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import logging
import math
import random

from src.data_fetch.prices import fetch_price_history
from src.data_fetch.nse_universe import load_merged_universe

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
OUT_JSON = ROOT / "config" / "backtest_latest.json"
HISTORY = ROOT / "config" / "alert_history.jsonl"

THR_5D = 8.0
THR_10D = 12.0
THR_1D_EXT = 12.0
THR_5D_EXT = 22.0
MIN_PRICE = 15.0
FORWARD_DAYS = (1, 3, 5, 10)


@dataclass
class ForwardHit:
    symbol: str
    date: str
    price: float
    ret_1d: float
    ret_5d: float
    ret_10d: float
    extended: bool
    filtered_ok: bool
    fwd: Dict[int, Optional[float]]  # days -> %


def _close_series(symbol: str):
    df = fetch_price_history(f"{symbol}.NS", period="1y")
    if df is None or len(df) < 80:
        df = fetch_price_history(f"{symbol}.BO", period="1y")
    if df is None or len(df) < 80:
        return None
    col = "close" if "close" in df.columns else "Close"
    s = df[col].astype(float).dropna()
    if len(s) < 80:
        return None
    return s


def _signals_from_closes(symbol: str, closes) -> List[ForwardHit]:
    """One signal max per stretch: fire on first day gates pass after not passing."""
    hits: List[ForwardHit] = []
    in_signal = False
    # closes is Series indexed by date
    vals = closes.values
    idx = closes.index
    n = len(vals)
    for i in range(12, n - 11):
        px = float(vals[i])
        if px <= 0 or math.isnan(px):
            in_signal = False
            continue
        r1 = (px / float(vals[i - 1]) - 1) * 100
        r5 = (px / float(vals[i - 5]) - 1) * 100
        r10 = (px / float(vals[i - 10]) - 1) * 100
        if r1 > 80 or r5 > 120:
            in_signal = False
            continue
        raising = (r5 >= THR_5D or r10 >= THR_10D) and r10 >= 0
        if not raising:
            in_signal = False
            continue
        if in_signal:
            # already in a raising stretch — skip to reduce clustered entries
            continue
        in_signal = True
        extended = r1 >= THR_1D_EXT or r5 >= THR_5D_EXT
        filtered_ok = (
            px >= MIN_PRICE
            and not (r1 >= THR_1D_EXT)  # WAIT on spike day
            and r5 < 90
        )
        fwd: Dict[int, Optional[float]] = {}
        for d in FORWARD_DAYS:
            j = i + d
            if j < n:
                fpx = float(vals[j])
                if fpx > 0:
                    fwd[d] = (fpx / px - 1) * 100
                else:
                    fwd[d] = None
            else:
                fwd[d] = None
        try:
            dt = str(idx[i])[:10]
        except Exception:
            dt = str(i)
        hits.append(
            ForwardHit(
                symbol=symbol,
                date=dt,
                price=px,
                ret_1d=r1,
                ret_5d=r5,
                ret_10d=r10,
                extended=extended,
                filtered_ok=filtered_ok,
                fwd=fwd,
            )
        )
    return hits


def _stats(hits: List[ForwardHit], only_filtered: bool = False) -> Dict[str, Any]:
    use = [h for h in hits if h.filtered_ok] if only_filtered else hits
    out: Dict[str, Any] = {"n_signals": len(use)}
    for d in FORWARD_DAYS:
        rets = [h.fwd[d] for h in use if h.fwd.get(d) is not None]
        if not rets:
            out[f"d{d}"] = {"n": 0}
            continue
        wins = sum(1 for r in rets if r > 0)
        out[f"d{d}"] = {
            "n": len(rets),
            "win_rate_pct": round(100.0 * wins / len(rets), 1),
            "avg_ret_pct": round(sum(rets) / len(rets), 2),
            "med_ret_pct": round(sorted(rets)[len(rets) // 2], 2),
        }
    ext = [h for h in use if h.extended]
    non = [h for h in use if not h.extended]
    def avg5(xs):
        rs = [h.fwd.get(5) for h in xs if h.fwd.get(5) is not None]
        return round(sum(rs) / len(rs), 2) if rs else None
    out["extended_share_pct"] = round(100.0 * len(ext) / len(use), 1) if use else 0
    out["avg_5d_extended"] = avg5(ext)
    out["avg_5d_not_extended"] = avg5(non)
    return out


def run_backtest(
    max_symbols: int = 120,
    seed: int = 42,
) -> Dict[str, Any]:
    try:
        universe = load_merged_universe()
    except Exception:
        universe = []
    if not universe:
        return {"error": "empty universe", "scan_time": now_ist()}

    rng = random.Random(seed)
    sample = universe[:]
    rng.shuffle(sample)
    sample = sample[:max_symbols]

    all_hits: List[ForwardHit] = []

    def work(sym_name):
        sym, name = sym_name
        s = _close_series(sym)
        if s is None:
            return []
        return _signals_from_closes(sym, s)

    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(work, sn): sn[0] for sn in sample}
        for fut in as_completed(futs):
            try:
                all_hits.extend(fut.result() or [])
            except Exception:
                continue

    result = {
        "saved_at": format_ist(),
        "scan_time": now_ist().isoformat() if hasattr(now_ist(), "isoformat") else str(now_ist()),
        "symbols_tested": len(sample),
        "total_signals": len(all_hits),
        "rules": {
            "raising": f"5D>={THR_5D}% OR 10D>={THR_10D}%",
            "extended": f"1D>={THR_1D_EXT}% OR 5D>={THR_5D_EXT}%",
            "filtered": f"price>={MIN_PRICE}, not 1D-extended spike entry",
            "entry": "first day of new raising stretch only",
        },
        "all_raising_signals": _stats(all_hits, only_filtered=False),
        "filtered_only": _stats(all_hits, only_filtered=True),
        "sample_signals": [
            {
                "symbol": h.symbol,
                "date": h.date,
                "price": round(h.price, 2),
                "ret_5d": round(h.ret_5d, 1),
                "extended": h.extended,
                "filtered_ok": h.filtered_ok,
                "fwd_5d": None if h.fwd.get(5) is None else round(h.fwd[5], 2),
            }
            for h in sorted(all_hits, key=lambda x: x.date, reverse=True)[:25]
        ],
    }
    try:
        OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    except Exception as e:
        logger.warning("backtest save: %s", e)
    return result


def append_alert_history(
    symbol: str,
    list_name: str,
    price: float,
    extras: Optional[Dict[str, Any]] = None,
) -> None:
    """Append one live alert row for later outcome scoring."""
    try:
        HISTORY.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": format_ist(),
            "symbol": symbol.upper(),
            "list": list_name,
            "price": price,
            **(extras or {}),
        }
        with HISTORY.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except Exception as e:
        logger.debug("alert history: %s", e)


def format_backtest_telegram(result: Optional[Dict[str, Any]] = None) -> str:
    if result is None:
        result = run_backtest()
    if result.get("error"):
        return f"<b>📉 BACKTEST</b>\nError: {result.get('error')}"

    a = result.get("all_raising_signals") or {}
    f = result.get("filtered_only") or {}
    d5a = a.get("d5") or {}
    d5f = f.get("d5") or {}
    lines = [
        "<b>📉 BACKTEST ENGINE</b>",
        result.get("saved_at") or format_ist(),
        f"<i>Symbols tested: {result.get('symbols_tested')} · "
        f"Signals: {result.get('total_signals')}</i>",
        "",
        "<b>Raising signals (all)</b>",
        f"· n={a.get('n_signals')} · 5D win {d5a.get('win_rate_pct', 'n/a')}% · "
        f"avg 5D {d5a.get('avg_ret_pct', 'n/a')}%",
        f"· Extended share {a.get('extended_share_pct')}% · "
        f"avg5d EXT {a.get('avg_5d_extended')} vs non-EXT {a.get('avg_5d_not_extended')}",
        "",
        "<b>Filtered only</b>",
        f"· n={f.get('n_signals')} · 5D win {d5f.get('win_rate_pct', 'n/a')}% · "
        f"avg 5D {d5f.get('avg_ret_pct', 'n/a')}%",
        "",
        "<i>First day of raising stretch · Yahoo sample · "
        "Past ≠ future · Not advice · StockScorecard</i>",
    ]
    return "\n".join(lines)
