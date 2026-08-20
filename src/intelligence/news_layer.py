"""
News Intelligence Layer
Niche: headlines that can influence stocks and the broader market.

- Pulls from free RSS sources (Google News India markets + related queries)
- Scores by market-impact keywords (policy, FII, results, RBI, crude, etc.)
- Maps simple sector tags for the report
- Output for Telegram section or standalone message
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from xml.etree import ElementTree as ET
import logging
import re
import requests

logger = logging.getLogger(__name__)

# Free RSS endpoints (Google News – no API key)
RSS_FEEDS = [
    (
        "India markets",
        "https://news.google.com/rss/search?q=India+stock+market+Nifty+Sensex&hl=en-IN&gl=IN&ceid=IN:en",
    ),
    (
        "RBI policy",
        "https://news.google.com/rss/search?q=RBI+repo+rate+OR+monetary+policy+India&hl=en-IN&gl=IN&ceid=IN:en",
    ),
    (
        "FII DII flows",
        "https://news.google.com/rss/search?q=FII+DII+India+markets+foreign+investors&hl=en-IN&gl=IN&ceid=IN:en",
    ),
    (
        "Corporate results",
        "https://news.google.com/rss/search?q=India+quarterly+results+earnings+Sensex&hl=en-IN&gl=IN&ceid=IN:en",
    ),
    (
        "Sector catalysts",
        "https://news.google.com/rss/search?q=India+(pharma+FDA+OR+defence+order+OR+EV+OR+banking+NPA+OR+IT+deal)&hl=en-IN&gl=IN&ceid=IN:en",
    ),
]

# Keyword weights – higher = more market-moving
IMPACT_KEYWORDS: List[Tuple[str, int]] = [
    (r"\brbi\b", 5),
    (r"\brepo rate\b", 5),
    (r"\bmpc\b", 4),
    (r"\bfii\b|\bfpi\b", 4),
    (r"\bdii\b", 3),
    (r"\bsebi\b", 4),
    (r"\bbudget\b|\bfinance bill\b", 5),
    (r"\bcrude\b|\boil price\b", 4),
    (r"\busd\b|\brupee\b|\bforex\b", 3),
    (r"\bfed\b|\brate cut\b|\brate hike\b", 4),
    (r"\bearnings\b|\bresults\b|\bprofit\b|\brevenue\b", 3),
    (r"\bfda\b|\bwarning letter\b|\busfda\b", 5),
    (r"\border win\b|\bcontract\b|\bdefence order\b", 4),
    (r"\bip o\b|\blisting\b", 2),
    (r"\bmerger\b|\bacquisition\b|\btakeover\b", 4),
    (r"\bbankruptcy\b|\bdefault\b|\bfraud\b", 5),
    (r"\bnifty\b|\bsensex\b|\bmarket\b", 2),
    (r"\bgap up\b|\bgap down\b|\bcrash\b|\brally\b", 3),
    (r"\bwar\b|\bgeopolit\b|\bsanction\b", 4),
    (r"\bmonsoon\b|\binflation\b|\bgdp\b", 3),
]

SECTOR_TAGS: List[Tuple[str, str]] = [
    (r"\bpharma\b|\bfda\b|\bdrug\b", "Pharma"),
    (r"\bbank\b|\bnbfc\b|\bnpa\b", "Banks"),
    (r"\bit\b|\bsoftware\b|\binfosys\b|\btcs\b", "IT"),
    (r"\bauto\b|\bev\b|\bvehicle\b", "Auto/EV"),
    (r"\bdefence\b|\bhal\b|\bdrone\b", "Defence"),
    (r"\bmetal\b|\bsteel\b|\bcopper\b", "Metals"),
    (r"\boil\b|\bgas\b|\bcrude\b|\bongc\b", "Energy"),
    (r"\brealty\b|\bhousing\b|\bproperty\b", "Realty"),
    (r"\bfmcg\b|\bconsumer\b", "FMCG"),
    (r"\btelecom\b|\bairtel\b|\bjio\b", "Telecom"),
]


@dataclass
class NewsItem:
    title: str
    source: str
    link: str = ""
    published: str = ""
    impact_score: int = 0
    sectors: List[str] = field(default_factory=list)
    bias: str = "Neutral"  # Bullish / Bearish / Neutral


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _parse_rss(xml_text: str, feed_label: str) -> List[NewsItem]:
    items: List[NewsItem] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    # Google RSS uses channel/item
    for item in root.findall(".//item")[:15]:
        title = _strip_html((item.findtext("title") or ""))
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        if not title:
            continue
        items.append(
            NewsItem(title=title, source=feed_label, link=link, published=pub)
        )
    return items


def _score_item(item: NewsItem) -> NewsItem:
    text = item.title.lower()
    score = 0
    for pattern, w in IMPACT_KEYWORDS:
        if re.search(pattern, text, re.I):
            score += w
    sectors = []
    for pattern, tag in SECTOR_TAGS:
        if re.search(pattern, text, re.I):
            if tag not in sectors:
                sectors.append(tag)

    # Simple tone
    bear = len(re.findall(r"fall|drop|crash|sell|fraud|warning|cut|weak|slump|decline", text))
    bull = len(re.findall(r"rally|surge|jump|gain|buy|record|win|approval|boost|rise", text))
    if bull > bear + 1:
        bias = "Bullish"
    elif bear > bull + 1:
        bias = "Bearish"
    else:
        bias = "Neutral"

    item.impact_score = score
    item.sectors = sectors
    item.bias = bias
    return item


def fetch_market_news(max_items: int = 12) -> List[NewsItem]:
    """Fetch and rank market-influencing news."""
    all_items: List[NewsItem] = []
    headers = {"User-Agent": "StockScorecard/1.0 (news intelligence)"}

    for label, url in RSS_FEEDS:
        try:
            r = requests.get(url, timeout=12, headers=headers)
            if not r.ok:
                logger.warning("News feed %s HTTP %s", label, r.status_code)
                continue
            parsed = _parse_rss(r.text, label)
            all_items.extend(parsed)
        except Exception as e:
            logger.warning("News feed %s failed: %s", label, e)

    # Dedupe by normalized title
    seen = set()
    unique: List[NewsItem] = []
    for it in all_items:
        key = re.sub(r"\W+", "", it.title.lower())[:80]
        if key in seen:
            continue
        seen.add(key)
        unique.append(_score_item(it))

    unique.sort(key=lambda x: x.impact_score, reverse=True)
    # Keep items with some signal, or top headlines anyway
    strong = [u for u in unique if u.impact_score >= 3]
    if len(strong) < 5:
        strong = unique[:max_items]
    return strong[:max_items]


def format_news_section(items: Optional[List[NewsItem]] = None, cfg: Optional[dict] = None) -> List[str]:
    """Lines for embedding in daily Telegram report."""
    if items is None:
        items = fetch_market_news()

    lines = ["<b>📰 NEWS INTELLIGENCE</b> <i>(market-moving)</i>"]
    try:
        from src.intelligence.news_bias import news_scoring_status
        if cfg is None:
            import yaml
            from pathlib import Path
            cp = Path("config.yaml")
            cfg = yaml.safe_load(cp.read_text()) if cp.exists() else {}
        st = news_scoring_status(cfg or {})
        lines.append(f"<i>{st['message']}</i>")
    except Exception:
        pass
    if not items:
        lines.append("• No high-impact headlines fetched")
        lines.append("")
        return lines

    for it in items[:8]:
        bias_icon = {"Bullish": "🟢", "Bearish": "🔴", "Neutral": "⚪"}.get(it.bias, "⚪")
        sec = f" [{', '.join(it.sectors)}]" if it.sectors else ""
        # Truncate long titles
        title = it.title if len(it.title) <= 120 else it.title[:117] + "…"
        lines.append(f"• {bias_icon} {title}{sec}")

    lines.append("<i>Headlines only – not trade signals. Verify before acting.</i>")
    lines.append("")
    return lines


def format_news_telegram_message(items: Optional[List[NewsItem]] = None) -> str:
    """Standalone Telegram message for news intelligence."""
    if items is None:
        items = fetch_market_news()
    now = datetime.now().strftime("%d %b %Y | %H:%M IST")
    lines = [
        "<b>📰 News Intelligence – Market & Stocks</b>",
        now,
        "",
        "<i>Niche: news that can influence stocks and the market.</i>",
        "",
    ]
    lines.extend(format_news_section(items))
    lines.append("<i>StockScorecard – News layer</i>")
    return "\n".join(lines)
