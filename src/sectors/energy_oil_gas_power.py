"""Energy / Oil & Gas / Power sector scanner."""

from typing import List, Dict, Any, Optional
from src.sectors.base import BaseSectorScanner
from src.shared.models import StockIdea
from src.sectors._helpers import (
    enrich_universe, build_swing_idea, build_long_term_idea, build_dark_horse_idea,
)

UNIVERSE = [
    {"symbol": "RELIANCE", "name": "Reliance Industries Ltd"},
    {"symbol": "ONGC", "name": "Oil & Natural Gas Corp"},
    {"symbol": "IOC", "name": "Indian Oil Corporation"},
    {"symbol": "BPCL", "name": "Bharat Petroleum Corp"},
    {"symbol": "HINDPETRO", "name": "Hindustan Petroleum"},
    {"symbol": "GAIL", "name": "GAIL (India) Ltd"},
    {"symbol": "NTPC", "name": "NTPC Ltd"},
    {"symbol": "POWERGRID", "name": "Power Grid Corporation"},
    {"symbol": "ADANIPOWER", "name": "Adani Power Ltd"},
    {"symbol": "TATAPOWER", "name": "Tata Power Company"},
    {"symbol": "ADANIGREEN", "name": "Adani Green Energy"},
    {"symbol": "NHPC", "name": "NHPC Ltd"},
    {"symbol": "SJVN", "name": "SJVN Ltd"},
    {"symbol": "IGL", "name": "Indraprastha Gas Ltd"},
]


class EnergyOilGasPowerScanner(BaseSectorScanner):
    sector_key = "energy_oil_gas_power"
    sector_name = "Energy / Oil & Gas / Power"

    def get_universe(self) -> List[Dict[str, Any]]:
        return enrich_universe(UNIVERSE, self.sector_name)

    def score_swing(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_swing_idea(stock, self.sector_name, min_volume=100000)

    def score_long_term(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_long_term_idea(stock, self.sector_name, max_de=200, invest_threshold=60)

    def score_dark_horse(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_dark_horse_idea(stock, self.sector_name, max_mcap=25000)
