"""
Sector Heat Map + Top-5 per rising sector (Swing & Long-term).

Telegram-friendly "heat map" (emoji bars) ranked by multi-month sector strength.
For each Leading / Improving sector: top 5 swing and top 5 long-term from that
sector's scanner.

Does not replace existing sector-rotation message; this is a richer companion.
"""

from __future__ import annotations

from src.shared.time_ist import format_ist, now_ist

from datetime import datetime
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


def _heat_bar(score: float, max_score: float = 100.0) -> str:
    """5-block emoji bar from relative score."""
    if max_score <= 0:
        n = 0
    else:
        n = int(round(max(0.0, min(5.0, (score / max_score) * 5))))
    return "█" * n + "░" * (5 - n)


def _label_emoji(label: str) -> str:
    return {
        "Leading": "🔥",
        "Improving": "📈",
        "Soft": "😐",
        "Lagging": "❄️",
    }.get(label, "•")


def run_sector_heatmap(top_n: int = 5, rising_only: bool = True) -> Dict[str, Any]:
    from src.intelligence.sector_rotation import run_sector_rotation
    from src.orchestrator.runner import SECTOR_REGISTRY, load_config
    from src.shared.models import Action

    rotation = run_sector_rotation()
    sectors = list(rotation.get("sectors") or [])
    # sectors may be SectorStrength objects or dicts
    ranked = []
    for s in sectors:
        if hasattr(s, "name"):
            ranked.append({
                "name": s.name,
                "ss_sector": s.ss_sector,
                "label": s.label,
                "score": float(s.score),
                "ret_1m": s.ret_1m,
                "ret_3m": s.ret_3m,
                "ret_6m": s.ret_6m,
                "rel_1m": s.rel_1m,
            })
        elif isinstance(s, dict):
            ranked.append(s)

    ranked.sort(key=lambda x: -x.get("score", 0))
    max_sc = max((x.get("score") or 0) for x in ranked) if ranked else 100.0
    if max_sc <= 0:
        max_sc = 100.0

    rising = [
        x for x in ranked
        if (x.get("label") in ("Leading", "Improving")) or not rising_only
    ]
    if not rising and ranked:
        rising = ranked[:5]  # fallback: top score sectors

    cfg = load_config()
    # Deduplicate ss_sector keys (Bank + PSU Bank both map banks_financials)
    seen_keys = set()
    per_sector: List[Dict[str, Any]] = []

    for sec in rising:
        key = sec.get("ss_sector") or ""
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        scanner_cls = SECTOR_REGISTRY.get(key)
        if not scanner_cls:
            per_sector.append({
                "heat": sec,
                "swing": [],
                "long_term": [],
                "error": f"no scanner for {key}",
            })
            continue
        try:
            scanner = scanner_cls(config=cfg)
            result = scanner.run()
            swing = [
                i for i in (result.get("swing") or [])
                if getattr(i, "action", None) == Action.BUY_NOW
                or str(getattr(i, "action", "")).find("BUY") >= 0
            ]
            # if filter too strict, take top by score
            if not swing:
                swing = list(result.get("swing") or [])
            long_t = [
                i for i in (result.get("long_term") or [])
                if getattr(i, "action", None) == Action.HOLD_INVEST
                or "INVEST" in str(getattr(i, "action", ""))
            ]
            if not long_t:
                long_t = list(result.get("long_term") or [])
            swing = sorted(swing, key=lambda x: -x.score)[:top_n]
            long_t = sorted(long_t, key=lambda x: -x.score)[:top_n]
            per_sector.append({
                "heat": sec,
                "swing": swing,
                "long_term": long_t,
                "error": None,
            })
        except Exception as e:
            logger.warning("heatmap sector %s: %s", key, e)
            per_sector.append({
                "heat": sec,
                "swing": [],
                "long_term": [],
                "error": str(e)[:80],
            })

    return {
        "scan_time": now_ist(),
        "ranked": ranked,
        "max_score": max_sc,
        "per_sector": per_sector,
        "nifty": rotation.get("benchmark") or rotation.get("nifty"),
    }


def format_sector_heatmap_telegram(result: Optional[Dict[str, Any]] = None) -> str:
    if result is None:
        result = run_sector_heatmap(top_n=5, rising_only=True)

    now = format_ist(result["scan_time"])
    ranked = result.get("ranked") or []
    max_sc = float(result.get("max_score") or 100)
    per = result.get("per_sector") or []

    lines = [
        "<b>🌡️ SECTOR HEAT MAP</b>",
        now,
        "",
        "<i>Hotter = stronger multi-month sector relative strength</i>",
        "",
        "<b>HEAT MAP (all tracked sectors)</b>",
    ]

    for s in ranked[:12]:
        bar = _heat_bar(float(s.get("score") or 0), max_sc)
        em = _label_emoji(str(s.get("label") or ""))
        r1 = s.get("ret_1m")
        r1t = f"{r1:+.1f}%" if isinstance(r1, (int, float)) else "—"
        lines.append(
            f"{em} <code>{bar}</code> <b>{s.get('name')}</b> "
            f"({s.get('label')}) 1M {r1t}"
        )

    lines.append("")
    lines.append("<b>TOP 5 FROM RISING SECTORS</b>")
    lines.append("<i>Leading / Improving only · Swing + Long-term</i>")
    lines.append("")

    if not per:
        lines.append("• No rising-sector stock lists available")
    else:
        for block in per:
            h = block.get("heat") or {}
            em = _label_emoji(str(h.get("label") or ""))
            lines.append(
                f"{em} <b>{h.get('name')}</b> · {h.get('label')} "
                f"(score {float(h.get('score') or 0):.0f})"
            )
            if block.get("error"):
                lines.append(f"   ⚠️ {block['error']}")
            swing = block.get("swing") or []
            long_t = block.get("long_term") or []
            lines.append("   <b>🟢 Swing top 5</b>")
            if not swing:
                lines.append("   • —")
            else:
                for i, idea in enumerate(swing[:5], 1):
                    lines.append(
                        f"   {i}. <b>{idea.symbol}</b> – {idea.reason[:70]} "
                        f"(sc {idea.score:.0f})"
                    )
            lines.append("   <b>🔵 Long-term top 5</b>")
            if not long_t:
                lines.append("   • —")
            else:
                for i, idea in enumerate(long_t[:5], 1):
                    lines.append(
                        f"   {i}. <b>{idea.symbol}</b> – {idea.reason[:70]} "
                        f"(sc {idea.score:.0f})"
                    )
            lines.append("")

    lines.append(
        "<i>Heat from sector indices; stocks from sector scanners. "
        "Not advice. Verify before acting. StockScorecard</i>"
    )

    text = "\n".join(lines)
    # Telegram hard limit – keep under ~4000
    if len(text) > 4000:
        text = text[:3900] + "\n\n… (truncated)"
    return text
