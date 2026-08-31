"""Media & Entertainment sector scanner."""

from typing import List, Dict, Any, Optional
from src.sectors.base import BaseSectorScanner
from src.shared.models import StockIdea
from src.sectors._helpers import (
    enrich_universe, build_swing_idea, build_long_term_idea, build_dark_horse_idea,
)

UNIVERSE = [
    {"symbol": "ZEEL", "name": "Zee Entertainment Enterprises"},
    {"symbol": "SUNTV", "name": "Sun TV Network Ltd"},
    {"symbol": "PVRINOX", "name": "PVR INOX Ltd"},
    {"symbol": "NETWORK18", "name": "TV18 Broadcast Ltd"},
    {"symbol": "NETWORK18", "name": "Network18 Media"},
    {"symbol": "DISHTV", "name": "Dish TV India Ltd"},
    {"symbol": "HATHWAY", "name": "Hathway Cable & Datacom"},
    {"symbol": "NAZARA", "name": "Nazara Technologies Ltd"},
    {"symbol": "TIPSMUSIC", "name": "Tips Industries Ltd"},
    {"symbol": "SAREGAMA", "name": "Saregama India Ltd"},
]


class MediaScanner(BaseSectorScanner):
    sector_key = "media"
    sector_name = "Media & Entertainment"

    def get_universe(self) -> List[Dict[str, Any]]:
        return enrich_universe(UNIVERSE, self.sector_name)

    def score_swing(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_swing_idea(stock, self.sector_name, min_volume=30000)

    def score_long_term(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_long_term_idea(stock, self.sector_name, max_de=150, invest_threshold=58)

    def score_dark_horse(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_dark_horse_idea(stock, self.sector_name, max_mcap=15000)
