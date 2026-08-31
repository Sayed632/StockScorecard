"""
Pre-IPO / IPO pipeline watch.

Curated watchlist (config/pre_ipo_watchlist.yaml) grouped by status.
When a name is marked listed + has a Yahoo symbol, it can be handed
to the existing IPO performance module separately.

This is a status tracker — not a pre-IPO share purchase product.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging

import yaml

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
WATCHLIST = ROOT / "config" / "pre_ipo_watchlist.yaml"

STATUS_ORDER = [
    "open",
    "rhp",
    "sebi_observed",
    "drhp_filed",
    "on_radar",
    "listed",
]

STATUS_LABEL = {
    "open": "🟢 IPO OPEN / LIVE WINDOW",
    "rhp": "🟢 RHP (public offer docs)",
    "sebi_observed": "🟡 SEBI OBSERVED / NEAR CLEARANCE",
    "drhp_filed": "🟡 DRHP FILED",
    "on_radar": "⚪ ON RADAR (not filed / early)",
    "listed": "🔵 RECENTLY LISTED",
}


@dataclass
class PreIpoName:
    id: str
    name: str
    sector: str
    status: str
    note: str
    issue_size_hint: str
    expected_window: str


def load_watchlist() -> List[PreIpoName]:
    if not WATCHLIST.exists():
        logger.warning("Missing %s", WATCHLIST)
        return []
    raw = yaml.safe_load(WATCHLIST.read_text(encoding="utf-8")) or {}
    out: List[PreIpoName] = []
    for row in raw.get("names") or []:
        st = str(row.get("status") or "on_radar").lower().strip()
        out.append(
            PreIpoName(
                id=str(row.get("id") or row.get("name") or ""),
                name=str(row.get("name") or ""),
                sector=str(row.get("sector") or ""),
                status=st,
                note=str(row.get("note") or ""),
                issue_size_hint=str(row.get("issue_size_hint") or "—"),
                expected_window=str(row.get("expected_window") or "TBA"),
            )
        )
    return out


def collect_pre_ipo() -> Dict[str, Any]:
    names = load_watchlist()
    by_status: Dict[str, List[PreIpoName]] = {s: [] for s in STATUS_ORDER}
    for n in names:
        key = n.status if n.status in by_status else "on_radar"
        by_status[key].append(n)
    return {
        "scan_time": datetime.now(),
        "by_status": by_status,
        "total": len(names),
    }


def format_pre_ipo_telegram(result: Optional[Dict[str, Any]] = None) -> str:
    if result is None:
        result = collect_pre_ipo()
    now = result["scan_time"].strftime("%d %b %Y | %H:%M IST")
    by_status: Dict[str, List[PreIpoName]] = result.get("by_status") or {}

    lines = [
        "<b>📋 PRE-IPO / IPO PIPELINE</b>",
        now,
        "",
        "<i>Watch status only — not a recommendation to buy unlisted shares.</i>",
        "<i>Verify on SEBI / merchant banker / your broker before acting.</i>",
        "",
    ]

    shown = 0
    for st in STATUS_ORDER:
        items = by_status.get(st) or []
        if not items:
            continue
        lines.append(f"<b>{STATUS_LABEL.get(st, st.upper())}</b>")
        for n in items:
            lines.append(f"• <b>{n.name}</b> — {n.sector}")
            if n.issue_size_hint and n.issue_size_hint != "—":
                lines.append(f"  Size: {n.issue_size_hint}")
            if n.expected_window:
                lines.append(f"  Window: {n.expected_window}")
            if n.note:
                note = n.note if len(n.note) <= 140 else n.note[:137] + "…"
                lines.append(f"  <i>{note}</i>")
            shown += 1
        lines.append("")

    if shown == 0:
        lines.append("• Watchlist empty — edit config/pre_ipo_watchlist.yaml")
        lines.append("")

    lines.append(
        f"<i>Total tracked: {result.get('total', 0)} · "
        "When listed, use IPO performance module. StockScorecard</i>"
    )
    return "\n".join(lines)
