"""Banks & Financial Services sector scanner."""

from typing import List, Dict, Any, Optional
from src.sectors.base import BaseSectorScanner
from src.shared.models import StockIdea
from src.sectors._helpers import (
    enrich_universe, build_swing_idea, build_long_term_idea, build_dark_horse_idea,
)

UNIVERSE = [
    {"symbol": "HDFCBANK", "name": "HDFC Bank Ltd"},
    {"symbol": "ICICIBANK", "name": "ICICI Bank Ltd"},
    {"symbol": "SBIN", "name": "State Bank of India"},
    {"symbol": "KOTAKBANK", "name": "Kotak Mahindra Bank Ltd"},
    {"symbol": "AXISBANK", "name": "Axis Bank Ltd"},
    {"symbol": "INDUSINDBK", "name": "IndusInd Bank Ltd"},
    {"symbol": "BANKBARODA", "name": "Bank of Baroda"},
    {"symbol": "PNB", "name": "Punjab National Bank"},
    {"symbol": "BAJFINANCE", "name": "Bajaj Finance Ltd"},
    {"symbol": "BAJAJFINSV", "name": "Bajaj Finserv Ltd"},
    {"symbol": "HDFCLIFE", "name": "HDFC Life Insurance"},
    {"symbol": "SBILIFE", "name": "SBI Life Insurance"},
    {"symbol": "CHOLAFIN", "name": "Cholamandalam Investment"},
    {"symbol": "MFSL", "name": "Max Financial Services"},
]


class BanksFinancialsScanner(BaseSectorScanner):
    sector_key = "banks_financials"
    sector_name = "Banks & Financial Services"

    def get_universe(self) -> List[Dict[str, Any]]:
        return enrich_universe(UNIVERSE, self.sector_name)

    def score_swing(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_swing_idea(stock, self.sector_name, min_volume=80000)

    def score_long_term(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        # Banks can carry higher leverage; relax debt filter
        return build_long_term_idea(stock, self.sector_name, max_de=500, invest_threshold=62)

    def score_dark_horse(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        return build_dark_horse_idea(stock, self.sector_name, max_mcap=25000)
