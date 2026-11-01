"""
Context Intelligence Layer
Sources inspired by research list (Pulse/ET/Trendlyne-style news + PIB policy + sector tags).

Practical approach (GitHub Actions friendly):
  - Google News RSS queries (same pattern as news_layer) — no paid APIs
  - PIB / policy / macro keyword buckets
  - Sector bias summary for swing context

Does NOT scrape all 29 research sites (ToS / blocks). Curated free feeds only.
"""

from __future__ import annotations

from src.shared.time_ist import format_ist, now_ist

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET
import logging
import re
import requests

logger = logging.getLogger(__name__)

# Research-menu → free RSS proxies
CONTEXT_FEEDS: List[Tuple[str, str]] = [
    (
        "Market news",
        "https://news.google.com/rss/search?q=India+stock+market+Nifty+Sensex+OR+FII&hl=en-IN&gl=IN&ceid=IN:en",
    ),
    (
        "Zerodha Pulse style",
        "https://news.google.com/rss/search?q=site:pulse.zerodha.com+OR+site:zerodha.com%2Fpulse+(market+OR+Nifty)&hl=en-IN&gl=IN&ceid=IN:en",
    ),
    (
        "PIB policy",
        "https://news.google.com/rss/search?q=site:pib.gov.in+(finance+OR+tax+OR+PLI+OR+RBI+OR+export+OR+defence+OR+pharma)&hl=en-IN&gl=IN&ceid=IN:en",
    ),
    (
        "Sector / industry",
        "https://news.google.com/rss/search?q=India+(pharma+FDA+OR+defence+order+OR+EV+OR+banking+NPA+OR+metal+OR+IT+spending)&hl=en-IN&gl=IN&ceid=IN:en",
    ),
    (
        "Trendlyne / ET mix",
        "https://news.google.com/rss/search?q=(site:trendlyne.com+OR+site:economictimes.indiatimes.com)+(stocks+OR+results+OR+order)&hl=en-IN&gl=IN&ceid=IN:en",
    ),
]

SECTOR_KEYWORDS: List[Tuple[str, List[str]]] = [
    ("pharmaceuticals", [r"\bpharma\b", r"\bfda\b", r"\bdrug\b", r"\busfda\b", r"\bapi\b"]),
    ("defence_aerospace", [r"\bdefence\b", r"\bdefense\b", r"\baerospace\b", r"\bhal\b", r"\bdrone\b", r"\border\b"]),
    ("banks_financials", [r"\bbank\b", r"\bnpa\b", r"\brbi\b", r"\bcredit\b", r"\bfi\b"]),
    ("information_technology", [r"\bit\b", r"\bsoftware\b", r"\btech\b", r"\binfosys\b", r"\btcs\b"]),
    ("automobile_ev", [r"\bev\b", r"\belectric vehicle\b", r"\bauto\b", r"\bautomobile\b"]),
    ("metals_mining", [r"\bsteel\b", r"\bmetal\b", r"\bcopper\b", r"\bzinc\b", r"\bmining\b"]),
    ("energy_oil_gas_power", [r"\bcrude\b", r"\boil\b", r"\bgas\b", r"\bpower\b", r"\brenewable\b"]),
    ("capital_goods_infra", [r"\binfra\b", r"\bcapex\b", r"\bpli\b", r"\bmanufacturing\b", r"\bcapacity\b"]),
    ("realty", [r"\breal estate\b", r"\bhousing\b", r"\brealty\b"]),
    ("telecom", [r"\btelecom\b", r"\b5g\b", r"\bspectrum\b", r"\bjio\b"]),
    ("fmcg", [r"\bfmcg\b", r"\bconsumer\b"]),
]

POLICY_PATTERNS = [
    (r"\bbudget\b", "Budget/fiscal"),
    (r"\bpli\b", "PLI / manufacturing"),
    (r"\bgst\b", "GST"),
    (r"\brbi\b|\brepo\b|\bmpc\b", "RBI / rates"),
    (r"\bsebi\b", "SEBI"),
    (r"\bexport\b|\bduty\b|\btariff\b", "Trade / duty"),
    (r"\bdefence\b.*\border\b|\border\b.*\bdefence\b", "Defence orders"),
]


@dataclass
class ContextItem:
    title: str
    source: str
    link: str
    sectors: List[str]
    policy_tags: List[str]


