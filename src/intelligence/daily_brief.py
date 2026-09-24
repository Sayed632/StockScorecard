"""
Daily Brief – curated message AFTER all other Telegram outputs.

Existing messages stay unchanged. This is an extra review layer:
  1) Rule-based curator (always works, no API key)
  2) Optional AI polish if XAI_API_KEY / GROK_API_KEY / OPENAI_API_KEY is set

Design: prefer names that appear in multiple layers; keep lists short;
never invent numbers not present in the scan packet.
"""

from __future__ import annotations

from src.shared.time_ist import format_ist, now_ist

from datetime import datetime
from typing import Any, Dict, List, Optional
import logging
import os
import re

import requests

from src.shared.models import ScanResult, Action, StockIdea

logger = logging.getLogger(__name__)


def _idea_lines(ideas: List[StockIdea], buy_only: bool = True, limit: int = 5) -> List[str]:
    out = []
    for i in ideas:
        if buy_only and i.action not in (
            Action.BUY_NOW,
            Action.HOLD_INVEST,
            Action.DARK_HORSE_BUY,
            Action.DARK_HORSE_INVEST,
        ):
            # still allow WAIT in a separate bucket
            if i.action != Action.WAIT:
                continue
        prob = (i.extras or {}).get("probability")
        ptxt = f" | P={prob:.0%}" if isinstance(prob, (int, float)) else ""
        out.append(f"{i.symbol}|{i.score:.1f}|{i.reason[:120]}{ptxt}|{i.sector}")
        if len(out) >= limit * 2:
            break
    return out


def build_brief_packet(scan_result: ScanResult, extra_notes: Optional[List[str]] = None) -> Dict[str, Any]:
    """Structured packet for rule engine / optional AI."""
    swing_buy = [i for i in scan_result.swing_ideas if i.action == Action.BUY_NOW]
    swing_wait = [i for i in scan_result.swing_ideas if i.action == Action.WAIT]
    long_inv = [i for i in scan_result.long_term_ideas if i.action == Action.HOLD_INVEST]
    dark = list(scan_result.dark_horse_ideas or [])

    # Multi-layer: symbols in more than one list get boost
    counts: Dict[str, int] = {}
    for bucket in (swing_buy, long_inv, dark):
        for i in bucket:
            counts[i.symbol] = counts.get(i.symbol, 0) + 1

    def rank(ideas: List[StockIdea]) -> List[StockIdea]:
        return sorted(
            ideas,
            key=lambda x: (-counts.get(x.symbol, 0), -x.score),
        )

    return {
        "scan_time": scan_result.scan_time.isoformat(),
        "frequency": scan_result.frequency,
        "multi_layer": {k: v for k, v in counts.items() if v >= 2},
        "swing_buy": [
            {"symbol": i.symbol, "score": i.score, "reason": i.reason, "sector": i.sector,
             "layers": counts.get(i.symbol, 1)}
            for i in rank(swing_buy)[:8]
        ],
        "swing_wait": [
            {"symbol": i.symbol, "reason": i.reason}
            for i in swing_wait[:4]
        ],
        "long_term": [
            {"symbol": i.symbol, "score": i.score, "reason": i.reason, "sector": i.sector,
             "layers": counts.get(i.symbol, 1)}
            for i in rank(long_inv)[:8]
        ],
        "dark_horse": [
            {"symbol": i.symbol, "score": i.score, "reason": i.reason, "sector": i.sector,
             "layers": counts.get(i.symbol, 1)}
            for i in rank(dark)[:6]
        ],
        "sector_summary": dict(list((scan_result.sector_summary or {}).items())[:8]),
        "notes": list(scan_result.notes or [])[:5] + list(extra_notes or [])[:5],
    }


