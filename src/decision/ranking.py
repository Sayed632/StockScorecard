"""
Decision & Ranking Layer
Merges sector results, applies FII/DII + sector FPI bias to Swing, prepares final lists.
"""

from typing import List, Dict, Optional
from src.shared.models import StockIdea, ScanResult, Action
from src.shared.fii_dii import (
    FIIDIISnapshot,
    SectorFPI,
    sector_swing_adjustment,
)
from datetime import datetime
from src.decision.probability import attach_probabilities


def _apply_swing_bias(
    ideas: List[StockIdea],
    market_bias_pts: float,
    market_bias_reason: str,
    sector_key: str,
    sector_fpi_list: List[SectorFPI],
) -> List[StockIdea]:
    """Adjust swing idea scores and reasons using market + sector institutional bias."""
    sec_pts, sec_reason = sector_swing_adjustment(sector_key, sector_fpi_list)
    total_bias = market_bias_pts + sec_pts

    adjusted = []
    for idea in ideas:
        if idea.engine.value != "swing":
            adjusted.append(idea)
            continue

        new_score = idea.score + total_bias
        reason = idea.reason
        bias_notes = []
        if market_bias_pts != 0:
            bias_notes.append(f"mkt {market_bias_pts:+.0f}")
        if sec_pts != 0 and sec_reason:
            bias_notes.append(sec_reason)
        if bias_notes:
            reason = f"{reason} [{', '.join(bias_notes)}]"

        action = idea.action
        if new_score >= 72 and idea.action in (Action.WAIT, Action.WATCHLIST, Action.BUY_NOW):
            action = Action.BUY_NOW
        if new_score < 50 and idea.action == Action.BUY_NOW:
            action = Action.WAIT
        if new_score < 40:
            action = Action.EXIT_AVOID

        adjusted.append(StockIdea(
            symbol=idea.symbol,
            name=idea.name,
            sector=idea.sector,
            engine=idea.engine,
            action=action,
            reason=reason,
            market_cap_cr=idea.market_cap_cr,
            market_cap_bucket=idea.market_cap_bucket,
            score=round(new_score, 1),
            catalysts=list(idea.catalysts) + ([f"bias:{total_bias:+.0f}"] if total_bias else []),
            extras=dict(idea.extras or {}),
        ))
    return adjusted


def merge_and_rank(
    sector_results: Dict[str, Dict[str, List[StockIdea]]],
    max_per_list: int = 8,
    frequency: int = 1,
    frequency_reason: str = "Normal",
    fii_dii: Optional[FIIDIISnapshot] = None,
    sector_fpi: Optional[List[SectorFPI]] = None,
) -> ScanResult:
    sector_fpi = sector_fpi or []
    market_bias_pts, market_bias_reason = (0.0, "neutral")
    if fii_dii:
        market_bias_pts, market_bias_reason = fii_dii.swing_bias_points()

    all_swing: List[StockIdea] = []
    all_long: List[StockIdea] = []
    all_dark: List[StockIdea] = []
    sector_summary = {}

    for sector_key, engines in sector_results.items():
        swing = engines.get("swing", [])
        long_t = engines.get("long_term", [])
        dark = engines.get("dark_horse", [])

        swing = _apply_swing_bias(
            swing,
            market_bias_pts=market_bias_pts,
            market_bias_reason=market_bias_reason,
            sector_key=sector_key,
            sector_fpi_list=sector_fpi,
        )

        all_swing.extend([i for i in swing if i.action in (Action.BUY_NOW, Action.WAIT)])
        all_long.extend([i for i in long_t if i.action == Action.HOLD_INVEST])
        all_dark.extend(dark)

        actionable = (
            len([i for i in swing if i.action == Action.BUY_NOW])
            + len([i for i in long_t if i.action == Action.HOLD_INVEST])
            + len(dark)
        )
        if actionable > 0:
            sector_summary[sector_key] = f"{actionable} actionable ideas"

    all_swing = attach_probabilities(all_swing)
    all_long = attach_probabilities(all_long)
    all_dark = attach_probabilities(all_dark)
    # Keep primary sort by probability, secondary by score already mixed in estimator

    notes = [f"Frequency: {frequency}x – {frequency_reason}"]
    if fii_dii:
        notes.append(f"Swing market bias: {market_bias_pts:+.0f} ({market_bias_reason})")

    return ScanResult(
        scan_time=datetime.now(),
        frequency=frequency,
        swing_ideas=all_swing[:max_per_list],
        long_term_ideas=all_long[:max_per_list],
        dark_horse_ideas=all_dark[:max_per_list],
        sector_summary=sector_summary,
        notes=notes,
    )
