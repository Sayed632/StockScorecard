"""
Decision & Ranking Layer
Merges sector results, applies global limits, prepares final lists.
"""

from typing import List, Dict
from src.shared.models import StockIdea, ScanResult, EngineType, Action
from datetime import datetime


def merge_and_rank(
    sector_results: Dict[str, Dict[str, List[StockIdea]]],
    max_per_list: int = 8,
    frequency: int = 1,
    frequency_reason: str = "Normal",
) -> ScanResult:
    """
    sector_results = {
        "pharmaceuticals": {"swing": [...], "long_term": [...], "dark_horse": [...]},
        ...
    }
    """
    all_swing: List[StockIdea] = []
    all_long: List[StockIdea] = []
    all_dark: List[StockIdea] = []
    sector_summary = {}

    for sector_key, engines in sector_results.items():
        swing = engines.get("swing", [])
        long_t = engines.get("long_term", [])
        dark = engines.get("dark_horse", [])

        # Only keep actionable ideas for the main lists
        all_swing.extend([i for i in swing if i.action in (Action.BUY_NOW, Action.WAIT)])
        all_long.extend([i for i in long_t if i.action == Action.HOLD_INVEST])
        all_dark.extend(dark)

        actionable = len([i for i in swing if i.action == Action.BUY_NOW]) + \
                     len([i for i in long_t if i.action == Action.HOLD_INVEST]) + \
                     len(dark)
        if actionable > 0:
            sector_summary[sector_key] = f"{actionable} actionable ideas"

    # Global ranking
    all_swing.sort(key=lambda x: x.score, reverse=True)
    all_long.sort(key=lambda x: x.score, reverse=True)
    all_dark.sort(key=lambda x: x.score, reverse=True)

    return ScanResult(
        scan_time=datetime.now(),
        frequency=frequency,
        swing_ideas=all_swing[:max_per_list],
        long_term_ideas=all_long[:max_per_list],
        dark_horse_ideas=all_dark[:max_per_list],
        sector_summary=sector_summary,
        notes=[f"Frequency: {frequency}x – {frequency_reason}"],
    )