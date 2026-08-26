"""
Multi-month Sector Strength / Rotation.

Ranks NSE sector indices on 1M / 3M / 6M returns vs Nifty 50,
labels Leading / Improving / Soft / Lagging, maps to StockScorecard
sector keys, and posts one clear Telegram list.

Complements:
  - Sectorial-RRG (Streamlit visual RRG dashboard)
  - Hot Stocks (stock-level multi-month)
  - FII/DII sector FPI (institutional allocation when available)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Yahoo symbols for major NSE sector / thematic indices
SECTOR_INDICES: List[Tuple[str, str, str]] = [
    # (display_name, yfinance_ticker, stockscorecard_sector_key)
    ("Nifty Bank", "^NSEBANK", "banks_financials"),
    ("Nifty IT", "^CNXIT", "information_technology"),
    ("Nifty Pharma", "^CNXPHARMA", "pharmaceuticals"),
    ("Nifty Auto", "^CNXAUTO", "automobile_ev"),
    ("Nifty Metal", "^CNXMETAL", "metals_mining"),
    ("Nifty FMCG", "^CNXFMCG", "fmcg"),
    ("Nifty Realty", "^CNXREALTY", "realty"),
    ("Nifty Energy", "^CNXENERGY", "energy_oil_gas_power"),
    ("Nifty Media", "^CNXMEDIA", "media"),
    ("Nifty PSU Bank", "^CNXPSUBANK", "banks_financials"),
    ("Nifty Infra", "^CNXINFRA", "capital_goods_infra"),
    ("Nifty PSE", "^CNXPSE", "capital_goods_infra"),
]

BENCHMARK = ("Nifty 50", "^NSEI")


@dataclass
class SectorStrength:
    name: str
    yf_ticker: str
    ss_sector: str
    ret_1m: Optional[float]
    ret_3m: Optional[float]
    ret_6m: Optional[float]
    rel_1m: Optional[float]  # vs Nifty
    rel_3m: Optional[float]
    rel_6m: Optional[float]
    label: str  # Leading / Improving / Soft / Lagging
    score: float
    note: str


def _ret(close, days: int) -> Optional[float]:
    if close is None or len(close) <= days:
        return None
    past = float(close.iloc[-days - 1])
    if past <= 0:
        return None
    return (float(close.iloc[-1]) / past - 1.0) * 100.0


def _fetch_close(ticker: str):
    try:
        import yfinance as yf
        df = yf.Ticker(ticker).history(period="1y")
        if df is None or len(df) < 30:
            return None
        return df["Close"].astype(float)
    except Exception as e:
        logger.debug("sector price %s: %s", ticker, e)
        return None


def _label(rel_1m: Optional[float], rel_3m: Optional[float], rel_6m: Optional[float]) -> Tuple[str, float, str]:
    """
    Multi-month focused label.
    Score blends 6M (weight high) + 3M + 1M relative to Nifty.
    """
    r6 = rel_6m if rel_6m is not None else 0.0
    r3 = rel_3m if rel_3m is not None else 0.0
    r1 = rel_1m if rel_1m is not None else 0.0
    score = 0.5 * r6 + 0.3 * r3 + 0.2 * r1

    if r6 >= 5 and r3 >= 0 and r1 >= -1:
        return "🟢 Leading", score, "Strong multi-month vs Nifty — prefer setups here"
    if r6 >= 0 and (r1 >= 2 or r3 >= 3):
        return "🔵 Improving", score, "Multi-month OK + recent relative strength (Bank-like RRG improve)"
    if r6 >= 2 and r1 < -2:
        return "🟡 Softening", score, "Still ok on 6M but short-term cooling — selective"
    if r6 < -3 or (r6 < 0 and r3 < -2):
        return "🔴 Lagging", score, "Weak multi-month vs Nifty — lower priority"
    return "⚪ Neutral", score, "Mixed vs benchmark"


def run_sector_rotation() -> Dict[str, Any]:
    bench_close = _fetch_close(BENCHMARK[1])
    b1 = _ret(bench_close, 21) if bench_close is not None else None
    b3 = _ret(bench_close, 63) if bench_close is not None else None
    b6 = _ret(bench_close, 126) if bench_close is not None else None

    rows: List[SectorStrength] = []
    for name, yf_t, ss in SECTOR_INDICES:
        close = _fetch_close(yf_t)
        if close is None:
            continue
        r1, r3, r6 = _ret(close, 21), _ret(close, 63), _ret(close, 126)
        rel1 = (r1 - b1) if (r1 is not None and b1 is not None) else r1
        rel3 = (r3 - b3) if (r3 is not None and b3 is not None) else r3
        rel6 = (r6 - b6) if (r6 is not None and b6 is not None) else r6
        label, score, note = _label(rel1, rel3, rel6)
        rows.append(
            SectorStrength(
                name=name,
                yf_ticker=yf_t,
                ss_sector=ss,
                ret_1m=r1,
                ret_3m=r3,
                ret_6m=r6,
                rel_1m=rel1,
                rel_3m=rel3,
                rel_6m=rel6,
                label=label,
                score=score,
                note=note,
            )
        )

    rows.sort(key=lambda x: -x.score)
    return {
        "scan_time": datetime.now(),
        "benchmark": {
            "name": BENCHMARK[0],
            "ret_1m": b1,
            "ret_3m": b3,
            "ret_6m": b6,
        },
        "sectors": rows,
    }


def format_sector_rotation_telegram(result: Optional[Dict[str, Any]] = None) -> str:
    if result is None:
        result = run_sector_rotation()
    now = result["scan_time"].strftime("%d %b %Y | %H:%M IST")
    b = result.get("benchmark") or {}
    sectors: List[SectorStrength] = result.get("sectors") or []

    def pct(x: Optional[float]) -> str:
        if x is None:
            return "—"
        return f"{x:+.1f}%"

    lines = [
        "<b>📊 SECTOR ROTATION</b> – multi-month strength",
        now,
        "",
        f"<i>Benchmark {b.get('name', 'Nifty')}: "
        f"1M {pct(b.get('ret_1m'))} · 3M {pct(b.get('ret_3m'))} · 6M {pct(b.get('ret_6m'))}</i>",
        "<i>Sectors ranked by relative multi-month score vs Nifty.</i>",
        "",
    ]

    leading = [s for s in sectors if s.label.startswith("🟢")]
    improving = [s for s in sectors if s.label.startswith("🔵")]
    soft = [s for s in sectors if s.label.startswith("🟡")]
    lagging = [s for s in sectors if s.label.startswith("🔴")]

    def block(title: str, items: List[SectorStrength], n: int = 6):
        lines.append(f"<b>{title}</b>")
        if not items:
            lines.append("• —")
        else:
            for s in items[:n]:
                lines.append(
                    f"• <b>{s.name}</b> → {s.ss_sector}\n"
                    f"  Abs 1M {pct(s.ret_1m)} · 3M {pct(s.ret_3m)} · 6M {pct(s.ret_6m)}\n"
                    f"  vs Nifty 1M {pct(s.rel_1m)} · 6M {pct(s.rel_6m)}\n"
                    f"  {s.note}"
                )
        lines.append("")

    block("🟢 Leading (strong multi-month)", leading)
    block("🔵 Improving (RRG-style rising)", improving)
    block("🟡 Softening", soft, 4)
    block("🔴 Lagging (de-prioritise)", lagging, 4)

    # Action map for StockScorecard
    prefer = [s.ss_sector for s in (leading + improving)[:5]]
    prefer = list(dict.fromkeys(prefer))
    if prefer:
        lines.append("<b>✅ Prefer these StockScorecard sectors</b>")
        for p in prefer:
            lines.append(f"• {p}")
        lines.append("")

    lines.append(
        "<i>Use with Fresh Buys / Horizon inside these sectors. "
        "Visual RRG: Sectorial-RRG app. StockScorecard</i>"
    )
    return "\n".join(lines)
