"""
Big Money Flow – where institutions appear to be putting money.

Sources (best-effort, free / account-based):
  1) Screener.in shareholding (FII / DII / Promoter) when
     SCREENER_EMAIL + SCREENER_PASSWORD (or SCREENER_USERNAME) are set
  2) Public NSE bulk-deal style pages when reachable
  3) Existing FII/DII market + sector FPI (already in system) as context

Screener has NO official public API – we use session login + HTML tables
politely (low volume, delays). Fail soft if credentials missing or site blocks.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import logging
import os
import re
import time

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Liquid / institutional focus names for shareholding delta
WATCHLIST = [
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "BHARTIARTL",
    "ITC", "LT", "AXISBANK", "KOTAKBANK", "BAJFINANCE", "MARUTI", "SUNPHARMA",
    "TATASTEEL", "JSWSTEEL", "NTPC", "POWERGRID", "ULTRACEMCO", "ASIANPAINT",
    "TITAN", "ADANIENT", "HAL", "BEL", "DIVISLAB", "LAURUSLABS", "HCLTECH",
    "WIPRO", "TECHM", "ONGC", "COALINDIA", "M&M", "TATAMOTORS", "TMPV",
]


@dataclass
class HoldingMove:
    symbol: str
    fii_now: Optional[float]
    fii_prev: Optional[float]
    dii_now: Optional[float]
    dii_prev: Optional[float]
    promoter_now: Optional[float]
    fii_delta: Optional[float]
    dii_delta: Optional[float]
    signal: str  # ACCUMULATION / DISTRIBUTION / MIXED / FLAT
    note: str


def _creds() -> Tuple[str, str]:
    user = (
        os.getenv("SCREENER_EMAIL")
        or os.getenv("SCREENER_USERNAME")
        or os.getenv("SCREENER_USER")
        or ""
    ).strip()
    pwd = (os.getenv("SCREENER_PASSWORD") or os.getenv("SCREENER_PASS") or "").strip()
    return user, pwd


def _session_login() -> Optional[requests.Session]:
    user, pwd = _creds()
    if not user or not pwd:
        logger.info("Screener credentials not set – shareholding scrape skipped")
        return None
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (compatible; StockScorecard/1.0; +research; polite)"
        ),
        "Accept": "text/html,application/xhtml+xml",
    })
    try:
        r = s.get("https://www.screener.in/login/", timeout=25)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        csrf = None
        for inp in soup.find_all("input"):
            if (inp.get("name") or "") == "csrfmiddlewaretoken":
                csrf = inp.get("value")
                break
        if not csrf:
            logger.warning("Screener login: no csrf token")
            return None
        payload = {
            "csrfmiddlewaretoken": csrf,
            "username": user,
            "password": pwd,
        }
        r2 = s.post(
            "https://www.screener.in/login/",
            data=payload,
            headers={"Referer": "https://www.screener.in/login/"},
            timeout=25,
            allow_redirects=True,
        )
        if r2.status_code >= 400:
            logger.warning("Screener login HTTP %s", r2.status_code)
            return None
        # crude success check
        if "logout" not in r2.text.lower() and "login" in r2.url.lower():
            logger.warning("Screener login may have failed (still on login)")
            # still return session – some pages work anonymously
        return s
    except Exception as e:
        logger.warning("Screener login error: %s", e)
        return None


def _parse_pct(text: str) -> Optional[float]:
    t = (text or "").strip().replace("%", "").replace(",", "")
    if not t or t in ("-", "—", "NA"):
        return None
    try:
        return float(t)
    except Exception:
        return None


def _shareholding_from_html(html: str, symbol: str) -> Optional[HoldingMove]:
    """
    Parse Screener shareholding table: look for FIIs, DIIs, Promoters rows
    with latest two quarter columns.
    """
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    fii_vals: List[float] = []
    dii_vals: List[float] = []
    prom_vals: List[float] = []

    for table in tables:
        text = table.get_text(" ", strip=True).lower()
        if "promoter" not in text and "fii" not in text and "dii" not in text:
            continue
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 3:
                continue
            label = cells[0].lower()
            nums = [_parse_pct(c) for c in cells[1:]]
            nums = [n for n in nums if n is not None]
            if not nums:
                continue
            if "promoter" in label and "pledge" not in label:
                prom_vals = nums
            elif "fii" in label or "foreign" in label:
                fii_vals = nums
            elif "dii" in label or "domestic" in label:
                dii_vals = nums

    if not fii_vals and not dii_vals:
        return None

    # Screener often lists oldest → newest or newest → oldest; take last two as "prev, now"
    def delta(vals: List[float]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        if not vals:
            return None, None, None
        if len(vals) == 1:
            return vals[0], None, None
        # assume last is latest
        now, prev = vals[-1], vals[-2]
        return now, prev, now - prev

    fii_now, fii_prev, fii_d = delta(fii_vals)
    dii_now, dii_prev, dii_d = delta(dii_vals)
    prom_now = prom_vals[-1] if prom_vals else None

    signal = "FLAT"
    notes = []
    if fii_d is not None and fii_d >= 0.5:
        notes.append(f"FII +{fii_d:.1f}%")
    if fii_d is not None and fii_d <= -0.5:
        notes.append(f"FII {fii_d:.1f}%")
    if dii_d is not None and dii_d >= 0.5:
        notes.append(f"DII +{dii_d:.1f}%")
    if dii_d is not None and dii_d <= -0.5:
        notes.append(f"DII {dii_d:.1f}%")

    buy = (fii_d or 0) >= 0.4 or (dii_d or 0) >= 0.4
    sell = (fii_d or 0) <= -0.4 or (dii_d or 0) <= -0.4
    if buy and not sell:
        signal = "ACCUMULATION"
    elif sell and not buy:
        signal = "DISTRIBUTION"
    elif buy and sell:
        signal = "MIXED"
    else:
        signal = "FLAT"

    return HoldingMove(
        symbol=symbol,
        fii_now=fii_now,
        fii_prev=fii_prev,
        dii_now=dii_now,
        dii_prev=dii_prev,
        promoter_now=prom_now,
        fii_delta=fii_d,
        dii_delta=dii_d,
        signal=signal,
        note="; ".join(notes) if notes else "no material QoQ change",
    )


def fetch_shareholding_moves(
    symbols: Optional[List[str]] = None,
    delay_sec: float = 1.2,
    limit: int = 25,
) -> List[HoldingMove]:
    symbols = (symbols or WATCHLIST)[:limit]
    session = _session_login()
    if session is None:
        # anonymous session still tries public pages
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; StockScorecard/1.0)",
        })

    out: List[HoldingMove] = []
    for i, sym in enumerate(symbols):
        url = f"https://www.screener.in/company/{sym}/consolidated/"
        try:
            r = session.get(url, timeout=25)
            if r.status_code != 200:
                # try without consolidated
                r = session.get(f"https://www.screener.in/company/{sym}/", timeout=25)
            if r.status_code != 200:
                logger.debug("screener %s HTTP %s", sym, r.status_code)
                continue
            move = _shareholding_from_html(r.text, sym)
            if move:
                out.append(move)
        except Exception as e:
            logger.debug("screener %s: %s", sym, e)
        if i < len(symbols) - 1:
            time.sleep(delay_sec)
    return out


def fetch_nse_bulk_deals_hint() -> List[str]:
    """
    Best-effort public bulk deal headlines (may break if NSE blocks bots).
    Returns short human lines.
    """
    lines: List[str] = []
    urls = [
        "https://www.nseindia.com/api/snapshot-capital-market-largedeals",
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://www.nseindia.com/",
    }
    try:
        s = requests.Session()
        s.headers.update(headers)
        # warm-up cookie
        s.get("https://www.nseindia.com/", timeout=15)
        for url in urls:
            r = s.get(url, timeout=20)
            if not r.ok:
                continue
            data = r.json()
            # structure varies – try common keys
            rows = data if isinstance(data, list) else data.get("data") or data.get("bulkdeals") or []
            if isinstance(rows, dict):
                rows = rows.get("data") or []
            for row in (rows or [])[:8]:
                if not isinstance(row, dict):
                    continue
                sym = row.get("symbol") or row.get("sm_name") or row.get("BD_SYMBOL") or ""
                client = row.get("clientName") or row.get("BD_CLIENT_NAME") or ""
                qty = row.get("qty") or row.get("BD_QTY_TRD") or ""
                typ = row.get("buySell") or row.get("BD_BUY_SELL") or ""
                if sym:
                    lines.append(f"{sym} · {typ} · {client[:40]} · qty {qty}")
    except Exception as e:
        logger.debug("NSE bulk deals: %s", e)
    return lines


def run_big_money_flow() -> Dict[str, Any]:
    moves = fetch_shareholding_moves()
    accum = [m for m in moves if m.signal == "ACCUMULATION"]
    distrib = [m for m in moves if m.signal == "DISTRIBUTION"]
    mixed = [m for m in moves if m.signal == "MIXED"]

    # rank by absolute institutional delta
    def strength(m: HoldingMove) -> float:
        return abs(m.fii_delta or 0) + abs(m.dii_delta or 0)

    accum.sort(key=strength, reverse=True)
    distrib.sort(key=strength, reverse=True)

    bulk = fetch_nse_bulk_deals_hint()

    # market-level context from existing module
    mkt_lines: List[str] = []
    try:
        from src.shared.fii_dii import fetch_fii_dii, format_fii_dii_section
        snap = fetch_fii_dii()
        mkt_lines = format_fii_dii_section(snap) if snap else []
    except Exception as e:
        logger.debug("fii context: %s", e)

    return {
        "scan_time": datetime.now(),
        "credentials_present": bool(_creds()[0] and _creds()[1]),
        "moves": moves,
        "accumulation": accum[:10],
        "distribution": distrib[:10],
        "mixed": mixed[:5],
        "bulk_deals": bulk,
        "market_fii_dii": mkt_lines,
    }


def format_big_money_telegram(result: Optional[Dict[str, Any]] = None) -> str:
    if result is None:
        result = run_big_money_flow()
    now = result["scan_time"].strftime("%d %b %Y | %H:%M IST")
    cred = result.get("credentials_present")

    lines = [
        "<b>💰 BIG MONEY FLOW</b>",
        now,
        "",
        "<i>Where institutions appear to be adding / reducing (shareholding QoQ)</i>",
        f"<i>Screener login: {'configured' if cred else 'NOT set – public pages only'}</i>",
        "",
    ]

    if result.get("market_fii_dii"):
        lines.append("<b>MARKET FII / DII (cash)</b>")
        # already may contain HTML-ish bullets
        for ln in result["market_fii_dii"][:6]:
            lines.append(ln if ln.startswith("•") or ln.startswith("<") else f"• {ln}")
        lines.append("")

    lines.append("<b>🟢 INSTITUTIONAL ACCUMULATION (QoQ)</b>")
    acc = result.get("accumulation") or []
    if not acc:
        lines.append("• No clear accumulation in scanned set (or data unavailable)")
    else:
        for m in acc:
            lines.append(
                f"• <b>{m.symbol}</b> – {m.note}"
                f"{f' · FII {m.fii_now:.1f}%' if m.fii_now is not None else ''}"
                f"{f' · DII {m.dii_now:.1f}%' if m.dii_now is not None else ''}"
            )

    lines.append("")
    lines.append("<b>🔴 INSTITUTIONAL DISTRIBUTION (QoQ)</b>")
    dist = result.get("distribution") or []
    if not dist:
        lines.append("• No clear distribution in scanned set")
    else:
        for m in dist:
            lines.append(f"• <b>{m.symbol}</b> – {m.note}")

    bulk = result.get("bulk_deals") or []
    if bulk:
        lines.append("")
        lines.append("<b>📦 BULK / LARGE DEALS (if available)</b>")
        for b in bulk[:8]:
            lines.append(f"• {b}")

    lines.append("")
    lines.append(
        "<i>Shareholding is usually quarterly (lagging). Not the same as same-day FII flash. "
        "Not investment advice. StockScorecard</i>"
    )
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3900] + "\n\n… (truncated)"
    return text
