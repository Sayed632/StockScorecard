"""
Profitable IPOs tracker – current return vs IPO issue price.

Uses config/ipo_watchlist.yaml (symbol + issue_price).
Fetches live/last price via yfinance; ranks by gain %.

Symbols without a resolvable NSE quote are skipped.
Not investment advice — IPO performance changes quickly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

import yaml

logger = logging.getLogger(__name__)

WATCHLIST = Path("config/ipo_watchlist.yaml")


@dataclass
class IPOResult:
    symbol: str
    name: str
    issue_price: float
    current_price: float
    gain_pct: float
    list_date: str
    resolved_ticker: str
    note: str = ""


def _load_watchlist() -> List[Dict[str, Any]]:
    if not WATCHLIST.exists():
        return []
    data = yaml.safe_load(WATCHLIST.read_text()) or {}
    return list(data.get("ipos") or [])


def _resolve_price(symbol: str) -> tuple[Optional[float], str]:
    """Try common NSE ticker variants."""
    import yfinance as yf

    candidates = [
        f"{symbol}.NS",
        f"{symbol}.BO",
    ]
    # Short aliases sometimes differ on Yahoo
    aliases = {
        "DHOOT": "DHOOTTRANS",
        "ADITYAINFO": "ADITYAINF",
    }
    if symbol in aliases:
        candidates = [f"{aliases[symbol]}.NS", f"{aliases[symbol]}.BO"] + candidates
    # Some IPOs use truncated or alternate codes
    for t in candidates:
        try:
            df = yf.Ticker(t).history(period="5d")
            if df is not None and len(df) > 0 and "Close" in df.columns:
                px = float(df["Close"].astype(float).iloc[-1])
                if px > 0:
                    return px, t
        except Exception:
            continue
    return None, ""


def run_ipo_performance(min_gain_pct: float = 0.0, limit: int = 20) -> Dict[str, Any]:
    rows: List[IPOResult] = []
    skipped = 0

    for item in _load_watchlist():
        sym = (item.get("symbol") or "").upper().strip()
        name = item.get("name") or sym
        issue = item.get("issue_price")
        list_date = str(item.get("list_date") or "—")
        if not sym or issue is None:
            skipped += 1
            continue
        try:
            issue_f = float(issue)
        except (TypeError, ValueError):
            skipped += 1
            continue
        if issue_f <= 0:
            skipped += 1
            continue

        px, ticker = _resolve_price(sym)
        if px is None:
            # try name-based fuzzy: skip for now
            skipped += 1
            logger.debug("IPO price miss: %s", sym)
            continue

        gain = (px / issue_f - 1.0) * 100.0
        note = ""
        if gain >= 100:
            note = "Multibagger vs issue price"
        elif gain >= 50:
            note = "Strong post-list performance"
        elif gain >= 0:
            note = "Above issue price"
        else:
            note = "Below issue price"

        rows.append(
            IPOResult(
                symbol=sym,
                name=name,
                issue_price=issue_f,
                current_price=px,
                gain_pct=gain,
                list_date=list_date,
                resolved_ticker=ticker,
                note=note,
            )
        )

    rows.sort(key=lambda r: -r.gain_pct)
    profitable = [r for r in rows if r.gain_pct >= min_gain_pct]
    losers = [r for r in rows if r.gain_pct < 0]

    return {
        "scan_time": datetime.now(),
        "all": rows,
        "profitable": [r for r in profitable if r.gain_pct >= 0][:limit],
        "losers": sorted(losers, key=lambda r: r.gain_pct)[:8],
        "skipped": skipped,
        "tracked": len(rows),
    }


def format_ipo_telegram(result: Optional[Dict[str, Any]] = None) -> str:
    if result is None:
        result = run_ipo_performance()
    now = result["scan_time"].strftime("%d %b %Y | %H:%M IST")
    profit: List[IPOResult] = result.get("profitable") or []
    losers: List[IPOResult] = result.get("losers") or []

    lines = [
        "<b>🆕 IPO PERFORMANCE</b> – vs issue price",
        now,
        "",
        f"<i>Tracked with live price: {result.get('tracked', 0)} · "
        f"Skipped (no issue price / no quote): {result.get('skipped', 0)}</i>",
        "<i>Gain = current price ÷ IPO issue price − 1. Not advice.</i>",
        "",
        "<b>🟢 Profitable vs issue</b>",
    ]

    if not profit:
        lines.append("• None resolved above issue today (check tickers in config)")
    else:
        for r in profit[:15]:
            badge = "🚀" if r.gain_pct >= 100 else ("📈" if r.gain_pct >= 30 else "✅")
            lines.append(
                f"• {badge} <b>{r.symbol}</b> – {r.name}\n"
                f"  Issue ₹{r.issue_price:,.0f} → Now ₹{r.current_price:,.1f} "
                f"(<b>{r.gain_pct:+.1f}%</b>)\n"
                f"  Listed: {r.list_date} · {r.note}"
            )

    if losers:
        lines.append("")
        lines.append("<b>🔴 Below issue price</b>")
        for r in losers[:6]:
            lines.append(
                f"• <b>{r.symbol}</b> – {r.name}\n"
                f"  Issue ₹{r.issue_price:,.0f} → Now ₹{r.current_price:,.1f} "
                f"(<b>{r.gain_pct:+.1f}%</b>)"
            )

    lines.append("")
    lines.append(
        "<i>Update symbols/issue prices in config/ipo_watchlist.yaml. "
        "StockScorecard – IPO Performance</i>"
    )
    return "\n".join(lines)
