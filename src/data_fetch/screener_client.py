"""
Shared Screener.in client (session login + company page parse).

No official API – polite HTML fetch. Credentials from env:
  SCREENER_EMAIL / SCREENER_USERNAME + SCREENER_PASSWORD
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import logging
import os
import re
import time

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def screener_creds() -> Tuple[str, str]:
    user = (
        os.getenv("SCREENER_EMAIL")
        or os.getenv("SCREENER_USERNAME")
        or os.getenv("SCREENER_USER")
        or ""
    ).strip()
    pwd = (os.getenv("SCREENER_PASSWORD") or os.getenv("SCREENER_PASS") or "").strip()
    return user, pwd


def make_session() -> requests.Session:
    user, pwd = screener_creds()
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; StockScorecard/1.1; +research)",
        "Accept": "text/html,application/xhtml+xml",
    })
    if not user or not pwd:
        return s
    try:
        r = s.get("https://www.screener.in/login/", timeout=25)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        csrf = None
        for inp in soup.find_all("input"):
            if inp.get("name") == "csrfmiddlewaretoken":
                csrf = inp.get("value")
                break
        if csrf:
            s.post(
                "https://www.screener.in/login/",
                data={
                    "csrfmiddlewaretoken": csrf,
                    "username": user,
                    "password": pwd,
                },
                headers={"Referer": "https://www.screener.in/login/"},
                timeout=25,
                allow_redirects=True,
            )
    except Exception as e:
        logger.warning("Screener login: %s", e)
    return s


def _num(text: str) -> Optional[float]:
    t = (text or "").strip().replace(",", "").replace("%", "").replace("₹", "")
    t = re.sub(r"[^\d.\-]", "", t)
    if not t or t in (".", "-"):
        return None
    try:
        return float(t)
    except Exception:
        return None


@dataclass
class ScreenerSnapshot:
    symbol: str
    market_cap: Optional[str] = None
    pe: Optional[float] = None
    roe: Optional[float] = None
    roce: Optional[float] = None
    debt_to_equity: Optional[float] = None
    sales_growth_qoq: Optional[float] = None
    profit_growth_qoq: Optional[float] = None
    sales_growth_yoy: Optional[float] = None
    profit_growth_yoy: Optional[float] = None
    promoter_pct: Optional[float] = None
    pledge_pct: Optional[float] = None
    fii_pct: Optional[float] = None
    dii_pct: Optional[float] = None
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)
    peers: List[str] = field(default_factory=list)
    raw_ratios: Dict[str, str] = field(default_factory=dict)
    ok: bool = False
    error: Optional[str] = None


def _parse_top_ratios(soup: BeautifulSoup, snap: ScreenerSnapshot) -> None:
    # Screener top ratios often in li or #top-ratios
    for box in soup.select("#top-ratios li, .company-ratios li, li"):
        text = box.get_text(" ", strip=True)
        if not text or ":" not in text and "  " not in text:
            # format "Market Cap ₹ 1,234 Cr." sometimes name + value spans
            pass
        low = text.lower()
        val = _num(text.split()[-1]) if text.split() else None
        # paired spans
        spans = box.find_all(["span", "a"])
        if len(spans) >= 2:
            name = spans[0].get_text(strip=True).lower()
            val = _num(spans[-1].get_text(strip=True))
            snap.raw_ratios[name] = spans[-1].get_text(strip=True)
            if "market cap" in name:
                snap.market_cap = spans[-1].get_text(strip=True)
            elif name in ("stock p/e", "p/e", "pe"):
                snap.pe = val
            elif "roe" in name:
                snap.roe = val
            elif "roce" in name:
                snap.roce = val
            elif "debt to equity" in name or "debt/equity" in name:
                snap.debt_to_equity = val
            elif "promoter holding" in name:
                snap.promoter_pct = val
            elif "pledged" in name:
                snap.pledge_pct = val


def _parse_quarters(soup: BeautifulSoup, snap: ScreenerSnapshot) -> None:
    """Best-effort QoQ from quarterly results table (last two cols)."""
    for table in soup.find_all("table"):
        header = table.get_text(" ", strip=True).lower()
        if "sales" not in header and "net profit" not in header:
            continue
        rows = {}
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            if len(cells) < 3:
                continue
            label = cells[0].lower()
            nums = [_num(c) for c in cells[1:]]
            nums = [n for n in nums if n is not None]
            if not nums:
                continue
            rows[label] = nums
        sales = rows.get("sales") or rows.get("revenue")
        profit = None
        for k, v in rows.items():
            if "net profit" in k or k == "profit":
                profit = v
                break
        if sales and len(sales) >= 2 and sales[-2] not in (0, None):
            try:
                snap.sales_growth_qoq = (sales[-1] / sales[-2] - 1.0) * 100.0
            except Exception:
                pass
        if profit and len(profit) >= 2 and profit[-2] not in (0, None):
            try:
                snap.profit_growth_qoq = (profit[-1] / profit[-2] - 1.0) * 100.0
            except Exception:
                pass
        # YoY if 5 columns (approx)
        if sales and len(sales) >= 5 and sales[-5] not in (0, None):
            try:
                snap.sales_growth_yoy = (sales[-1] / sales[-5] - 1.0) * 100.0
            except Exception:
                pass
        if profit and len(profit) >= 5 and profit[-5] not in (0, None):
            try:
                snap.profit_growth_yoy = (profit[-1] / profit[-5] - 1.0) * 100.0
            except Exception:
                pass
        if sales or profit:
            break


def _parse_pros_cons(soup: BeautifulSoup, snap: ScreenerSnapshot) -> None:
    for section_id, bucket in (("pros", "pros"), ("cons", "cons")):
        el = soup.find(id=section_id) or soup.find(class_=section_id)
        if not el:
            continue
        items = [li.get_text(" ", strip=True) for li in el.find_all("li")]
        items = [x for x in items if x][:5]
        if bucket == "pros":
            snap.pros = items
        else:
            snap.cons = items


def _parse_peers(soup: BeautifulSoup, snap: ScreenerSnapshot) -> None:
    peers = []
    for a in soup.select("table a, #peers a"):
        href = a.get("href") or ""
        if "/company/" in href:
            m = re.search(r"/company/([^/]+)/", href)
            if m:
                sym = m.group(1).upper()
                if sym != snap.symbol and sym not in peers:
                    peers.append(sym)
    snap.peers = peers[:8]


def fetch_company(session: requests.Session, symbol: str) -> ScreenerSnapshot:
    snap = ScreenerSnapshot(symbol=symbol.upper())
    url = f"https://www.screener.in/company/{symbol}/consolidated/"
    try:
        r = session.get(url, timeout=30)
        if r.status_code != 200:
            r = session.get(f"https://www.screener.in/company/{symbol}/", timeout=30)
        if r.status_code != 200:
            snap.error = f"HTTP {r.status_code}"
            return snap
        soup = BeautifulSoup(r.text, "html.parser")
        _parse_top_ratios(soup, snap)
        _parse_quarters(soup, snap)
        _parse_pros_cons(soup, snap)
        _parse_peers(soup, snap)
        # shareholding pledge often in table
        for tr in soup.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if not cells:
                continue
            lab = cells[0].lower()
            if "pledged" in lab and len(cells) > 1:
                snap.pledge_pct = _num(cells[-1]) or snap.pledge_pct
            if lab.startswith("promoters") and "pledged" not in lab and len(cells) > 1:
                snap.promoter_pct = _num(cells[-1]) or snap.promoter_pct
            if "fii" in lab or "foreign" in lab:
                snap.fii_pct = _num(cells[-1]) or snap.fii_pct
            if "dii" in lab or "domestic" in lab:
                snap.dii_pct = _num(cells[-1]) or snap.dii_pct
        snap.ok = True
        return snap
    except Exception as e:
        snap.error = str(e)[:120]
        return snap


def fetch_many(
    symbols: List[str],
    delay_sec: float = 1.1,
    limit: int = 20,
) -> List[ScreenerSnapshot]:
    session = make_session()
    out: List[ScreenerSnapshot] = []
    for i, sym in enumerate(symbols[:limit]):
        out.append(fetch_company(session, sym))
        if i < min(len(symbols), limit) - 1:
            time.sleep(delay_sec)
    return out
