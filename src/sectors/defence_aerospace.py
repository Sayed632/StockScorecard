"""Defence & Aerospace sector scanner.

Aligned with rising India aerospace / defence manufacturing news flow:
  OEMs, shipyards, electronics, drones, space-tech, precision aero manufacturing.
"""

from typing import List, Dict, Any, Optional
from src.sectors.base import BaseSectorScanner
from src.shared.models import StockIdea
from src.sectors._helpers import (
    enrich_universe, build_swing_idea, build_long_term_idea, build_dark_horse_idea,
)

UNIVERSE = [
    # Core defence PSUs / majors
    {"symbol": "HAL", "name": "Hindustan Aeronautics Ltd"},
    {"symbol": "BEL", "name": "Bharat Electronics Ltd"},
    {"symbol": "BDL", "name": "Bharat Dynamics Ltd"},
    {"symbol": "BHEL", "name": "Bharat Heavy Electricals Ltd"},
    {"symbol": "MAZDOCK", "name": "Mazagon Dock Shipbuilders"},
    {"symbol": "COCHINSHIP", "name": "Cochin Shipyard Ltd"},
    {"symbol": "GRSE", "name": "Garden Reach Shipbuilders"},
    {"symbol": "BEML", "name": "BEML Ltd"},
    {"symbol": "MIDHANI", "name": "Mishra Dhatu Nigam Ltd"},
    # Private aerospace / defence tech
    {"symbol": "AEQUS", "name": "Aequs Ltd"},
    {"symbol": "DATAPATTNS", "name": "Data Patterns (India) Ltd"},
    {"symbol": "PARAS", "name": "Paras Defence & Space"},
    {"symbol": "MTARTECH", "name": "MTAR Technologies Ltd"},
    {"symbol": "SOLARINDS", "name": "Solar Industries India"},
    {"symbol": "IDEAFORGE", "name": "ideaForge Technology Ltd"},
    {"symbol": "ZENTECH", "name": "Zen Technologies Ltd"},
    {"symbol": "APOLLO", "name": "Apollo Micro Systems Ltd"},
    {"symbol": "DCXINDIA", "name": "DCX Systems Ltd"},
    {"symbol": "ASTRAMICRO", "name": "Astra Microwave Products Ltd"},
    {"symbol": "CYIENT", "name": "Cyient Ltd"},
    {"symbol": "TATAELXSI", "name": "Tata Elxsi Ltd"},
    {"symbol": "LT", "name": "Larsen & Toubro Ltd"},
    {"symbol": "WALCHANNAG", "name": "Walchandnagar Industries Ltd"},
    {"symbol": "DYNAMATECH", "name": "Dynamatic Technologies Ltd"},
    {"symbol": "PREMEXPLN", "name": "Premier Explosives Ltd"},
    {"symbol": "NESCO", "name": "Nesco Ltd"},
]


class DefenceAerospaceScanner(BaseSectorScanner):
    sector_key = "defence_aerospace"
    sector_name = "Defence & Aerospace"

    def get_universe(self) -> List[Dict[str, Any]]:
        return enrich_universe(UNIVERSE, self.sector_name)

    def score_swing(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        # Slightly lower volume floor for mid/small aero names
        return build_swing_idea(stock, self.sector_name, min_volume=30000, buy_threshold=66)

    def score_long_term(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_long_term_idea(stock, self.sector_name, max_de=120, invest_threshold=60)

    def score_dark_horse(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_dark_horse_idea(stock, self.sector_name, max_mcap=30000)
