"""Metals & Mining sector scanner."""

from typing import List, Dict, Any, Optional
from src.sectors.base import BaseSectorScanner
from src.shared.models import StockIdea
from src.sectors._helpers import (
    enrich_universe, build_swing_idea, build_long_term_idea, build_dark_horse_idea,
)

UNIVERSE = [
    {"symbol": "TATASTEEL", "name": "Tata Steel Ltd"},
    {"symbol": "JSWSTEEL", "name": "JSW Steel Ltd"},
    {"symbol": "HINDALCO", "name": "Hindalco Industries Ltd"},
    {"symbol": "VEDL", "name": "Vedanta Ltd"},
    {"symbol": "COALINDIA", "name": "Coal India Ltd"},
    {"symbol": "NMDC", "name": "NMDC Ltd"},
    {"symbol": "SAIL", "name": "Steel Authority of India"},
    {"symbol": "NATIONALUM", "name": "National Aluminium Co"},
    {"symbol": "HINDCOPPER", "name": "Hindustan Copper Ltd"},
    {"symbol": "JINDALSTEL", "name": "Jindal Steel & Power"},
    {"symbol": "APLAPOLLO", "name": "APL Apollo Tubes Ltd"},
    {"symbol": "WELCORP", "name": "Welspun Corp Ltd"},
]


class MetalsMiningScanner(BaseSectorScanner):
    sector_key = "metals_mining"
    sector_name = "Metals & Mining"

    def get_universe(self) -> List[Dict[str, Any]]:
        return enrich_universe(UNIVERSE, self.sector_name)

    def score_swing(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_swing_idea(stock, self.sector_name, min_volume=80000)

    def score_long_term(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_long_term_idea(stock, self.sector_name, max_de=180, invest_threshold=60)

    def score_dark_horse(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_dark_horse_idea(stock, self.sector_name, max_mcap=20000)
