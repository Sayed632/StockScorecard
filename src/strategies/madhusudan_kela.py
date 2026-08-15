"""
Madhusudan Kela portfolio tracker + multi-year strategy sleeve.

Tracks selected *publicly disclosed* holdings (typically stake >1%).
NOT official advice from Madhusudan Kela. Holdings change every quarter.
Source basis: public shareholding / media compilations (Jun 2026 style data).
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


# Disclosed portfolio tracker (update when new bulk shareholding data is out)
# stake_pct = last reported approximate holding %
KELA_PORTFOLIO = [
    {"symbol": "CHOICEIN", "name": "Choice International Ltd", "stake_pct": 7.2, "note": "Largest disclosed holding"},
    {"symbol": "MKVENTURES", "name": "MKVentures Capital Ltd", "stake_pct": 74.4, "note": "Promoter / related entity"},
    {"symbol": "WINDMACH", "name": "Windsor Machines Ltd", "stake_pct": 6.4, "note": "Trimmed in Jun quarter"},
    {"symbol": "SANGAMIND", "name": "Sangam (India) Ltd", "stake_pct": 4.9, "note": "Textiles"},
    {"symbol": "RPTECH", "name": "Rashi Peripherals Ltd", "stake_pct": 1.8, "note": "Strong CY26 performer"},
    {"symbol": "SGFIN", "name": "SG Finserve Ltd", "stake_pct": 1.4, "note": "NBFC"},
    {"symbol": "IBULHSGFIN", "name": "Indiabulls / related housing finance", "stake_pct": 2.2, "note": "Newer large entry"},
    {"symbol": "INDOSTAR", "name": "Indostar Capital Finance Ltd", "stake_pct": 2.1, "note": "NBFC"},
    {"symbol": "KOPRAN", "name": "Kopran Ltd", "stake_pct": 1.7, "note": "Pharma"},
    {"symbol": "SUBAM", "name": "Subam Papers Ltd", "stake_pct": 7.0, "note": "Newer entry"},
    {"symbol": "SIMPLEXINF", "name": "Simplex Infrastructures Ltd", "stake_pct": 1.2, "note": "Infra"},
    {"symbol": "BOMDYEING", "name": "Bombay Dyeing & Mfg Co", "stake_pct": 1.5, "note": "Legacy textile/realty"},
    {"symbol": "REPRO", "name": "Repro India Ltd", "stake_pct": 3.3, "note": "Print services"},
    {"symbol": "IRIS", "name": "IRIS RegTech / Business Services", "stake_pct": 5.2, "note": "RegTech"},
    {"symbol": "UNIECOM", "name": "Unicommerce eSolutions Ltd", "stake_pct": 1.5, "note": "E-comm SaaS"},
    {"symbol": "APTECHT", "name": "Aptech Ltd", "stake_pct": 1.1, "note": "Education / training"},
    {"symbol": "NIYOGIN", "name": "Niyogin Fintech Ltd", "stake_pct": 4.5, "note": "Fintech"},
    {"symbol": "EMKAY", "name": "Emkay Global Financial Services", "stake_pct": 1.1, "note": "Broking"},
]


@dataclass
class KelaHolding:
    symbol: str
    name: str
    action: str
    reason: str
    score: float
    stake_pct: Optional[float] = None
    last_price: Optional[float] = None
    market_cap_cr: Optional[float] = None
    bucket: str = ""
    note: str = ""
    extras: Dict[str, Any] = field(default_factory=dict)


def _score_holding(stock: Dict[str, Any], stake_pct: Optional[float], note: str) -> Optional[KelaHolding]:
    symbol = stock.get("symbol", "")
    name = stock.get("name", symbol)
    mcap = stock.get("market_cap_cr")
    prices = stock.get("_prices")

    q = score_quality(stock)
    g = score_growth(stock)
    v = score_valuation(stock)
    t = score_technical(prices)

    score = 0.40 * q + 0.35 * g + 0.15 * v + 0.10 * t
    if mcap is not None and mcap < 15000:
        score += 4
    if mcap is not None and mcap < 5000:
        score += 3

    if score >= 68 and q >= 55:
        action = "🔵 HOLD / ACCUMULATE"
        reason = "Multi-year quality-growth profile"
    elif score >= 55:
        action = "⚪ WATCHLIST"
        reason = "On radar – wait for clarity or better entry"
    else:
        action = "🔴 LIGHT / AVOID"
        reason = "Fundamentals not convincing for long sleeve"

    if t >= 65 and action.startswith("🔵"):
        reason += " | Tape supportive for staggered entry"
    elif t < 40 and action.startswith("🔵"):
        reason += " | Weak near-term tape – stagger only"

    last_price = None
    try:
        if prices is not None and len(prices) > 0:
            last_price = float(prices["close"].iloc[-1])
    except Exception:
        pass

    return KelaHolding(
        symbol=symbol,
        name=name,
        action=action,
        reason=reason,
        score=round(min(score, 99), 1),
        stake_pct=stake_pct,
        last_price=last_price,
        market_cap_cr=mcap,
        bucket=market_cap_bucket(mcap),
        note=note,
        extras={"quality": q, "growth": g, "valuation": v, "technical": t},
    )


def run_kela_strategy() -> Dict[str, Any]:
    """Track Kela disclosed portfolio and score each holding."""
    holdings: List[KelaHolding] = []
    for item in KELA_PORTFOLIO:
        yahoo = item["symbol"] + ".NS"
        fund = fetch_basic_fundamentals(yahoo)
        fund["name"] = item["name"]
        fund["_prices"] = fetch_price_history(yahoo, period="1y")
        h = _score_holding(fund, item.get("stake_pct"), item.get("note", ""))
        if h:
            holdings.append(h)

    holdings.sort(key=lambda x: (x.stake_pct or 0, x.score), reverse=True)

    return {
        "scan_time": datetime.now(),
        "as_of_label": "Disclosed holdings basis ~Jun 2026 public data (update quarterly)",
        "ideas": holdings,
        "philosophy": [
            "Bottom-up stock picking (company first)",
            "Multi-year horizon (typically 3–5+ years)",
            "Volatility as opportunity for quality names",
            "High conviction – concentrated book",
            "Research first; execute when price allows",
        ],
    }


def format_kela_telegram(result: Dict[str, Any]) -> str:
    now = result["scan_time"].strftime("%d %b %Y | %H:%M IST")
    lines = [
        "<b>📌 Madhusudan Kela’s Strategy – Portfolio Tracker</b>",
        f"{now}",
        f"<i>{result.get('as_of_label', '')}</i>",
        "",
        "<i>Not official advice from Madhusudan Kela. Not investment advice.</i>",
        "<i>Stakes are last reported public figures and can change.</i>",
        "",
        "<b>Strategy principles</b>",
    ]
    for p in result["philosophy"]:
        lines.append(f"• {p}")
    lines.append("")
    lines.append("<b>Tracked portfolio</b>")

    ideas: List[KelaHolding] = result.get("ideas") or []
    if not ideas:
        lines.append("• No holdings scored (data unavailable)")
    else:
        for h in ideas:
            stake = f"{h.stake_pct:.1f}%" if h.stake_pct is not None else "—"
            px = f"₹{h.last_price:.1f}" if h.last_price is not None else "—"
            note = f" | {h.note}" if h.note else ""
            lines.append(
                f"• <b>{h.symbol}</b> (stake ~{stake}){note}\n"
                f"  {h.action} | Score {h.score} | {px} | {h.bucket}\n"
                f"  {h.reason}"
            )

    lines.append("")
    lines.append(f"<i>Holdings tracked: {len(ideas)} | Horizon: years, not days</i>")
    lines.append("<i>StockScorecard – Kela portfolio sleeve</i>")
    return "\n".join(lines)
