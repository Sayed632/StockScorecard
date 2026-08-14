"""
Base class for all sector scanners.
Every sector implements the same interface.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from src.shared.models import StockIdea, EngineType


class BaseSectorScanner(ABC):
    sector_key: str = "base"
    sector_name: str = "Base Sector"

    def __init__(self, config: dict = None):
        self.config = config or {}

    @abstractmethod
    def get_universe(self) -> List[Dict[str, Any]]:
        """Return list of stock dicts belonging to this sector."""
        pass

    @abstractmethod
    def score_swing(self, stock: Dict[str, Any]) -> StockIdea | None:
        """Return a Swing StockIdea or None."""
        pass

    @abstractmethod
    def score_long_term(self, stock: Dict[str, Any]) -> StockIdea | None:
        """Return a Long-term StockIdea or None."""
        pass

    @abstractmethod
    def score_dark_horse(self, stock: Dict[str, Any]) -> StockIdea | None:
        """Return a Dark Horse StockIdea or None."""
        pass

    def run(self) -> Dict[str, List[StockIdea]]:
        """Run all three engines for this sector."""
        universe = self.get_universe()
        swing, long_term, dark = [], [], []

        for stock in universe:
            s = self.score_swing(stock)
            if s:
                swing.append(s)
            lt = self.score_long_term(stock)
            if lt:
                long_term.append(lt)
            dh = self.score_dark_horse(stock)
            if dh:
                dark.append(dh)

        # Sort by score descending
        swing.sort(key=lambda x: x.score, reverse=True)
        long_term.sort(key=lambda x: x.score, reverse=True)
        dark.sort(key=lambda x: x.score, reverse=True)

        return {
            "swing": swing,
            "long_term": long_term,
            "dark_horse": dark,
        }