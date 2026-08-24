"""
Open Positions / Trade Plan layer.

- Builds candidate plans: entry zone, stop, target, horizon weeks
- Persists open plans in data/open_positions.json
- Ages plans (week counter) and flags exit alerts (stop / time / structure)

Decision support only — does not place orders.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import json
import logging
import math

import pandas as pd

from src.data_fetch.prices import fetch_price_history

logger = logging.getLogger(__name__)

POSITIONS_PATH = Path("data/open_positions.json")
RESULTS_PATH = Path("data/trade_plan_log.csv")


@dataclass
class TradePlan:
    symbol: str
    name: str
    status: str  # CANDIDATE / OPEN / EXIT_ALERT / CLOSED
    entry_low: float
    entry_high: float
    stop: float
    target: float
    horizon_weeks: int
    risk_pct: float
    reward_pct: float
    opened_on: Optional[str] = None  # ISO date when marked OPEN
    weeks_held: float = 0.0
    last_price: Optional[float] = None
    exit_reason: str = ""
    note: str = ""
    source: str = "auto"  # auto / manual


def _close_series(symbol: str) -> Optional[pd.Series]:
    df = fetch_price_history(symbol + ".NS", period="6mo")
    if df is None or len(df) < 30:
        return None
    cols = {c.lower(): c for c in df.columns}
    c = cols.get("close") or cols.get("adj close")
    if not c:
        return None
    return df[c].astype(float)


def _build_plan(symbol: str, name: str = "", horizon_weeks: int = 3) -> Optional[TradePlan]:
    close = _close_series(symbol)
    if close is None:
        return None
    px = float(close.iloc[-1])
    # Recent swing low (~15 sessions) for stop anchor
    swing_low = float(close.iloc[-16:-1].min()) if len(close) >= 16 else float(close.min())
    # Entry zone: slight pullback band under last close
    entry_high = round(px * 1.005, 2)
    entry_low = round(min(px * 0.98, (px + swing_low) / 2), 2)
    if entry_low >= entry_high:
        entry_low = round(px * 0.97, 2)
    stop = round(min(swing_low * 0.99, px * 0.92), 2)
    if stop >= entry_low:
        stop = round(entry_low * 0.96, 2)
    risk = entry_high - stop
    if risk <= 0:
        return None
    # ~2R target (swing)
    target = round(entry_high + 2.0 * risk, 2)
    risk_pct = (risk / entry_high) * 100
    reward_pct = ((target - entry_high) / entry_high) * 100
    note = f"Stop under ~15d swing low; target ~2R; hold up to {horizon_weeks} weeks"
    return TradePlan(
        symbol=symbol.upper(),
        name=name or symbol,
        status="CANDIDATE",
        entry_low=entry_low,
        entry_high=entry_high,
        stop=stop,
        target=target,
        horizon_weeks=horizon_weeks,
        risk_pct=round(risk_pct, 1),
        reward_pct=round(reward_pct, 1),
        last_price=px,
        note=note,
        source="auto",
    )


def _load_positions() -> List[Dict[str, Any]]:
    if not POSITIONS_PATH.exists():
        return []
    try:
        data = json.loads(POSITIONS_PATH.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_positions(rows: List[Dict[str, Any]]) -> None:
    POSITIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    POSITIONS_PATH.write_text(json.dumps(rows, indent=2))


def refresh_open_positions() -> List[TradePlan]:
    """Update weeks_held, last_price, EXIT_ALERT for OPEN rows."""
    raw = _load_positions()
    updated: List[Dict[str, Any]] = []
    plans: List[TradePlan] = []
    today = date.today()

    for row in raw:
        status = row.get("status", "CANDIDATE")
        sym = row.get("symbol", "")
        close = _close_series(sym)
        px = float(close.iloc[-1]) if close is not None else row.get("last_price")
        row["last_price"] = px

        if status == "OPEN" and row.get("opened_on"):
            try:
                opened = date.fromisoformat(str(row["opened_on"])[:10])
                days = (today - opened).days
                row["weeks_held"] = round(days / 7.0, 1)
            except Exception:
                row["weeks_held"] = row.get("weeks_held", 0)

            stop = float(row.get("stop") or 0)
            target = float(row.get("target") or 0)
            horizon = int(row.get("horizon_weeks") or 3)
            weeks = float(row.get("weeks_held") or 0)
            exit_reason = ""

            if px is not None and stop and px <= stop:
                row["status"] = "EXIT_ALERT"
                exit_reason = f"Stop threatened/hit (px {px:.1f} ≤ stop {stop:.1f})"
            elif px is not None and target and px >= target:
                row["status"] = "EXIT_ALERT"
                exit_reason = f"Target reached (px {px:.1f} ≥ target {target:.1f})"
            elif weeks >= horizon:
                row["status"] = "EXIT_ALERT"
                exit_reason = f"Time stop — held {weeks:.1f}w ≥ horizon {horizon}w"
            else:
                # soft structure: close below entry_low after 1 week
                entry_low = float(row.get("entry_low") or 0)
                if weeks >= 1 and px is not None and entry_low and px < entry_low * 0.98:
                    row["status"] = "EXIT_ALERT"
                    exit_reason = "Structure weak — below entry zone"

            row["exit_reason"] = exit_reason

        # rebuild dataclass
        plans.append(
            TradePlan(
                symbol=row.get("symbol", ""),
                name=row.get("name", ""),
                status=row.get("status", "CANDIDATE"),
                entry_low=float(row.get("entry_low") or 0),
                entry_high=float(row.get("entry_high") or 0),
                stop=float(row.get("stop") or 0),
                target=float(row.get("target") or 0),
                horizon_weeks=int(row.get("horizon_weeks") or 3),
                risk_pct=float(row.get("risk_pct") or 0),
                reward_pct=float(row.get("reward_pct") or 0),
                opened_on=row.get("opened_on"),
                weeks_held=float(row.get("weeks_held") or 0),
                last_price=row.get("last_price"),
                exit_reason=row.get("exit_reason") or "",
                note=row.get("note") or "",
                source=row.get("source") or "auto",
            )
        )
        updated.append(row)

    _save_positions(updated)
    return plans


def add_candidates_from_symbols(symbols: List[Tuple[str, str]], horizon_weeks: int = 3) -> List[TradePlan]:
    """Create CANDIDATE plans; merge into file without wiping OPEN."""
    existing = {r.get("symbol"): r for r in _load_positions()}
    new_plans: List[TradePlan] = []

    for sym, name in symbols:
        sym = sym.upper()
        plan = _build_plan(sym, name, horizon_weeks=horizon_weeks)
        if not plan:
            continue
        if sym in existing and existing[sym].get("status") in ("OPEN", "EXIT_ALERT"):
            # keep live trade
            continue
        existing[sym] = asdict(plan)
        new_plans.append(plan)

    _save_positions(list(existing.values()))
    return new_plans


def mark_open(symbol: str) -> bool:
    """User/system marks a candidate as OPEN (entry taken)."""
    rows = _load_positions()
    found = False
    for r in rows:
        if r.get("symbol", "").upper() == symbol.upper():
            r["status"] = "OPEN"
            r["opened_on"] = date.today().isoformat()
            r["weeks_held"] = 0
            r["exit_reason"] = ""
            found = True
    if found:
        _save_positions(rows)
    return found


def mark_closed(symbol: str, reason: str = "manual") -> bool:
    rows = _load_positions()
    found = False
    kept = []
    for r in rows:
        if r.get("symbol", "").upper() == symbol.upper():
            r["status"] = "CLOSED"
            r["exit_reason"] = reason
            found = True
            # drop closed from active file (optional: log first)
        else:
            kept.append(r)
    if found:
        _save_positions(kept)
    return found


def auto_seed_from_horizon_and_hot(max_candidates: int = 12) -> List[TradePlan]:
    """Seed candidates from Horizon BUY + top Hot (non-extreme preferred)."""
    symbols: List[Tuple[str, str]] = []
    try:
        from src.intelligence.horizon_monitor import run_horizon_monitor
        hz = run_horizon_monitor(max_rows=40)
        for row in hz.get("rows") or []:
            if row.action.startswith("🟢"):
                symbols.append((row.symbol, row.name))
    except Exception as e:
        logger.warning("horizon seed: %s", e)

    try:
        from src.intelligence.hot_stocks import run_hot_stocks
        hot = run_hot_stocks(limit=15)
        for s in hot.get("stocks") or []:
            # skip extreme for auto entry candidates
            if s.heat.startswith("🔥"):
                continue
            symbols.append((s.symbol, s.name))
    except Exception as e:
        logger.warning("hot seed: %s", e)

    # unique preserve order
    seen = set()
    uniq = []
    for s, n in symbols:
        if s not in seen:
            seen.add(s)
            uniq.append((s, n))
    return add_candidates_from_symbols(uniq[:max_candidates])


def format_trade_plans_telegram() -> str:
    # seed + refresh
    try:
        auto_seed_from_horizon_and_hot()
    except Exception as e:
        logger.warning("auto seed: %s", e)
    plans = refresh_open_positions()

    now = datetime.now().strftime("%d %b %Y | %H:%M IST")
    lines = [
        "<b>📋 TRADE PLANS / OPEN POSITIONS</b>",
        now,
        "",
        "<i>Entry zone · Stop · Target · Week counter · Exit alerts</i>",
        "<i>Does not place orders. Decision support only.</i>",
        "",
    ]

    exits = [p for p in plans if p.status == "EXIT_ALERT"]
    opens = [p for p in plans if p.status == "OPEN"]
    cands = [p for p in plans if p.status == "CANDIDATE"]

    lines.append("<b>🚨 EXIT ALERTS</b>")
    if exits:
        for p in exits[:8]:
            lines.append(
                f"• <b>{p.symbol}</b> – {p.exit_reason or 'Review exit'}\n"
                f"  px {p.last_price} | stop {p.stop} | target {p.target} | held {p.weeks_held}w"
            )
    else:
        lines.append("• None")
    lines.append("")

    lines.append("<b>📂 OPEN</b>")
    if opens:
        for p in opens[:8]:
            lines.append(
                f"• <b>{p.symbol}</b> week {p.weeks_held}/{p.horizon_weeks}\n"
                f"  entry {p.entry_low}–{p.entry_high} | stop {p.stop} | tgt {p.target}\n"
                f"  risk {p.risk_pct}% → reward ~{p.reward_pct}%"
            )
    else:
        lines.append("• None — mark OPEN in data/open_positions.json when you enter")
    lines.append("")

    lines.append("<b>🌱 CANDIDATES (plans)</b>")
    if cands:
        for p in cands[:10]:
            lines.append(
                f"• <b>{p.symbol}</b> hold ≤{p.horizon_weeks}w\n"
                f"  BUY zone {p.entry_low}–{p.entry_high}\n"
                f"  STOP {p.stop} | TARGET {p.target} | R:R ~1:2\n"
                f"  {p.note}"
            )
    else:
        lines.append("• No candidates seeded")
    lines.append("")
    lines.append(
        "<i>To track a trade: set status=OPEN and opened_on=YYYY-MM-DD in data/open_positions.json</i>"
    )
    lines.append("<i>StockScorecard – Trade Plans</i>")
    return "\n".join(lines)
