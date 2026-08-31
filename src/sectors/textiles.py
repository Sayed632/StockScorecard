"""Textiles & Apparel sector scanner."""

from typing import List, Dict, Any, Optional
from src.sectors.base import BaseSectorScanner
from src.shared.models import StockIdea
from src.sectors._helpers import (
    enrich_universe, build_swing_idea, build_long_term_idea, build_dark_horse_idea,
)

UNIVERSE = [
    {"symbol": "PAGEIND", "name": "Page Industries Ltd"},
    {"symbol": "KPRMILL", "name": "KPR Mill Ltd"},
    {"symbol": "WELSPUNLIV", "name": "Welspun India Ltd"},
    {"symbol": "RAYMOND", "name": "Raymond Ltd"},
    {"symbol": "ARVIND", "name": "Arvind Ltd"},
    {"symbol": "TRIDENT", "name": "Trident Ltd"},
    {"symbol": "VARDHACRLC", "name": "Vardhman Acrylics"},
    {"symbol": "INDORAMA", "name": "Indo Rama Synthetics"},
    {"symbol": "GOKEX", "name": "Gokaldas Exports Ltd"},
    {"symbol": "LUXIND", "name": "Lux Industries Ltd"},
    {"symbol": "SANGAMIND", "name": "Sangam (India) Ltd"},
]


class TextilesScanner(BaseSectorScanner):
    sector_key = "textiles"
    sector_name = "Textiles & Apparel"

    def get_universe(self) -> List[Dict[str, Any]]:
        return enrich_universe(UNIVERSE, self.sector_name)

    def score_swing(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_swing_idea(stock, self.sector_name, min_volume=25000)

    def score_long_term(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_long_term_idea(stock, self.sector_name, max_de=120, invest_threshold=60)

    def score_dark_horse(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_dark_horse_idea(stock, self.sector_name, max_mcap=12000)
