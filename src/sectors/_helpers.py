"""
Shared helpers for sector scanners.
"""

from typing import List, Dict, Any, Optional
import numpy as np
from src.data_fetch.fundamentals import fetch_basic_fundamentals
from src.data_fetch.prices import fetch_price_history
from src.factors.technical import score_technical
from src.factors.quality import score_quality
from src.factors.growth import score_growth
from src.factors.valuation import score_valuation
from src.shared.models import StockIdea, Action, EngineType


def enrich_universe(items: List[Dict[str, str]], sector_name: str) -> List[Dict[str, Any]]:
    """Fetch fundamentals + prices for a list of {symbol, name}."""
    stocks = []
    for item in items:
        yahoo = item["symbol"] + ".NS"
        fund = fetch_basic_fundamentals(yahoo)
        fund["name"] = item["name"]
        fund["sector"] = sector_name
        fund["yahoo_symbol"] = yahoo
        fund["_prices"] = fetch_price_history(yahoo, period="1y")
        stocks.append(fund)
    return stocks


def market_cap_bucket(mcap: Optional[float]) -> str:
    if mcap is None or (isinstance(mcap, float) and np.isnan(mcap)):
        return "Unknown"
    if mcap >= 20000:
        return "Large"
    if mcap >= 5000:
        return "Mid"
    if mcap >= 500:
        return "Small"
    return "Micro"


def build_swing_idea(
    stock: Dict[str, Any],
    sector_name: str,
    min_volume: int = 40000,
    buy_threshold: float = 70,
    wait_threshold: float = 55,
) -> Optional[StockIdea]:
    symbol = stock.get("symbol", "")
    name = stock.get("name", symbol)
    mcap = stock.get("market_cap_cr")
    prices = stock.get("_prices")
    avg_vol = stock.get("avg_volume") or 0

    if avg_vol and avg_vol < min_volume:
        return None

    t_score = score_technical(prices)
    q = score_quality(stock)
    score = t_score
    catalysts = []

    if t_score >= 65:
        score += 10
        catalysts.append("Strong technical trend")
    elif t_score >= 50:
        score += 3
        catalysts.append("Improving momentum")
    if q >= 70:
        score += 5

    if score >= buy_threshold and t_score >= 58:
        action = Action.BUY_NOW
        reason = "Strong momentum + technical confirmation"
        if catalysts:
            reason += f" ({', '.join(catalysts[:2])})"
    elif score >= wait_threshold:
        action = Action.WAIT
        reason = "Setup forming – waiting for confirmation"
    elif t_score < 35:
        action = Action.EXIT_AVOID
        reason = "Weak technical structure"
    else:
        action = Action.WATCHLIST
        reason = "Setup under observation"

    return StockIdea(
        symbol=symbol,
        name=name,
        sector=sector_name,
        engine=EngineType.SWING,
        action=action,
        reason=reason,
        market_cap_cr=mcap,
        market_cap_bucket=market_cap_bucket(mcap),
        score=round(score, 1),
        catalysts=catalysts,
    )


def build_long_term_idea(
    stock: Dict[str, Any],
    sector_name: str,
    max_de: float = 200,
    invest_threshold: float = 65,
) -> Optional[StockIdea]:
    symbol = stock.get("symbol", "")
    name = stock.get("name", symbol)
    mcap = stock.get("market_cap_cr")

    de = stock.get("debt_to_equity")
    if de is not None and de > max_de:
        return None

    q = score_quality(stock)
    g = score_growth(stock)
    v = score_valuation(stock)
    score = 0.40 * q + 0.35 * g + 0.25 * v

    if score >= invest_threshold and q >= 60:
        action = Action.HOLD_INVEST
        reason = "Strong quality + durable growth profile"
    elif score >= 52:
        action = Action.WATCHLIST
        reason = "Decent business – waiting for better entry"
    else:
        action = Action.EXIT_AVOID
        reason = "Quality or growth not convincing yet"

    return StockIdea(
        symbol=symbol,
        name=name,
        sector=sector_name,
        engine=EngineType.LONG_TERM,
        action=action,
        reason=reason,
        market_cap_cr=mcap,
        market_cap_bucket=market_cap_bucket(mcap),
        score=round(score, 1),
    )


def build_dark_horse_idea(
    stock: Dict[str, Any],
    sector_name: str,
    max_mcap: float = 18000,
) -> Optional[StockIdea]:
    symbol = stock.get("symbol", "")
    name = stock.get("name", symbol)
    mcap = stock.get("market_cap_cr")

    if mcap is None or mcap > max_mcap:
        return None

    q = score_quality(stock)
    g = score_growth(stock)
    t = score_technical(stock.get("_prices"))

    if q < 52 or g < 42:
        return None

    score = 0.35 * q + 0.30 * g + 0.35 * t
    if mcap < 8000:
        score += 8
    if mcap < 3000:
        score += 5

    if score >= 68 and t >= 52:
        action = Action.DARK_HORSE_BUY
        reason = "Hidden strength + early momentum"
    elif score >= 60:
        action = Action.DARK_HORSE_INVEST
        reason = "Solid mid/small name with improving fundamentals"
    else:
        return None

    return StockIdea(
        symbol=symbol,
        name=name,
        sector=sector_name,
        engine=EngineType.DARK_HORSE,
        action=action,
        reason=reason,
        market_cap_cr=mcap,
        market_cap_bucket=market_cap_bucket(mcap),
        score=round(score, 1),
    )
