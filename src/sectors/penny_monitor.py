"""
Penny Stocks Monitor – sector-agnostic.
High-risk segment: low price + small/micro market-cap names.
"""

from typing import List, Dict, Any, Optional
from src.sectors.base import BaseSectorScanner
from src.shared.models import StockIdea, Action, EngineType
from src.sectors._helpers import enrich_universe, market_cap_bucket
from src.factors.technical import score_technical
from src.factors.quality import score_quality
from src.factors.growth import score_growth

# Starter penny / micro-cap watch universe (expandable)
# Focus: low absolute price and/or micro market-cap names that still trade
PENNY_UNIVERSE = [
    {"symbol": "YESBANK", "name": "Yes Bank Ltd"},
    {"symbol": "IDEA", "name": "Vodafone Idea Ltd"},
    {"symbol": "SUZLON", "name": "Suzlon Energy Ltd"},
    {"symbol": "JPPOWER", "name": "Jaiprakash Power Ventures"},
    {"symbol": "RPOWER", "name": "Reliance Power Ltd"},
    {"symbol": "RTNPOWER", "name": "RattanIndia Power Ltd"},
    {"symbol": "FSL", "name": "Firstsource Solutions"},
    {"symbol": "NETWORK18", "name": "Network18 Media"},
    {"symbol": "SAIL", "name": "Steel Authority of India"},
    {"symbol": "NATIONALUM", "name": "National Aluminium Co"},
    {"symbol": "HINDCOPPER", "name": "Hindustan Copper Ltd"},
    {"symbol": "IREDA", "name": "Indian Renewable Energy Dev Agency"},
    {"symbol": "PNB", "name": "Punjab National Bank"},
    {"symbol": "BANKBARODA", "name": "Bank of Baroda"},
    {"symbol": "UCOBANK", "name": "UCO Bank"},
    {"symbol": "CENTRALBK", "name": "Central Bank of India"},
    {"symbol": "IOB", "name": "Indian Overseas Bank"},
    {"symbol": "TRIDENT", "name": "Trident Ltd"},
    {"symbol": "JAICORPLTD", "name": "Jai Corp Ltd"},
    {"symbol": "GMRAIRPORT", "name": "GMR Airports Infrastructure"},
    {"symbol": "BOMDYEING", "name": "Bombay Dyeing & Mfg Co"},
    {"symbol": "SAMMAANCAP", "name": "Indiabulls Housing Finance"},
]


class PennyMonitorScanner(BaseSectorScanner):
    """
    Sector-agnostic penny / micro monitor.
    Criteria (practical India definition used here):
      - Last price preferably < ₹50  OR  market cap < ₹5,000 Cr
      - Minimum liquidity so it is tradable
      - Basic technical / quality screen so pure garbage is filtered
    """

    sector_key = "penny_monitor"
    sector_name = "Penny / Micro Monitor"

    # Thresholds
    MAX_PRICE = 50.0          # ₹
    MAX_MCAP_CR = 5000.0      # soft micro/small preference
    MIN_AVG_VOLUME = 100000   # need some liquidity

    def get_universe(self) -> List[Dict[str, Any]]:
        return enrich_universe(PENNY_UNIVERSE, self.sector_name)

    def _is_penny_candidate(self, stock: Dict[str, Any]) -> bool:
        mcap = stock.get("market_cap_cr")
        prices = stock.get("_prices")
        avg_vol = stock.get("avg_volume") or 0

        if avg_vol and avg_vol < self.MIN_AVG_VOLUME:
            return False

        last_price = None
        if prices is not None and len(prices) > 0:
            last_price = float(prices["close"].iloc[-1])

        # Qualify if cheap in price OR small in size
        price_ok = last_price is not None and last_price <= self.MAX_PRICE
        mcap_ok = mcap is not None and mcap <= self.MAX_MCAP_CR

        return bool(price_ok or mcap_ok)

    def score_swing(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        """Penny monitor mainly surfaces as high-risk swing / speculative ideas."""
        if not self._is_penny_candidate(stock):
            return None

        symbol = stock.get("symbol", "")
        name = stock.get("name", symbol)
        mcap = stock.get("market_cap_cr")
        prices = stock.get("_prices")
        t = score_technical(prices)
        q = score_quality(stock)

        if t < 40:
            return None  # avoid structurally weak names

        score = 0.55 * t + 0.25 * q + 20  # base bump for monitor visibility
        last_price = float(prices["close"].iloc[-1]) if prices is not None and len(prices) else None
        price_tag = f"~₹{last_price:.1f}" if last_price else ""

        if score >= 72 and t >= 60:
            action = Action.BUY_NOW
            reason = f"Penny momentum setup {price_tag} – HIGH RISK"
        elif score >= 58:
            action = Action.WAIT
            reason = f"Penny watch – setup forming {price_tag}"
        else:
            action = Action.WATCHLIST
            reason = f"On penny radar {price_tag}"

        return StockIdea(
            symbol=symbol,
            name=name,
            sector=self.sector_name,
            engine=EngineType.SWING,
            action=action,
            reason=reason,
            market_cap_cr=mcap,
            market_cap_bucket=market_cap_bucket(mcap),
            score=round(min(score, 99), 1),
            catalysts=["Penny/Micro monitor"],
            extras={"penny": True, "last_price": last_price},
        )

    def score_long_term(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        """Very selective – most pennies are not long-term compounds."""
        if not self._is_penny_candidate(stock):
            return None

        q = score_quality(stock)
        g = score_growth(stock)
        if q < 58 or g < 50:
            return None

        symbol = stock.get("symbol", "")
        name = stock.get("name", symbol)
        mcap = stock.get("market_cap_cr")
        score = 0.5 * q + 0.5 * g

        if score >= 65:
            action = Action.HOLD_INVEST
            reason = "Rare quality penny – speculative long-term only"
        else:
            return None

        return StockIdea(
            symbol=symbol,
            name=name,
            sector=self.sector_name,
            engine=EngineType.LONG_TERM,
            action=action,
            reason=reason,
            market_cap_cr=mcap,
            market_cap_bucket=market_cap_bucket(mcap),
            score=round(score, 1),
            extras={"penny": True},
        )

    def score_dark_horse(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        """Penny + improving fundamentals can appear as aggressive Dark Horse."""
        if not self._is_penny_candidate(stock):
            return None

        q = score_quality(stock)
        g = score_growth(stock)
        t = score_technical(stock.get("_prices"))
        if q < 50 or t < 50:
            return None

        symbol = stock.get("symbol", "")
        name = stock.get("name", symbol)
        mcap = stock.get("market_cap_cr")
        score = 0.3 * q + 0.3 * g + 0.4 * t
        if mcap and mcap < 2000:
            score += 6

        if score >= 66:
            action = Action.DARK_HORSE_BUY
            reason = "Penny Dark Horse – early strength (HIGH RISK)"
        elif score >= 58:
            action = Action.DARK_HORSE_WATCH
            reason = "Penny on Dark Horse radar"
        else:
            return None

        return StockIdea(
            symbol=symbol,
            name=name,
            sector=self.sector_name,
            engine=EngineType.DARK_HORSE,
            action=action,
            reason=reason,
            market_cap_cr=mcap,
            market_cap_bucket=market_cap_bucket(mcap),
            score=round(score, 1),
            extras={"penny": True},
        )
