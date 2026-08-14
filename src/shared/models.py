"""
Core data models used across the system.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


class Action(str, Enum):
    BUY_NOW = "🟢 BUY NOW"
    WAIT = "🟡 WAIT"
    HOLD_INVEST = "🔵 HOLD / INVEST"
    EXIT_AVOID = "🔴 EXIT / AVOID"
    WATCHLIST = "⚪ WATCHLIST"
    DARK_HORSE_BUY = "🦄🟢 DARK HORSE – BUY NOW"
    DARK_HORSE_INVEST = "🦄🔵 DARK HORSE – INVEST"
    DARK_HORSE_WATCH = "🦄⚪ DARK HORSE – WATCHLIST"


class EngineType(str, Enum):
    SWING = "swing"
    LONG_TERM = "long_term"
    DARK_HORSE = "dark_horse"


@dataclass
class StockIdea:
    symbol: str
    name: str
    sector: str
    engine: EngineType
    action: Action
    reason: str
    market_cap_cr: Optional[float] = None
    market_cap_bucket: Optional[str] = None
    score: float = 0.0
    catalysts: List[str] = field(default_factory=list)
    extras: Dict[str, Any] = field(default_factory=dict)

    def to_telegram_line(self) -> str:
        return f"{self.action}  <b>{self.symbol}</b> – {self.reason}"


@dataclass
class ScanResult:
    scan_time: datetime
    frequency: int                    # 1, 2 or 3
    swing_ideas: List[StockIdea] = field(default_factory=list)
    long_term_ideas: List[StockIdea] = field(default_factory=list)
    dark_horse_ideas: List[StockIdea] = field(default_factory=list)
    sector_summary: Dict[str, str] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)