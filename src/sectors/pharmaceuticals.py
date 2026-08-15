"""
Pharmaceutical Sector Scanner
Implements the approved Pharmaceutical Sector Detailed Rules (v1.0)
"""

from typing import List, Dict, Any, Optional
from src.sectors.base import BaseSectorScanner
from src.shared.models import StockIdea, Action, EngineType
from src.data_fetch.fundamentals import fetch_basic_fundamentals
from src.data_fetch.prices import fetch_price_history
from src.factors.technical import score_technical
from src.factors.quality import score_quality
from src.factors.growth import score_growth
from src.factors.valuation import score_valuation
import numpy as np


# Starter universe – will be expanded with full NSE mapping later
PHARMA_UNIVERSE = [
    {"symbol": "SUNPHARMA", "name": "Sun Pharmaceutical Industries Ltd"},
    {"symbol": "DRREDDY", "name": "Dr. Reddy's Laboratories Ltd"},
    {"symbol": "CIPLA", "name": "Cipla Ltd"},
    {"symbol": "DIVISLAB", "name": "Divi's Laboratories Ltd"},
    {"symbol": "LAURUSLABS", "name": "Laurus Labs Ltd"},
    {"symbol": "AUROPHARMA", "name": "Aurobindo Pharma Ltd"},
    {"symbol": "LUPIN", "name": "Lupin Ltd"},
    {"symbol": "TORNTPHARM", "name": "Torrent Pharmaceuticals Ltd"},
    {"symbol": "ALKEM", "name": "Alkem Laboratories Ltd"},
    {"symbol": "BIOCON", "name": "Biocon Ltd"},
    {"symbol": "GLENMARK", "name": "Glenmark Pharmaceuticals Ltd"},
    {"symbol": "IPCALAB", "name": "IPCA Laboratories Ltd"},
    {"symbol": "NATCOPHARM", "name": "Natco Pharma Ltd"},
    {"symbol": "PFIZER", "name": "Pfizer Ltd"},
    {"symbol": "SANOFI", "name": "Sanofi India Ltd"},
    {"symbol": "ABBOTTINDIA", "name": "Abbott India Ltd"},
    {"symbol": "KOPRAN", "name": "Kopran Ltd"},
]


