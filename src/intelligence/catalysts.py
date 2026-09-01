"""
Catalyst lookup for symbols – NSE filings + market news headlines.
Used by Hot Stocks, Horizon, Fresh Buys to show price context + why it may be rising.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import logging
import re

logger = logging.getLogger(__name__)

SECTOR_THEMES = {
    "defence_aerospace": "Defence / order-book momentum",
    "pharmaceuticals": "Pharma / healthcare sector flow",
    "information_technology": "IT / software demand",
    "telecom": "Telecom / network capex theme",
    "metals_mining": "Metals / commodity strength",
    "banks_financials": "Financials / credit growth",
    "capital_goods_infra": "Capex / infra spending",
    "textiles": "Textiles / manufacturing",
    "media": "Media / content",
    "energy_oil_gas_power": "Power / energy complex",
    "automobile_ev": "Auto / EV theme",
    "chemicals": "Chemicals / specialty chem",
    "fmcg": "FMCG / consumer",
    "realty": "Realty / housing",
    "others_residual": "Stock-specific momentum",
}


def _match_text(sym: str, name: str, text: str) -> bool:
    t = (text or "").lower()
    s = (sym or "").lower()
    if s and len(s) >= 3 and re.search(rf"\b{re.escape(s)}\b", t):
        return True
    if name:
        for part in re.split(r"[\s,]+", name):
            part = part.strip().lower()
            if len(part) >= 4 and part not in ("india", "limited", "ltd", "labs", "corp", "services"):
                if re.search(rf"\b{re.escape(part)}\b", t):
                    return True
    return False


def build_catalyst_map() -> Dict[str, str]:
    """symbol -> short catalyst string (NSE preferred, then news)."""
    catalysts: Dict[str, str] = {}

    try:
        from src.intelligence.nse_announcements import fetch_nse_announcements

        for a in fetch_nse_announcements(limit=40):
            sym = (a.symbol or "").upper()
            if not sym:
                continue
            subj = (a.subject or "").strip()
            detail = (a.detail or "").strip()
            snippet = subj or detail[:100]
            if detail and subj and subj.lower() not in detail.lower()[:50]:
                snippet = f"{subj} – {detail[:70]}"
            if not snippet:
                continue
            if sym not in catalysts or getattr(a, "impact", "") == "high":
                catalysts[sym] = f"NSE: {snippet[:115]}"
    except Exception as e:
        logger.warning("catalyst NSE: %s", e)

    try:
        from src.intelligence.news_layer import fetch_market_news

        for n in fetch_market_news(max_items=20):
            title = (n.title or "").strip()
            if not title:
                continue
            for ms in getattr(n, "matched_symbols", None) or []:
                ms = str(ms).upper()
                if ms and ms not in catalysts:
                    catalysts[ms] = f"News: {title[:110]}"
    except Exception as e:
        logger.warning("catalyst news: %s", e)

    return catalysts


def catalyst_for(
    symbol: str,
    name: str = "",
    sector: str = "",
    cmap: Optional[Dict[str, str]] = None,
) -> str:
    """Resolve catalyst for one symbol with sector fallback."""
    sym = (symbol or "").upper()
    if cmap is None:
        cmap = build_catalyst_map()
    if sym in cmap:
        return cmap[sym]
    # Try name match against stored news keys only via sector theme
    theme = SECTOR_THEMES.get(sector or "", "")
    if theme:
        return f"Theme: {theme}"
    return "Catalyst: momentum / no specific filing matched"


def format_price(px: Optional[float]) -> str:
    if px is None:
        return "—"
    try:
        import math
        p = float(px)
        if math.isnan(p) or math.isinf(p) or p <= 0:
            return "—"
        if p >= 1000:
            return f"₹{p:,.1f}"
        return f"₹{p:.2f}"
    except Exception:
        return "—"
