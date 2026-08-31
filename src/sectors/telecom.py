"""Telecom sector scanner."""

from typing import List, Dict, Any, Optional
from src.sectors.base import BaseSectorScanner
from src.shared.models import StockIdea
from src.sectors._helpers import (
    enrich_universe, build_swing_idea, build_long_term_idea, build_dark_horse_idea,
)

UNIVERSE = [
    {"symbol": "BHARTIARTL", "name": "Bharti Airtel Ltd"},
    {"symbol": "RCOM", "name": "Reliance Communications"},
    {"symbol": "IDEA", "name": "Vodafone Idea Ltd"},
    {"symbol": "TATACOMM", "name": "Tata Communications Ltd"},
    {"symbol": "INDUSTOWER", "name": "Indus Towers Ltd"},
    {"symbol": "BHARTIHEXA", "name": "Bharti Hexacom Ltd"},
    {"symbol": "ROUTE", "name": "Route Mobile Ltd"},
    {"symbol": "TTML", "name": "Tata Teleservices"},
    {"symbol": "MTNL", "name": "Mahanagar Telephone Nigam"},
    {"symbol": "HFCL", "name": "HFCL Ltd"},
]


class TelecomScanner(BaseSectorScanner):
    sector_key = "telecom"
    sector_name = "Telecom"

    def get_universe(self) -> List[Dict[str, Any]]:
        return enrich_universe(UNIVERSE, self.sector_name)

    def score_swing(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_swing_idea(stock, self.sector_name, min_volume=100000)

    def score_long_term(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_long_term_idea(stock, self.sector_name, max_de=250, invest_threshold=58)

    def score_dark_horse(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_dark_horse_idea(stock, self.sector_name, max_mcap=20000)
