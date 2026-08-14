"""Automobile + EV sector scanner."""

from typing import List, Dict, Any, Optional
from src.sectors.base import BaseSectorScanner
from src.shared.models import StockIdea
from src.sectors._helpers import (
    enrich_universe, build_swing_idea, build_long_term_idea, build_dark_horse_idea,
)

UNIVERSE = [
    {"symbol": "MARUTI", "name": "Maruti Suzuki India Ltd"},
    {"symbol": "TATAMOTORS", "name": "Tata Motors Ltd"},
    {"symbol": "M&M", "name": "Mahindra & Mahindra Ltd"},
    {"symbol": "BAJAJ-AUTO", "name": "Bajaj Auto Ltd"},
    {"symbol": "HEROMOTOCO", "name": "Hero MotoCorp Ltd"},
    {"symbol": "EICHERMOT", "name": "Eicher Motors Ltd"},
    {"symbol": "TVSMOTOR", "name": "TVS Motor Company Ltd"},
    {"symbol": "ASHOKLEY", "name": "Ashok Leyland Ltd"},
    {"symbol": "BHARATFORG", "name": "Bharat Forge Ltd"},
    {"symbol": "MOTHERSON", "name": "Samvardhana Motherson"},
    {"symbol": "BOSCHLTD", "name": "Bosch Ltd"},
    {"symbol": "TIINDIA", "name": "Tube Investments of India"},
]


class AutomobileEVScanner(BaseSectorScanner):
    sector_key = "automobile_ev"
    sector_name = "Automobile & EV"

    def get_universe(self) -> List[Dict[str, Any]]:
        return enrich_universe(UNIVERSE, self.sector_name)

    def score_swing(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_swing_idea(stock, self.sector_name, min_volume=60000)

    def score_long_term(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_long_term_idea(stock, self.sector_name, max_de=150, invest_threshold=63)

    def score_dark_horse(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_dark_horse_idea(stock, self.sector_name, max_mcap=20000)
