"""
Madhusudan Kela–inspired strategy module (separate sleeve).

IMPORTANT
- This is NOT official advice from Madhusudan Kela.
- We track selected *disclosed* holdings (stake >1% style public data)
  and score them with a multi-year, bottom-up lens aligned to his
  publicly described philosophy.
- Horizon: typically 3–5+ years (NOT swing).
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from src.data_fetch.fundamentals import fetch_basic_fundamentals
from src.data_fetch.prices import fetch_price_history
from src.factors.quality import score_quality
from src.factors.growth import score_growth
from src.factors.valuation import score_valuation
from src.factors.technical import score_technical
from src.sectors._helpers import market_cap_bucket


# Selected disclosed / widely reported holdings (expandable)
KELA_UNIVERSE = [
    {"symbol": "CHOICEIN", "name": "Choice International Ltd", "note": "Core large holding (reported)"},
    {"symbol": "SANGAMIND", "name": "Sangam (India) Ltd", "note": "Textiles / diversified"},
    {"symbol": "WINDMACH", "name": "Windsor Machines Ltd", "note": "Capital goods / industrial"},
    {"symbol": "KOPRAN", "name": "Kopran Ltd", "note": "Pharma"},
    {"symbol": "RPTECH", "name": "Rashi Peripherals Ltd", "note": "Distribution / tech hardware"},
    {"symbol": "SGFIN", "name": "SG Finserve Ltd", "note": "NBFC / supply-chain finance"},
    {"symbol": "IBULHSGFIN", "name": "Indiabulls Housing Finance", "note": "Housing finance"},
    {"symbol": "SUBAM", "name": "Subam Papers Ltd", "note": "Paper / packaging"},
    {"symbol": "REPRO", "name": "Repro India Ltd", "note": "Print / publishing services"},
    {"symbol": "EMKAY", "name": "Emkay Global Financial Services", "note": "Broking / financials"},
    {"symbol": "BOMDYEING", "name": "Bombay Dyeing & Mfg Co", "note": "Textiles / realty legacy"},
    {"symbol": "IRIS", "name": "IRIS Business Services Ltd", "note": "RegTech"},
    {"symbol": "UNIECOM", "name": "Unicommerce eSolutions Ltd", "note": "E-commerce SaaS"},
]


@dataclass
class KelaIdea:
    symbol: str
    name: str
    action: str          # emoji + label
    reason: str
    score: float
    market_cap_cr: Optional[float] = None
    bucket: str = ""
    note: str = ""
    extras: Dict[str, Any] = field(default_factory=dict)


def _score_kela_style(stock: Dict[str, Any]) -> Optional[KelaIdea]:
    """
    Multi-year bottom-up lens:
    - Quality + growth primary
    - Valuation secondary
    - Mild technical only for entry timing tag (not for long thesis)
    """
    symbol = stock.get("symbol", "")
    name = stock.get("name", symbol)
    mcap = stock.get("market_cap_cr")
    note = stock.get("_kela_note", "")

    q = score_quality(stock)
    g = score_growth(stock)
    v = score_valuation(stock)
    t = score_technical(stock.get("_prices"))

    # Kela-like: quality + growth heavy; mid/small preference soft bonus
    score = 0.40 * q + 0.35 * g + 0.15 * v + 0.10 * t
    if mcap is not None and mcap < 15000:
        score += 4
    if mcap is not None and mcap < 5000:
        score += 3

    if score >= 68 and q >= 55:
        action = "🔵 HOLD / ACCUMULATE"
        reason = "Fits multi-year quality-growth profile – patience required"
    elif score >= 55:
        action = "⚪ WATCHLIST"
        reason = "On radar – wait for better entry or clearer fundamentals"
    else:
        action = "🔴 AVOID / LIGHT"
        reason = "Quality or growth not convincing for long-term sleeve"

    # Entry timing hint (does not change thesis)
    if t >= 65 and action.startswith("🔵"):
        reason += " | Momentum supportive for staggered entry"
    elif t < 40 and action.startswith("🔵"):
        reason += " | Weak near-term tape – prefer staggered buys only"

    return KelaIdea(
        symbol=symbol,
        name=name,
        action=action,
        reason=reason,
        score=round(score, 1),
        market_cap_cr=mcap,
        bucket=market_cap_bucket(mcap),
        note=note,
        extras={"quality": q, "growth": g, "valuation": v, "technical": t},
    )


def run_kela_strategy() -> Dict[str, Any]:
    """Fetch + score Kela universe. Returns structured result for Telegram."""
    ideas: List[KelaIdea] = []
    for item in KELA_UNIVERSE:
        yahoo = item["symbol"] + ".NS"
        fund = fetch_basic_fundamentals(yahoo)
        fund["name"] = item["name"]
        fund["_kela_note"] = item.get("note", "")
        fund["_prices"] = fetch_price_history(yahoo, period="1y")
        idea = _score_kela_style(fund)
        if idea:
            ideas.append(idea)

    ideas.sort(key=lambda x: x.score, reverse=True)

    return {
        "scan_time": datetime.now(),
        "ideas": ideas,
        "philosophy": [
            "Bottom-up stock picking (company first, not index)",
            "Multi-year horizon (typically 3–5+ years)",
            "Volatility treated as opportunity for quality names",
            "High conviction / concentrated style – not a diversified index",
            "Research first; execute when price/timing allows",
        ],
    }


def format_kela_telegram(result: Dict[str, Any]) -> str:
    """Separate Telegram message for this sleeve only."""
    now = result["scan_time"].strftime("%d %b %Y | %H:%M IST")
    lines = [
        "<b>📌 Madhusudan Kela’s Strategy</b>",
        f"{now}",
        "",
        "<i>Inspired by his publicly described philosophy + selected disclosed holdings.</i>",
        "<i>Not official advice from Madhusudan Kela. Not investment advice.</i>",
        "",
        "<b>Strategy principles</b>",
    ]
    for p in result["philosophy"]:
        lines.append(f"• {p}")
    lines.append("")
    lines.append("<b>Tracked investments (scored for multi-year sleeve)</b>")

    ideas: List[KelaIdea] = result.get("ideas") or []
    if not ideas:
        lines.append("• No names scored today (data unavailable)")
    else:
        for idea in ideas:
            mcap = f"{idea.market_cap_cr:,.0f} Cr" if idea.market_cap_cr else "—"
            note = f" ({idea.note})" if idea.note else ""
            lines.append(
                f"• <b>{idea.symbol}</b>{note}\n"
                f"  {idea.action} | Score {idea.score} | {idea.bucket} | {mcap}\n"
                f"  {idea.reason}"
            )

    lines.append("")
    lines.append("<i>Horizon: years, not days. Position sizing & due diligence are your responsibility.</i>")
    lines.append("<i>StockScorecard – Kela sleeve (separate from Swing report)</i>")
    return "\n".join(lines)
