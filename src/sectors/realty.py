"""Realty sector scanner."""

from typing import List, Dict, Any, Optional
from src.sectors.base import BaseSectorScanner
from src.shared.models import StockIdea
from src.sectors._helpers import (
    enrich_universe, build_swing_idea, build_long_term_idea, build_dark_horse_idea,
)

UNIVERSE = [
    {"symbol": "DLF", "name": "DLF Ltd"},
    {"symbol": "GODREJPROP", "name": "Godrej Properties Ltd"},
    {"symbol": "OBEROIRLTY", "name": "Oberoi Realty Ltd"},
    {"symbol": "PRESTIGE", "name": "Prestige Estates Projects"},
    {"symbol": "PHOENIXLTD", "name": "Phoenix Mills Ltd"},
    {"symbol": "BRIGADE", "name": "Brigade Enterprises Ltd"},
    {"symbol": "SOBHA", "name": "Sobha Ltd"},
    {"symbol": "MAHLIFE", "name": "Mahindra Lifespace"},
    {"symbol": "SUNTECK", "name": "Sunteck Realty Ltd"},
    {"symbol": "LODHA", "name": "Macrotech Developers Ltd"},
]


class RealtyScanner(BaseSectorScanner):
    sector_key = "realty"
    sector_name = "Realty"

    def get_universe(self) -> List[Dict[str, Any]]:
        return enrich_universe(UNIVERSE, self.sector_name)

    def score_swing(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_swing_idea(stock, self.sector_name, min_volume=50000)

    def score_long_term(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_long_term_idea(stock, self.sector_name, max_de=200, invest_threshold=60)

    def score_dark_horse(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_dark_horse_idea(stock, self.sector_name, max_mcap=18000)