def _fetch_rss(url: str, source: str, limit: int = 8) -> List[ContextItem]:
    out: List[ContextItem] = []
    try:
        r = requests.get(
            url,
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0 StockScorecardContext/1.0"},
        )
        if not r.ok:
            return out
        root = ET.fromstring(r.content)
        for item in root.iter("item"):
            title_el = item.find("title")
            link_el = item.find("link")
            title = (title_el.text or "").strip() if title_el is not None else ""
            link = (link_el.text or "").strip() if link_el is not None else ""
            if not title:
                continue
            low = title.lower()
            sectors = []
            for sec, pats in SECTOR_KEYWORDS:
                if any(re.search(p, low) for p in pats):
                    sectors.append(sec)
            policy = []
            for pat, tag in POLICY_PATTERNS:
                if re.search(pat, low):
                    policy.append(tag)
            out.append(
                ContextItem(
                    title=title[:180],
                    source=source,
                    link=link,
                    sectors=sectors,
                    policy_tags=policy,
                )
            )
            if len(out) >= limit:
                break
    except Exception as e:
        logger.warning("context feed %s: %s", source, e)
    return out


def run_context_intelligence() -> Dict[str, Any]:
    items: List[ContextItem] = []
    seen = set()
    for source, url in CONTEXT_FEEDS:
        for it in _fetch_rss(url, source):
            key = re.sub(r"\W+", "", it.title.lower())[:80]
            if key in seen:
                continue
            seen.add(key)
            items.append(it)

    sector_hits: Dict[str, int] = {}
    policy_hits: Dict[str, int] = {}
    for it in items:
        for s in it.sectors:
            sector_hits[s] = sector_hits.get(s, 0) + 1
        for p in it.policy_tags:
            policy_hits[p] = policy_hits.get(p, 0) + 1

    top_sectors = sorted(sector_hits.items(), key=lambda x: -x[1])[:6]
    top_policy = sorted(policy_hits.items(), key=lambda x: -x[1])[:6]

    # Simple tone
    bullish = sum(
        1
        for it in items
        if re.search(r"surge|rally|record|growth|order win|upgrade", it.title, re.I)
    )
    bearish = sum(
        1
        for it in items
        if re.search(r"crash|fall|scam|ban|probe|weak|cut rate|selloff", it.title, re.I)
    )
    if bullish > bearish + 2:
        tone = "Constructive news flow"
    elif bearish > bullish + 2:
        tone = "Cautious news flow"
    else:
        tone = "Mixed / neutral"

    return {
        "scan_time": now_ist(),
        "items": items[:20],
        "sector_hits": top_sectors,
        "policy_hits": top_policy,
        "tone": tone,
        "bullish_n": bullish,
        "bearish_n": bearish,
    }


def format_context_intelligence_telegram(
    result: Optional[Dict[str, Any]] = None,
) -> str:
    if result is None:
        result = run_context_intelligence()
    now = format_ist(result.get("scan_time"))
    lines = [
        "<b>📰 CONTEXT INTELLIGENCE</b>",
        now,
        f"<i>Tone: {result.get('tone')} · "
        f"bullish-ish {result.get('bullish_n', 0)} / cautious-ish {result.get('bearish_n', 0)}</i>",
        "",
        "<b>📌 POLICY / MACRO TAGS</b>",
    ]
    pol = result.get("policy_hits") or []
    if not pol:
        lines.append("• —")
    else:
        for tag, n in pol:
            lines.append(f"• {tag} ({n})")

    lines.append("")
    lines.append("<b>🏭 SECTOR ATTENTION</b>")
    sec = result.get("sector_hits") or []
    if not sec:
        lines.append("• —")
    else:
        for s, n in sec:
            lines.append(f"• {s.replace('_', ' ')} ({n})")

    lines.append("")
    lines.append("<b>Headlines</b>")
    items: List[ContextItem] = result.get("items") or []
    if not items:
        lines.append("• No headlines fetched (network/RSS)")
    else:
        for it in items[:10]:
            tag = ""
            if it.sectors:
                tag = f" [{it.sectors[0][:12]}]"
            lines.append(f"• {it.title[:120]}{tag}")

    lines.append("")
    lines.append(
        "<i>Sources: free news RSS (Pulse/ET/Trendlyne/PIB-style queries). "
        "Context only — combine with price action. Not advice. StockScorecard</i>"
    )
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3900] + "\n\n… (truncated)"
    return text
