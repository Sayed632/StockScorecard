"""
Raising Stocks + Filtered Stocks

Layer 1 RAISING  – broad multi-day radar (recall)
  Pass: 5D >= +8% OR 10D >= +12%, and 10D not negative
  Top list by multi-day score; persistence tag STILL RAISING

Layer 2 FILTERED – action-oriented subset
  In Raising + liquidity-ish + not absurd data
  Tag EXTENDED if 1D spike or already very large short-term move
  CONTINUE / WAIT / SKIP style labels (rules, not broker orders)

Complements Wide Parallel Scan (1D volume bursts).
Past strength ≠ future profit. Not investment advice.
"""

from __future__ import annotations

from src.shared.time_ist import format_ist, now_ist

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import json
import logging
import math

from src.data_fetch.prices import fetch_price_history
from src.data_fetch.nse_universe import load_merged_universe

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
OUT_RAISING = ROOT / "config" / "rising_stocks_latest.json"
OUT_FILTERED = ROOT / "config" / "filtered_stocks_latest.json"
PREV_RAISING = ROOT / "config" / "raising_prev_symbols.json"

MAX_WORKERS = 16
TOP_RAISING = 50
TOP_FILTERED = 20

# Ideal thresholds (from product discussion)
THR_5D = 8.0
THR_10D = 12.0
THR_1D_EXTENDED = 12.0
THR_5D_EXTENDED = 22.0
MIN_PRICE_FILTERED = 15.0  # soft liquidity proxy


@dataclass
class Riser:
    symbol: str
    name: str
    price: float
    ret_1d: float
    ret_5d: float
    ret_10d: float
    score: float
    extended: bool = False
    still_raising: bool = False
    filter_label: str = ""  # CONTINUE / WAIT / SKIP
    filter_note: str = ""


def _load_prev_symbols() -> Set[str]:
    try:
        if PREV_RAISING.exists():
            data = json.loads(PREV_RAISING.read_text(encoding="utf-8"))
            return {str(s).upper() for s in (data.get("symbols") or [])}
    except Exception:
        pass
    return set()