class PharmaceuticalsScanner(BaseSectorScanner):
    sector_key = "pharmaceuticals"
    sector_name = "Pharmaceuticals & Healthcare"

    def get_universe(self) -> List[Dict[str, Any]]:
        stocks = []
        for item in PHARMA_UNIVERSE:
            yahoo = item["symbol"] + ".NS"
            fund = fetch_basic_fundamentals(yahoo)
            fund["name"] = item["name"]
            fund["sector"] = self.sector_name
            fund["yahoo_symbol"] = yahoo
            # Attach price history for technicals
            prices = fetch_price_history(yahoo, period="1y")
            fund["_prices"] = prices
            stocks.append(fund)
        return stocks

    def _market_cap_bucket(self, mcap: Optional[float]) -> str:
        if mcap is None or np.isnan(mcap):
            return "Unknown"
        if mcap >= 20000:
            return "Large"
        if mcap >= 5000:
            return "Mid"
        if mcap >= 500:
            return "Small"
        return "Micro"

    def score_swing(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        """
        Swing rules (approved):
        - Liquidity + trend structure
        - Relative strength / volume
        - Catalyst awareness (placeholder for news layer)
        """
        symbol = stock.get("symbol", "")
        name = stock.get("name", symbol)
        mcap = stock.get("market_cap_cr")
        prices = stock.get("_prices")

        t_score = score_technical(prices)
        # Simple liquidity proxy
        avg_vol = stock.get("avg_volume") or 0

        if avg_vol and avg_vol < 30000:
            return None  # hard liquidity filter

        catalysts = []
        score = t_score

        # Trend bonus
        if t_score >= 65:
            score += 10
            catalysts.append("Strong technical trend")
        elif t_score >= 50:
            score += 3
            catalysts.append("Improving momentum")

        # Quality of business still matters even for swing
        q = score_quality(stock)
        if q >= 70:
            score += 5

        action = Action.WATCHLIST
        reason = "Setup under observation"

        if score >= 72 and t_score >= 60:
            action = Action.BUY_NOW
            reason = "Strong momentum + technical confirmation"
            if catalysts:
                reason += f" ({', '.join(catalysts[:2])})"
        elif score >= 58:
            action = Action.WAIT
            reason = "Setup forming – waiting for confirmation"
        elif t_score < 35:
            action = Action.EXIT_AVOID
            reason = "Weak technical structure"

        return StockIdea(
            symbol=symbol,
            name=name,
            sector=self.sector_name,
            engine=EngineType.SWING,
            action=action,
            reason=reason,
            market_cap_cr=mcap,
            market_cap_bucket=self._market_cap_bucket(mcap),
            score=round(score, 1),
            catalysts=catalysts,
        )

    def score_long_term(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        """
        Long-term rules (approved):
        - Quality + growth durability
        - Acceptable leverage
        - No major red flags (simplified)
        """
        symbol = stock.get("symbol", "")
        name = stock.get("name", symbol)
        mcap = stock.get("market_cap_cr")

        q = score_quality(stock)
        g = score_growth(stock)
        v = score_valuation(stock)

        # Leverage check
        de = stock.get("debt_to_equity")
        if de is not None and de > 150:  # yfinance often gives % or ratio
            return None

        score = 0.40 * q + 0.35 * g + 0.25 * v

        action = Action.WATCHLIST
        reason = "Quality under review"

        if score >= 68 and q >= 65:
            action = Action.HOLD_INVEST
            reason = "Strong quality + durable growth profile"
        elif score >= 55:
            action = Action.WATCHLIST
            reason = "Decent business – waiting for better entry"
        else:
            action = Action.EXIT_AVOID
            reason = "Quality or growth not convincing yet"

        return StockIdea(
            symbol=symbol,
            name=name,
            sector=self.sector_name,
            engine=EngineType.LONG_TERM,
            action=action,
            reason=reason,
            market_cap_cr=mcap,
            market_cap_bucket=self._market_cap_bucket(mcap),
            score=round(score, 1),
        )

    def score_dark_horse(self, stock: Dict[str, Any]) -> Optional[StockIdea]:
        """
        Dark Horse rules (approved):
        - Prefer Mid / Small / Micro
        - Fundamentally clean + improving
        - Not overcrowded large-cap names
        """
        symbol = stock.get("symbol", "")
        name = stock.get("name", symbol)
        mcap = stock.get("market_cap_cr")

        if mcap is None or mcap > 18000:  # exclude pure large-caps
            return None

        q = score_quality(stock)
        g = score_growth(stock)
        t = score_technical(stock.get("_prices"))

        # Must have decent fundamentals
        if q < 55 or g < 45:
            return None

        score = 0.35 * q + 0.30 * g + 0.35 * t

        # Bonus for smaller size (true dark horse preference)
        if mcap and mcap < 8000:
            score += 8
        if mcap and mcap < 3000:
            score += 5

        action = Action.DARK_HORSE_WATCH
        reason = "Emerging candidate – monitoring"

        if score >= 70 and t >= 55:
            action = Action.DARK_HORSE_BUY
            reason = "Hidden strength + early momentum"
        elif score >= 62:
            action = Action.DARK_HORSE_INVEST
            reason = "Solid mid/small name with improving fundamentals"
        else:
            return None  # not strong enough to surface

        return StockIdea(
            symbol=symbol,
            name=name,
            sector=self.sector_name,
            engine=EngineType.DARK_HORSE,
            action=action,
            reason=reason,
            market_cap_cr=mcap,
            market_cap_bucket=self._market_cap_bucket(mcap),
            score=round(score, 1),
        )