def format_brief_rule_based(packet: Dict[str, Any]) -> str:
    """Deterministic curated message – no external AI required."""
    now = format_ist()
    multi = packet.get("multi_layer") or {}

    lines = [
        "<b>🎯 DAILY BRIEF</b> <i>(curated review)</i>",
        now,
        f"Scan frequency: {packet.get('frequency', 1)}x",
        "",
        "<i>All detailed messages above stay unchanged. This is a short priority view.</i>",
        "",
    ]

    if multi:
        lines.append("<b>⭐ MULTI-LAYER (appeared in 2+ lists)</b>")
        for sym, n in sorted(multi.items(), key=lambda x: -x[1])[:6]:
            lines.append(f"• <b>{sym}</b> – {n} lists")
        lines.append("")

    swing = packet.get("swing_buy") or []
    lines.append("<b>🟢 SWING – priority</b>")
    if not swing:
        lines.append("• No high-priority swing buys today")
    else:
        for i, row in enumerate(swing[:5], 1):
            tag = " ⭐" if row.get("layers", 1) >= 2 else ""
            lines.append(
                f"{i}. <b>{row['symbol']}</b>{tag} – {row.get('reason', '')[:100]}"
            )
    lines.append("")

    waits = packet.get("swing_wait") or []
    if waits:
        lines.append("<b>🟡 WAIT</b>")
        for row in waits[:3]:
            lines.append(f"• {row['symbol']} – {row.get('reason', '')[:80]}")
        lines.append("")

    long_t = packet.get("long_term") or []
    lines.append("<b>🔵 LONG-TERM – priority</b>")
    if not long_t:
        lines.append("• No priority long-term names today")
    else:
        for i, row in enumerate(long_t[:5], 1):
            tag = " ⭐" if row.get("layers", 1) >= 2 else ""
            lines.append(
                f"{i}. <b>{row['symbol']}</b>{tag} – {row.get('reason', '')[:100]}"
            )
    lines.append("")

    dark = packet.get("dark_horse") or []
    if dark:
        lines.append("<b>🦄 DARK HORSE – priority</b>")
        for row in dark[:4]:
            tag = " ⭐" if row.get("layers", 1) >= 2 else ""
            lines.append(f"• <b>{row['symbol']}</b>{tag} – {row.get('reason', '')[:90]}")
        lines.append("")

    lines.append("<i>Curated from full scan. Not investment advice. Use stop-losses for swing.</i>")
    lines.append("<i>StockScorecard – Daily Brief</i>")
    return "\n".join(lines)


def _optional_ai_polish(packet: Dict[str, Any], base_text: str) -> Optional[str]:
    """
    Optional LLM rewrite. Uses xAI or OpenAI-compatible Chat Completions if key present.
    Returns None on skip/failure → caller keeps rule-based text.
    """
    api_key = (
        os.getenv("XAI_API_KEY")
        or os.getenv("GROK_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or ""
    ).strip()
    if not api_key:
        return None

    # xAI if XAI/GROK key, else OpenAI
    if os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY"):
        url = "https://api.x.ai/v1/chat/completions"
        model = os.getenv("XAI_MODEL", "grok-2-latest")
    else:
        url = "https://api.openai.com/v1/chat/completions"
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    system = (
        "You are a SEBI-style decision-support editor for Indian equities. "
        "Rewrite the brief into clear Telegram HTML (<b> <i> only). "
        "ONLY use symbols and reasons from the JSON packet. Do not invent prices, "
        "orders, or fundamentals. Max 5 swing and 5 long-term. Keep under 3500 chars. "
        "End with: Not investment advice."
    )
    user = f"Packet JSON:\n{packet}\n\nDraft to improve:\n{base_text}"

    try:
        r = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.2,
                "max_tokens": 1200,
            },
            timeout=45,
        )
        if not r.ok:
            logger.warning("AI brief HTTP %s: %s", r.status_code, r.text[:200])
            return None
        data = r.json()
        text = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not text or len(text) < 40:
            return None
        # light sanitize: no script tags
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.I | re.S)
        if "DAILY BRIEF" not in text.upper():
            text = "<b>🎯 DAILY BRIEF</b> <i>(AI-assisted review)</i>\n" + text
        return text
    except Exception as e:
        logger.warning("AI brief failed: %s", e)
        return None


def format_daily_brief_telegram(
    scan_result: ScanResult,
    extra_notes: Optional[List[str]] = None,
    use_ai: bool = True,
) -> str:
    packet = build_brief_packet(scan_result, extra_notes=extra_notes)
    base = format_brief_rule_based(packet)
    if use_ai:
        polished = _optional_ai_polish(packet, base)
        if polished:
            return polished
    return base
