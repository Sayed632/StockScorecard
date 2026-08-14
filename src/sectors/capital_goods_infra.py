"""Capital Goods & Infrastructure sector scanner."""

from typing import List, Dict, Any, Optional
from src.sectors.base import BaseSectorScanner
from src.shared.models import StockIdea
from src.sectors._helpers import (
    enrich_universe, build_swing_idea, build_long_term_idea, build_dark_horse_idea,
)

UNIVERSE = [
    {"symbol": "LT", "name": "Larsen & Toubro Ltd"},
    {"symbol": "SIEMENS", "name": "Siemens Ltd"},
    {"symbol": "ABB", "name": "ABB India Ltd"},
    {"symbol": "HAVELLS", "name": "Havells India Ltd"},
    {"symbol": "POLYCAB", "name": "Polycab India Ltd"},
    {"symbol": "KEI", "name": "KEI Industries Ltd"},
    {"symbol": "THERMAX", "name": "Thermax Ltd"},
    {"symbol": "BHEL", "name": "Bharat Heavy Electricals"},
    {"symbol": "CUMMINSIND", "name": "Cummins India Ltd"},
    {"symbol": "AIAENG", "name": "AIA Engineering Ltd"},
    {"symbol": "KIRLOSENG", "name": "Kirloskar Oil Engines"},
    {"symbol": "IRB", "name": "IRB Infrastructure Developers"},
    {"symbol": "NCC", "name": "NCC Ltd"},
    {"symbol": "KPITTECH", "name": "KPIT Technologies Ltd"},
]


class CapitalGoodsInfraScanner(BaseSectorScanner):
    sector_key = "capital_goods_infra"
    sector_name = "Capital Goods & Infra"

    def get_universe(self) -> List[Dict[str, Any]]:
        return enrich_universe(UNIVERSE, self.sector_name)

    def score_swing(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_swing_idea(stock, self.sector_name, min_volume=40000)

    def score_long_term(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_long_term_idea(stock, self.sector_name, max_de=150, invest_threshold=62)

    def score_dark_horse(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_dark_horse_idea(stock, self.sector_name, max_mcap=20000)
