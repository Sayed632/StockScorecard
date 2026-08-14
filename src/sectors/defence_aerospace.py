"""Defence & Aerospace sector scanner."""

from typing import List, Dict, Any, Optional
from src.sectors.base import BaseSectorScanner
from src.shared.models import StockIdea
from src.sectors._helpers import (
    enrich_universe, build_swing_idea, build_long_term_idea, build_dark_horse_idea,
)

UNIVERSE = [
    {"symbol": "HAL", "name": "Hindustan Aeronautics Ltd"},
    {"symbol": "BEL", "name": "Bharat Electronics Ltd"},
    {"symbol": "BHEL", "name": "Bharat Heavy Electricals Ltd"},
    {"symbol": "MAZDOCK", "name": "Mazagon Dock Shipbuilders"},
    {"symbol": "COCHINSHIP", "name": "Cochin Shipyard Ltd"},
    {"symbol": "GRSE", "name": "Garden Reach Shipbuilders"},
    {"symbol": "BEML", "name": "BEML Ltd"},
    {"symbol": "DATAPATTNS", "name": "Data Patterns (India) Ltd"},
    {"symbol": "PARAS", "name": "Paras Defence & Space"},
    {"symbol": "MTARTECH", "name": "MTAR Technologies Ltd"},
    {"symbol": "SOLARINDS", "name": "Solar Industries India"},
    {"symbol": "IDEAFORGE", "name": "ideaForge Technology Ltd"},
]


class DefenceAerospaceScanner(BaseSectorScanner):
    sector_key = "defence_aerospace"
    sector_name = "Defence & Aerospace"

    def get_universe(self) -> List[Dict[str, Any]]:
        return enrich_universe(UNIVERSE, self.sector_name)

    def score_swing(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_swing_idea(stock, self.sector_name, min_volume=40000, buy_threshold=68)

    def score_long_term(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_long_term_idea(stock, self.sector_name, max_de=120, invest_threshold=62)

    def score_dark_horse(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_dark_horse_idea(stock, self.sector_name, max_mcap=25000)
