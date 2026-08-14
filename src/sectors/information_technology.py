"""Information Technology sector scanner."""

from typing import List, Dict, Any, Optional
from src.sectors.base import BaseSectorScanner
from src.shared.models import StockIdea
from src.sectors._helpers import (
    enrich_universe, build_swing_idea, build_long_term_idea, build_dark_horse_idea,
)

UNIVERSE = [
    {"symbol": "TCS", "name": "Tata Consultancy Services Ltd"},
    {"symbol": "INFY", "name": "Infosys Ltd"},
    {"symbol": "HCLTECH", "name": "HCL Technologies Ltd"},
    {"symbol": "WIPRO", "name": "Wipro Ltd"},
    {"symbol": "TECHM", "name": "Tech Mahindra Ltd"},
    {"symbol": "LTIM", "name": "LTIMindtree Ltd"},
    {"symbol": "PERSISTENT", "name": "Persistent Systems Ltd"},
    {"symbol": "COFORGE", "name": "Coforge Ltd"},
    {"symbol": "MPHASIS", "name": "Mphasis Ltd"},
    {"symbol": "OFSS", "name": "Oracle Financial Services"},
    {"symbol": "TATAELXSI", "name": "Tata Elxsi Ltd"},
    {"symbol": "SONATSOFTW", "name": "Sonata Software Ltd"},
]


class InformationTechnologyScanner(BaseSectorScanner):
    sector_key = "information_technology"
    sector_name = "Information Technology"

    def get_universe(self) -> List[Dict[str, Any]]:
        return enrich_universe(UNIVERSE, self.sector_name)

    def score_swing(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_swing_idea(stock, self.sector_name, min_volume=50000)

    def score_long_term(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_long_term_idea(stock, self.sector_name, max_de=80, invest_threshold=66)

    def score_dark_horse(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_dark_horse_idea(stock, self.sector_name, max_mcap=20000)
