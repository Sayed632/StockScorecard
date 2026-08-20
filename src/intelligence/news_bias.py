"""
News → Swing score bias with automatic activation date.

Until activate_on (config), news is display-only.
From activate_on onwards, high-impact headlines can boost/penalise Swing scores.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Dict, Any, Optional, Tuple
import logging
import re

from src.intelligence.news_layer import NewsItem, fetch_market_news
from src.shared.models import StockIdea

logger = logging.getLogger(__name__)


def _parse_activate_on(raw: str) -> Optional[date]:
    try:
        return datetime.strptime(str(raw).strip()[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def news_scoring_status(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns:
      active: bool – whether bias is live today
      activate_on: date or None
      days_remaining: int or None
      message: human string
    """
    ni = cfg.get("news_intelligence") or {}
    if not ni.get("score_bias_enabled", True):
        return {
            "active": False,
            "activate_on": None,
            "days_remaining": None,
            "message": "News score bias disabled in config",
        }

    act = _parse_activate_on(ni.get("activate_on") or "")
    today = date.today()
    if act is None:
        return {
            "active": True,
            "activate_on": None,
            "days_remaining": 0,
            "message": "News score bias ON (no activate_on set)",
        }

    if today >= act:
        return {
            "active": True,
            "activate_on": act,
            "days_remaining": 0,
            "message": f"News score bias ACTIVE (since {act.isoformat()})",
        }

    remaining = (act - today).days
    return {
        "active": False,
        "activate_on": act,
        "days_remaining": remaining,
        "message": f"News score bias scheduled – activates {act.isoformat()} ({remaining} day(s) left)",
    }


def _headline_matches_idea(title: str, idea: StockIdea) -> bool:
    t = title.lower()
    sym = (idea.symbol or "").lower()
    name = (idea.name or "").lower()
    sector = (idea.sector or "").lower()

    if sym and len(sym) >= 3 and re.search(rf"\b{re.escape(sym)}\b", t, re.I):
        return True
    # first word of company name
    if name:
        first = name.split()[0]
        if len(first) >= 4 and first.lower() in t:
            return True
    # sector keyword loose match
    sector_keys = {
        "pharma": r"pharma|fda|drug",
        "bank": r"bank|nbfc|npa",
        "it": r"\bit\b|software|infosys|tcs",
        "auto": r"auto|ev\b|vehicle",
        "defence": r"defence|defense|drone|hal\b",
        "metal": r"metal|steel|copper",
        "energy": r"oil|gas|crude|power",
        "realty": r"realty|housing|property",
        "fmcg": r"fmcg|consumer",
        "telecom": r"telecom|airtel",
        "chemical": r"chemical",
        "textile": r"textile",
    }
    for key, pat in sector_keys.items():
        if key in sector and re.search(pat, t, re.I):
            return True
    return False


def compute_news_bias_for_ideas(
    swing_ideas: List[StockIdea],
    cfg: Dict[str, Any],
    news_items: Optional[List[NewsItem]] = None,
) -> Tuple[List[StockIdea], str]:
    """
    If activation date reached, apply news bias to matching Swing ideas.
    Returns (possibly adjusted ideas, status note).
    """
    status = news_scoring_status(cfg)
    note = status["message"]

    if not status["active"]:
        return swing_ideas, note

    ni = cfg.get("news_intelligence") or {}
    bull = float(ni.get("bullish_points", 4))
    bear = float(ni.get("bearish_points", -5))
    min_impact = int(ni.get("min_impact_score", 5))

    if news_items is None:
        try:
            news_items = fetch_market_news(max_items=15)
        except Exception as e:
            logger.warning("News fetch for bias failed: %s", e)
            return swing_ideas, note + " | fetch failed"

    strong = [n for n in (news_items or []) if n.impact_score >= min_impact]
    if not strong:
        return swing_ideas, note + " | no strong headlines"

    out: List[StockIdea] = []
    applied = 0
    for idea in swing_ideas:
        delta = 0.0
        reasons = []
        for n in strong:
            matched = [m.upper() for m in (getattr(n, "matched_symbols", None) or [])]
            if idea.symbol.upper() in matched:
                pass  # direct ticker hit from news layer
            elif not _headline_matches_idea(n.title, idea):
                continue
            if n.bias == "Bullish":
                delta += bull
                reasons.append(f"news+ {n.title[:40]}")
            elif n.bias == "Bearish":
                delta += bear
                reasons.append(f"news- {n.title[:40]}")
        if delta == 0:
            out.append(idea)
            continue

        applied += 1
        new_score = idea.score + delta
        reason = idea.reason
        if reasons:
            reason = f"{reason} [{reasons[0]}…]" if len(reasons) > 1 else f"{reason} [{reasons[0]}]"
        cats = list(idea.catalysts or []) + [f"news_bias:{delta:+.0f}"]
        extras = dict(idea.extras or {})
        extras["news_bias"] = delta
        out.append(
            StockIdea(
                symbol=idea.symbol,
                name=idea.name,
                sector=idea.sector,
                engine=idea.engine,
                action=idea.action,
                reason=reason,
                market_cap_cr=idea.market_cap_cr,
                market_cap_bucket=idea.market_cap_bucket,
                score=new_score,
                catalysts=cats,
                extras=extras,
            )
        )

    note = f"{note} | applied to {applied} swing idea(s)"
    logger.info(note)
    return out, note
