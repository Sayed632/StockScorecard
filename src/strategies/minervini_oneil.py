"""
Minervini / O'Neil–style swing strategy (separate sleeve).

Rules inspired by:
- Mark Minervini: VCP / trend template, volatility contraction, breakout
- William O'Neil (CANSLIM): institutional demand, relative strength, breakouts

NOT official products of Minervini or O'Neil. Educational process encoding only.
Horizon: swing (days to several weeks).
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
import pandas as pd

from src.data_fetch.fundamentals import fetch_basic_fundamentals
from src.data_fetch.prices import fetch_price_history
from src.sectors._helpers import market_cap_bucket


# Liquid leaders / growth-oriented universe for this sleeve
MO_UNIVERSE = [
    {"symbol": "RELIANCE", "name": "Reliance Industries"},
    {"symbol": "TCS", "name": "TCS"},
    {"symbol": "INFY", "name": "Infosys"},
    {"symbol": "HDFCBANK", "name": "HDFC Bank"},
    {"symbol": "ICICIBANK", "name": "ICICI Bank"},
    {"symbol": "BAJFINANCE", "name": "Bajaj Finance"},
    {"symbol": "LT", "name": "Larsen & Toubro"},
    {"symbol": "TITAN", "name": "Titan"},
    {"symbol": "DIXON", "name": "Dixon Technologies"},
    {"symbol": "POLYCAB", "name": "Polycab"},
    {"symbol": "PERSISTENT", "name": "Persistent Systems"},
    {"symbol": "COFORGE", "name": "Coforge"},
    {"symbol": "HAL", "name": "Hindustan Aeronautics"},
    {"symbol": "BEL", "name": "Bharat Electronics"},
    {"symbol": "SOLARINDS", "name": "Solar Industries"},
    {"symbol": "TRENT", "name": "Trent"},
    {"symbol": "VARUNBEV", "name": "Varun Beverages"},
    {"symbol": "MAXHEALTH", "name": "Max Healthcare"},
    {"symbol": "DIVISLAB", "name": "Divi's Labs"},
    {"symbol": "SUNPHARMA", "name": "Sun Pharma"},
    {"symbol": "LAURUSLABS", "name": "Laurus Labs"},
    {"symbol": "TVSMOTOR", "name": "TVS Motor"},
    {"symbol": "M&M", "name": "Mahindra & Mahindra"},
    {"symbol": "APLAPOLLO", "name": "APL Apollo"},
    {"symbol": "KEI", "name": "KEI Industries"},
    {"symbol": "CUMMINSIND", "name": "Cummins India"},
    {"symbol": "PIIND", "name": "PI Industries"},
    {"symbol": "INDIGO", "name": "InterGlobe Aviation"},
]


@dataclass
class MOIdea:
    symbol: str
    name: str
    action: str
    reason: str
    score: float
    rs: Optional[float] = None
    vol_ratio: Optional[float] = None
    above_ma: bool = False
    breakout: bool = False
    market_cap_cr: Optional[float] = None
    bucket: str = ""
    extras: Dict[str, Any] = field(default_factory=dict)


def _safe_series(prices: Any) -> Optional[pd.DataFrame]:
    if prices is None:
        return None
    if isinstance(prices, pd.DataFrame) and len(prices) >= 60:
        return prices
    return None


def _relative_strength(close: pd.Series, lookback: int = 63) -> Optional[float]:
    """Simple RS proxy: % change over lookback (higher = stronger)."""
    if len(close) < lookback + 1:
        return None
    past = float(close.iloc[-lookback - 1])
    now = float(close.iloc[-1])
    if past <= 0:
        return None
    return (now / past - 1.0) * 100.0


def _volume_ratio(volume: pd.Series, window: int = 20) -> Optional[float]:
    if len(volume) < window + 5:
        return None
    avg = float(volume.iloc[-window - 1:-1].mean())
    last = float(volume.iloc[-1])
    if avg <= 0:
        return None
    return last / avg


def _trend_template(close: pd.Series) -> Tuple[bool, str]:
    """
    Minervini-like trend template (simplified):
    - Price above 50-day and 150-day MA
    - 50-day MA above 150-day MA
    - Close in upper half of 52-week range
    """
    if len(close) < 160:
        return False, "Insufficient history"
    ma50 = close.rolling(50).mean()
    ma150 = close.rolling(150).mean()
    c = float(close.iloc[-1])
    m50 = float(ma50.iloc[-1])
    m150 = float(ma150.iloc[-1])
    low52 = float(close.iloc[-252:].min()) if len(close) >= 252 else float(close.min())
    high52 = float(close.iloc[-252:].max()) if len(close) >= 252 else float(close.max())
    rng = high52 - low52
    upper_half = c >= (low52 + 0.5 * rng) if rng > 0 else False

    ok = c > m50 and c > m150 and m50 > m150 and upper_half
    bits = []
    bits.append("above MAs" if c > m50 and c > m150 else "below MA")
    bits.append("MA stacked" if m50 > m150 else "MA not stacked")
    bits.append("upper range" if upper_half else "lower range")
    return ok, ", ".join(bits)


def _breakout_signal(close: pd.Series, high: pd.Series, lookback: int = 20) -> Tuple[bool, str]:
    """Close near/above recent high (pivot breakout proxy)."""
    if len(close) < lookback + 2:
        return False, "no pivot"
    pivot = float(high.iloc[-lookback - 1:-1].max())
    c = float(close.iloc[-1])
    if pivot <= 0:
        return False, "no pivot"
    # within 1.5% below pivot counts as testing; above = breakout
    if c >= pivot:
        return True, f"breakout above {pivot:.1f}"
    if c >= pivot * 0.985:
        return False, f"testing pivot {pivot:.1f}"
    return False, f"below pivot {pivot:.1f}"


def _score_mo(stock: Dict[str, Any]) -> Optional[MOIdea]:
    symbol = stock.get("symbol", "")
    name = stock.get("name", symbol)
    mcap = stock.get("market_cap_cr")
    df = _safe_series(stock.get("_prices"))
    if df is None:
        return None

    # column names may vary
    cols = {c.lower(): c for c in df.columns}
    close_c = cols.get("close") or cols.get("adj close")
    vol_c = cols.get("volume")
    high_c = cols.get("high")
    if not close_c:
        return None

    close = df[close_c].astype(float)
    volume = df[vol_c].astype(float) if vol_c else None
    high = df[high_c].astype(float) if high_c else close

    rs = _relative_strength(close)
    vol_ratio = _volume_ratio(volume) if volume is not None else None
    trend_ok, trend_txt = _trend_template(close)
    bo, bo_txt = _breakout_signal(close, high)

    # Hard-ish filters (Minervini/O'Neil like)
    rs_ok = rs is not None and rs >= 8.0          # positive medium-term RS
    vol_ok = vol_ratio is not None and vol_ratio >= 1.2

    score = 40.0
    reasons = []

    if trend_ok:
        score += 20
        reasons.append(f"Trend OK ({trend_txt})")
    else:
        score -= 5
        reasons.append(f"Trend weak ({trend_txt})")

    if rs is not None:
        if rs >= 20:
            score += 15
            reasons.append(f"Strong RS {rs:.0f}%")
        elif rs >= 8:
            score += 8
            reasons.append(f"RS {rs:.0f}%")
        else:
            score -= 8
            reasons.append(f"Weak RS {rs:.0f}%")

    if bo:
        score += 15
        reasons.append(bo_txt)
    else:
        reasons.append(bo_txt)

    if vol_ok:
        score += 10
        reasons.append(f"Vol x{vol_ratio:.1f}")
    elif vol_ratio is not None:
        reasons.append(f"Vol x{vol_ratio:.1f}")

    # Liquidity
    avg_vol = stock.get("avg_volume") or 0
    if avg_vol and avg_vol < 50000:
        return None

    # Action logic: require trend + (breakout or strong RS) for BUY
    if trend_ok and bo and (rs_ok or vol_ok) and score >= 70:
        action = "🟢 BUY NOW"
        reason = "Breakout + trend + RS/volume confirmation"
    elif trend_ok and rs_ok and score >= 60:
        action = "🟡 WAIT"
        reason = "Trend/RS OK – waiting for volume breakout"
    elif score >= 50:
        action = "⚪ WATCHLIST"
        reason = "Setup forming – not confirmed"
    else:
        action = "🔴 AVOID"
        reason = "Fails Minervini/O'Neil template"

    reason = reason + " | " + "; ".join(reasons[:3])

    return MOIdea(
        symbol=symbol,
        name=name,
        action=action,
        reason=reason,
        score=round(min(score, 99), 1),
        rs=round(rs, 1) if rs is not None else None,
        vol_ratio=round(vol_ratio, 2) if vol_ratio is not None else None,
        above_ma=trend_ok,
        breakout=bo,
        market_cap_cr=mcap,
        bucket=market_cap_bucket(mcap),
    )


def run_minervini_oneil() -> Dict[str, Any]:
    ideas: List[MOIdea] = []
    for item in MO_UNIVERSE:
        yahoo = item["symbol"] + ".NS"
        fund = fetch_basic_fundamentals(yahoo)
        fund["name"] = item["name"]
        fund["_prices"] = fetch_price_history(yahoo, period="1y")
        idea = _score_mo(fund)
        if idea:
            ideas.append(idea)

    # Prefer actionable first
    rank = {"🟢 BUY NOW": 0, "🟡 WAIT": 1, "⚪ WATCHLIST": 2, "🔴 AVOID": 3}
    ideas.sort(key=lambda x: (rank.get(x.action, 9), -x.score))

    return {
        "scan_time": datetime.now(),
        "ideas": ideas,
        "rules": [
            "Price in uptrend (above 50 & 150 DMA, MAs stacked)",
            "Relative strength positive vs own history",
            "Breakout above recent pivot / base high",
            "Volume expansion on interest (prefer >1.2x avg)",
            "Cut losers fast; swing hold days–weeks",
        ],
    }


def format_mo_telegram(result: Dict[str, Any]) -> str:
    now = result["scan_time"].strftime("%d %b %Y | %H:%M IST")
    lines = [
        "<b>📈 Minervini/O’Neil Strategy</b>",
        f"{now}",
        "",
        "<i>Swing process inspired by Minervini VCP/trend template & O’Neil breakout+RS.</i>",
        "<i>Not affiliated with Minervini or O’Neil. Not investment advice.</i>",
        "",
        "<b>Rules applied</b>",
    ]
    for r in result["rules"]:
        lines.append(f"• {r}")
    lines.append("")

    ideas: List[MOIdea] = result.get("ideas") or []
    buys = [i for i in ideas if i.action.startswith("🟢")]
    waits = [i for i in ideas if i.action.startswith("🟡")]
    watch = [i for i in ideas if i.action.startswith("⚪")]

    lines.append("<b>🟢 BUY NOW (breakout confirmed)</b>")
    if buys:
        for i in buys[:8]:
            rs = f"RS {i.rs:.0f}%" if i.rs is not None else ""
            vr = f"Vol x{i.vol_ratio:.1f}" if i.vol_ratio is not None else ""
            meta = " · ".join(x for x in [rs, vr] if x)
            lines.append(f"• <b>{i.symbol}</b> – {i.reason}" + (f" ({meta})" if meta else ""))
    else:
        lines.append("• No confirmed breakouts today")
    lines.append("")

    if waits:
        lines.append("<b>🟡 WAIT (trend OK, need breakout/volume)</b>")
        for i in waits[:6]:
            lines.append(f"• <b>{i.symbol}</b> – {i.reason}")
        lines.append("")

    if watch:
        lines.append("<b>⚪ WATCHLIST</b>")
        for i in watch[:5]:
            lines.append(f"• {i.symbol} – {i.reason}")
        lines.append("")

    lines.append("<i>Use stop-loss below pattern/pivot. StockScorecard – Minervini/O’Neil sleeve</i>")
    return "\n".join(lines)
