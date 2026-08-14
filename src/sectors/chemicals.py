"""Chemicals sector scanner."""

from typing import List, Dict, Any, Optional
from src.sectors.base import BaseSectorScanner
from src.shared.models import StockIdea
from src.sectors._helpers import (
    enrich_universe, build_swing_idea, build_long_term_idea, build_dark_horse_idea,
)

UNIVERSE = [
    {"symbol": "PIDILITIND", "name": "Pidilite Industries Ltd"},
    {"symbol": "SRF", "name": "SRF Ltd"},
    {"symbol": "AARTIIND", "name": "Aarti Industries Ltd"},
    {"symbol": "DEEPAKNTR", "name": "Deepak Nitrite Ltd"},
    {"symbol": "NAVINFLUOR", "name": "Navin Fluorine International"},
    {"symbol": "ALKYLAMINE", "name": "Alkyl Amines Chemicals"},
    {"symbol": "CLEAN", "name": "Clean Science & Technology"},
    {"symbol": "FINEORG", "name": "Fine Organic Industries"},
    {"symbol": "GALAXYSURF", "name": "Galaxy Surfactants Ltd"},
    {"symbol": "TATACHEM", "name": "Tata Chemicals Ltd"},
    {"symbol": "UPL", "name": "UPL Ltd"},
    {"symbol": "PIIND", "name": "PI Industries Ltd"},
]


class ChemicalsScanner(BaseSectorScanner):
    sector_key = "chemicals"
    sector_name = "Chemicals"

    def get_universe(self) -> List[Dict[str, Any]]:
        return enrich_universe(UNIVERSE, self.sector_name)

    def score_swing(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_swing_idea(stock, self.sector_name, min_volume=30000)

    def score_long_term(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_long_term_idea(stock, self.sector_name, max_de=120, invest_threshold=64)

    def score_dark_horse(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_dark_horse_idea(stock, self.sector_name, max_mcap=15000)
