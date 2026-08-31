"""
Others / Residual scanner.
Liquid names that often sit outside the main dedicated sector universes
(conglomerates, logistics, hospitality, diversified services, etc.).
Includes selected tracked investor holdings (e.g. Kela-type mid/small names).
"""

from typing import List, Dict, Any, Optional
from src.sectors.base import BaseSectorScanner
from src.shared.models import StockIdea
from src.sectors._helpers import (
    enrich_universe, build_swing_idea, build_long_term_idea, build_dark_horse_idea,
)

UNIVERSE = [
    # Conglomerates / diversified
    {"symbol": "ADANIENT", "name": "Adani Enterprises Ltd"},
    {"symbol": "ADANIPORTS", "name": "Adani Ports & SEZ"},
    {"symbol": "GRASIM", "name": "Grasim Industries Ltd"},
    {"symbol": "SRF", "name": "SRF Ltd"},
    # Logistics / transport services
    {"symbol": "CONCOR", "name": "Container Corporation of India"},
    {"symbol": "BLUEDART", "name": "Blue Dart Express Ltd"},
    {"symbol": "DELHIVERY", "name": "Delhivery Ltd"},
    {"symbol": "TCI", "name": "Transport Corporation of India"},
    # Hospitality / travel
    {"symbol": "INDHOTEL", "name": "Indian Hotels Company"},
    {"symbol": "EIHOTEL", "name": "EIH Ltd"},
    {"symbol": "LEMONTREE", "name": "Lemon Tree Hotels"},
    {"symbol": "INDIGO", "name": "InterGlobe Aviation Ltd"},
    # Consumer discretionary / retail residual
    {"symbol": "TITAN", "name": "Titan Company Ltd"},
    {"symbol": "TRENT", "name": "Trent Ltd"},
    {"symbol": "DMART", "name": "Avenue Supermarts Ltd"},
    {"symbol": "NYKAA", "name": "FSN E-Commerce Ventures"},
    # Agri / fertilizers residual
    {"symbol": "COROMANDEL", "name": "Coromandel International"},
    {"symbol": "CHAMBLFERT", "name": "Chambal Fertilisers"},
    {"symbol": "FACT", "name": "Fertilisers & Chemicals Travancore"},
    # Misc liquid residual
    {"symbol": "IRCTC", "name": "IRCTC Ltd"},
    {"symbol": "PIIND", "name": "PI Industries Ltd"},
    {"symbol": "DIXON", "name": "Dixon Technologies Ltd"},
    # Tracked investor / mid-small residual (Kela portfolio examples)
    {"symbol": "RPTECH", "name": "Rashi Peripherals Ltd"},
    {"symbol": "WINDMACHIN", "name": "Windsor Machines Ltd"},
    {"symbol": "SUBAM", "name": "Subam Papers Ltd"},
    {"symbol": "REPRO", "name": "Repro India Ltd"},
    {"symbol": "EMKAY", "name": "Emkay Global Financial Services"},
    {"symbol": "UNIECOM", "name": "Unicommerce eSolutions Ltd"},
    {"symbol": "IRIS", "name": "IRIS Business Services Ltd"},
    {"symbol": "BOMDYEING", "name": "Bombay Dyeing & Mfg Co"},
]


class OthersResidualScanner(BaseSectorScanner):
    sector_key = "others_residual"
    sector_name = "Others / Residual"

    def get_universe(self) -> List[Dict[str, Any]]:
        return enrich_universe(UNIVERSE, self.sector_name)

    def score_swing(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_swing_idea(stock, self.sector_name, min_volume=50000)

    def score_long_term(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_long_term_idea(stock, self.sector_name, max_de=180, invest_threshold=62)

    def score_dark_horse(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_dark_horse_idea(stock, self.sector_name, max_mcap=20000)