def _save_prev_symbols(symbols: List[str]) -> None:
    try:
        PREV_RAISING.write_text(
            json.dumps(
                {"saved_at": format_ist(), "symbols": symbols[:80]},
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception as e:
        logger.debug("prev symbols save: %s", e)


def _metrics(symbol: str, name: str) -> Optional[Riser]:
    try:
        df = fetch_price_history(f"{symbol}.NS", period="1mo")
        if df is None or len(df) < 12:
            df = fetch_price_history(f"{symbol}.BO", period="1mo")
        if df is None or len(df) < 12:
            return None
        close_col = "close" if "close" in df.columns else "Close"
        c = df[close_col].astype(float).dropna()
        if len(c) < 12:
            return None
        px = float(c.iloc[-1])
        if px <= 0 or math.isnan(px):
            return None
        r1 = (px / float(c.iloc[-2]) - 1) * 100
        r5 = (px / float(c.iloc[-6]) - 1) * 100 if len(c) >= 6 else 0.0
        r10 = (px / float(c.iloc[-11]) - 1) * 100 if len(c) >= 11 else r5

        # RAISING gate
        if not (r5 >= THR_5D or r10 >= THR_10D):
            return None
        if r10 < 0:
            return None
        # Drop absurd prints
        if r1 > 80 or r5 > 120:
            return None

        # Prefer multi-day grind over pure 1D blow-off in ranking
        score = r5 * 1.5 + r10 * 1.1 + max(min(r1, 15), 0) * 0.25
        if r1 > 25:
            score *= 0.75

        extended = bool(r1 >= THR_1D_EXTENDED or r5 >= THR_5D_EXTENDED)

        return Riser(
            symbol=symbol.upper(),
            name=name or symbol,
            price=px,
            ret_1d=r1,
            ret_5d=r5,
            ret_10d=r10,
            score=score,
            extended=extended,
        )
    except Exception:
        return None


def _filter_label(r: Riser) -> tuple[str, str]:
    """CONTINUE / WAIT / SKIP — decision support only."""
    if r.price < MIN_PRICE_FILTERED:
        return "SKIP", "Below min price filter"
    if r.ret_1d > 40 or r.ret_5d > 90:
        return "SKIP", "Unreliable / extreme print"
    if r.extended and r.ret_1d >= THR_1D_EXTENDED:
        return "WAIT", "EXTENDED – spike chase risk"
    if r.extended and r.ret_5d >= THR_5D_EXTENDED and r.ret_1d >= 5:
        return "WAIT", "EXTENDED – large multi-day run"
    # Constructive multi-day, not extreme 1D
    if r.ret_5d >= THR_5D and r.ret_1d < THR_1D_EXTENDED and r.price >= MIN_PRICE_FILTERED:
        return "CONTINUE", "Raising + not extreme 1D"
    if r.ret_10d >= THR_10D and r.ret_1d < THR_1D_EXTENDED:
        return "CONTINUE", "10D strength + not extreme 1D"
    return "WAIT", "Raising but needs confirmation"


def run_rising_stocks(max_symbols: int = 1200) -> Dict[str, Any]:
    try:
        universe = load_merged_universe()
    except Exception:
        universe = []
    if len(universe) > max_symbols:
        universe = universe[:max_symbols]

    prev = _load_prev_symbols()
    risers: List[Riser] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(_metrics, s, n): s for s, n in universe}
        for fut in as_completed(futs):
            got = fut.result()
            if got:
                got.still_raising = got.symbol in prev
                risers.append(got)

    risers.sort(key=lambda x: -x.score)
    raising = risers[:TOP_RAISING]

    filtered: List[Riser] = []
    for r in raising:
        label, note = _filter_label(r)
        r.filter_label = label
        r.filter_note = note
        if label in ("CONTINUE", "WAIT"):
            filtered.append(r)
    # Prefer CONTINUE first, then WAIT; cap
    filtered.sort(
        key=lambda x: (0 if x.filter_label == "CONTINUE" else 1, -x.score)
    )
    filtered = filtered[:TOP_FILTERED]

    _save_prev_symbols([r.symbol for r in raising])

    result = {
        "scan_time": now_ist(),
        "universe_size": len(universe),
        "candidates": len(risers),
        "thresholds": {
            "5d": THR_5D,
            "10d": THR_10D,
            "1d_extended": THR_1D_EXTENDED,
            "5d_extended": THR_5D_EXTENDED,
            "min_price_filtered": MIN_PRICE_FILTERED,
        },
        "raising": raising,
        "filtered": filtered,
        # backward compat for old callers / Streamlit
        "top": raising[:15],
    }

    _persist(result)
    return result


def _persist(result: Dict[str, Any]) -> None:
    def pack(rows: List[Riser]) -> List[dict]:
        out = []
        for m in rows:
            out.append(
                {
                    "symbol": m.symbol,
                    "name": m.name,
                    "price": m.price,
                    "ret_1d": m.ret_1d,
                    "ret_5d": m.ret_5d,
                    "ret_10d": m.ret_10d,
                    "score": m.score,
                    "extended": m.extended,
                    "still_raising": m.still_raising,
                    "filter_label": m.filter_label,
                    "filter_note": m.filter_note,
                }
            )
        return out

    raising_items = pack(result.get("raising") or [])
    filtered_items = pack(result.get("filtered") or [])
    saved = format_ist(result.get("scan_time"))
    try:
        OUT_RAISING.write_text(
            json.dumps(
                {
                    "saved_at": saved,
                    "universe_size": result.get("universe_size"),
                    "candidates": result.get("candidates"),
                    "thresholds": result.get("thresholds"),
                    "items": raising_items,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        OUT_FILTERED.write_text(
            json.dumps(
                {
                    "saved_at": saved,
                    "items": filtered_items,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning("persist raising/filtered: %s", e)


def format_rising_stocks_telegram(result: Optional[Dict[str, Any]] = None) -> str:
    """Two-part Telegram: RAISING + FILTERED."""
    if result is None:
        result = run_rising_stocks()
    now = format_ist(result.get("scan_time"))
    raising: List[Riser] = result.get("raising") or []
    filtered: List[Riser] = result.get("filtered") or []
    thr = result.get("thresholds") or {}

    lines = [
        "<b>📈 RAISING STOCKS</b> <i>(multi-day radar)</i>",
        now,
        f"<i>Universe {result.get('universe_size', 0)} · "
        f"{result.get('candidates', 0)} passed · showing {len(raising)}</i>",
        f"<i>Gate: 5D≥{thr.get('5d', THR_5D)}% OR 10D≥{thr.get('10d', THR_10D)}%</i>",
        "",
        "<b>👩 Simple</b>",
        "• <b>Raising</b> = already moving up over days (watch list)",
        "• <b>Filtered</b> = stricter · CONTINUE/WAIT/SKIP",
        "• EXTENDED = far/fast — do not chase",
        "• Not auto-buy · use stops",
        "",
    ]

    if not raising:
        lines.append("• No names cleared Raising gates")
    else:
        for i, m in enumerate(raising[:40], 1):
            tags = []
            if m.still_raising:
                tags.append("STILL")
            if m.extended:
                tags.append("EXT")
            tag = f" [{','.join(tags)}]" if tags else ""
            lines.append(
                f"{i}. <b>{m.symbol}</b>{tag} – {m.name[:28]}\n"
                f"   ₹{m.price:.2f} · 1D {m.ret_1d:+.1f}% · "
                f"5D {m.ret_5d:+.1f}% · 10D {m.ret_10d:+.1f}%"
            )

    lines.append("")
    lines.append("<b>✅ FILTERED STOCKS</b> <i>(rules applied)</i>")
    if not filtered:
        lines.append("• None passed Filtered gates")
    else:
        for i, m in enumerate(filtered, 1):
            lab = m.filter_label or "WAIT"
            emoji = "🟢" if lab == "CONTINUE" else "🟡" if lab == "WAIT" else "⚪"
            lines.append(
                f"{i}. {emoji} <b>{m.symbol}</b> – {lab}\n"
                f"   {m.filter_note[:80]}\n"
                f"   ₹{m.price:.2f} · 5D {m.ret_5d:+.1f}% · 1D {m.ret_1d:+.1f}%"
            )

    lines.append("")
    lines.append(
        "<i>Raising = identify · Filtered = discipline · "
        "Wide scan still separate for 1D bursts. Not advice. StockScorecard</i>"
    )
    text = "\n".join(lines)
    if len(text) > 4000:
        # Prefer keeping Filtered section: trim Raising middle
        text = text[:3900] + "\n\n… (truncated)"
    return text
