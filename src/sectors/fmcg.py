"""FMCG / Consumer sector scanner."""

from typing import List, Dict, Any, Optional
from src.sectors.base import BaseSectorScanner
from src.shared.models import StockIdea
from src.sectors._helpers import (
    enrich_universe, build_swing_idea, build_long_term_idea, build_dark_horse_idea,
)

UNIVERSE = [
    {"symbol": "HINDUNILVR", "name": "Hindustan Unilever Ltd"},
    {"symbol": "ITC", "name": "ITC Ltd"},
    {"symbol": "NESTLEIND", "name": "Nestle India Ltd"},
    {"symbol": "BRITANNIA", "name": "Britannia Industries Ltd"},
    {"symbol": "DABUR", "name": "Dabur India Ltd"},
    {"symbol": "MARICO", "name": "Marico Ltd"},
    {"symbol": "GODREJCP", "name": "Godrej Consumer Products"},
    {"symbol": "COLPAL", "name": "Colgate-Palmolive (India)"},
    {"symbol": "TATACONSUM", "name": "Tata Consumer Products"},
    {"symbol": "EMAMILTD", "name": "Emami Ltd"},
    {"symbol": "VBL", "name": "Varun Beverages Ltd"},
    {"symbol": "UNITDSPR", "name": "United Spirits Ltd"},
]


class FMCGScanner(BaseSectorScanner):
    sector_key = "fmcg"
    sector_name = "FMCG & Consumer"

    def get_universe(self) -> List[Dict[str, Any]]:
        return enrich_universe(UNIVERSE, self.sector_name)

    def score_swing(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_swing_idea(stock, self.sector_name, min_volume=50000)

    def score_long_term(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_long_term_idea(stock, self.sector_name, max_de=100, invest_threshold=66)

    def score_dark_horse(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_dark_horse_idea(stock, self.sector_name, max_mcap=20000)
