"""
Simple probability ranker (Phase B – heuristic).

Uses existing features (score, engine type, action, market-cap bucket, catalysts)
to estimate P(positive outcome). Not a trained ML model yet – designed so that
once results_log has enough outcomes, weights can be calibrated from data.
"""

from typing import List
from src.shared.models import StockIdea, EngineType, Action


def estimate_probability(idea: StockIdea) -> float:
    """
    Return probability in [0.05, 0.95] that the idea works over its horizon.
    Heuristic baseline – transparent and tunable.
    """
    # Base by engine
    if idea.engine == EngineType.SWING:
        p = 0.48
        horizon_note = "5-20d"
    elif idea.engine == EngineType.LONG_TERM:
        p = 0.52
        horizon_note = "6-36m"
    else:  # Dark Horse
        p = 0.42
        horizon_note = "speculative"

    # Score contribution (score roughly 0-100)
    # Map 50→0, 80→+0.15
    score_adj = max(-0.12, min(0.18, (idea.score - 55) / 100 * 0.5))
    p += score_adj

    # Action strength
    if idea.action in (Action.BUY_NOW, Action.DARK_HORSE_BUY):
        p += 0.06
    elif idea.action in (Action.HOLD_INVEST, Action.DARK_HORSE_INVEST):
        p += 0.04
    elif idea.action in (Action.WAIT, Action.DARK_HORSE_WATCH, Action.WATCHLIST):
        p -= 0.03
    elif idea.action == Action.EXIT_AVOID:
        p -= 0.15

    # Market-cap bucket (liquidity / stability proxy)
    bucket = (idea.market_cap_bucket or "").lower()
    if bucket == "large":
        p += 0.03
    elif bucket == "mid":
        p += 0.01
    elif bucket == "small":
        p -= 0.02
    elif bucket == "micro":
        p -= 0.05

    # Catalyst / bias hints in catalysts list
    cats = " ".join(idea.catalysts or []).lower()
    if "strong technical" in cats or "momentum" in cats:
        p += 0.03
    if "bias:+" in cats or "fpi inflow" in (idea.reason or "").lower():
        p += 0.02
    if "bias:-" in cats or "fpi outflow" in (idea.reason or "").lower():
        p -= 0.03
    if "high risk" in (idea.reason or "").lower() or "penny" in cats:
        p -= 0.06

    # Clamp
    p = max(0.05, min(0.95, p))
    return round(p, 2)


def attach_probabilities(ideas: List[StockIdea]) -> List[StockIdea]:
    """Mutate/copy ideas with probability in extras and sorted by probability."""
    out = []
    for idea in ideas:
        prob = estimate_probability(idea)
        extras = dict(idea.extras or {})
        extras["probability"] = prob
        out.append(StockIdea(
            symbol=idea.symbol,
            name=idea.name,
            sector=idea.sector,
            engine=idea.engine,
            action=idea.action,
            reason=idea.reason,
            market_cap_cr=idea.market_cap_cr,
            market_cap_bucket=idea.market_cap_bucket,
            score=idea.score,
            catalysts=list(idea.catalysts or []),
            extras=extras,
        ))
    out.sort(key=lambda x: x.extras.get("probability", 0), reverse=True)
    return out
