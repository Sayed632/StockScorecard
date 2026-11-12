"""
Mutual Fund watch – curated scheme NAVs + simple return stats + NFO headlines.

Data: public mfapi.in (unofficial aggregator of AMFI NAVs).
Does NOT predict future winners. Past performance ≠ future results.
"""

from __future__ import annotations

from src.shared.time_ist import format_ist, now_ist

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import logging
import re
import xml.etree.ElementTree as ET

import requests
import yaml

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "config" / "mf_watch.yaml"
OUT = ROOT / "config" / "mf_watch_latest.json"
MFAPI = "https://api.mfapi.in/mf/{code}"


@dataclass
class SchemeSnap:
    code: int
    label: str
    bucket: str
    name: str
    nav: Optional[float]
    ret_1m: Optional[float]
    ret_1y: Optional[float]
    ret_3y: Optional[float]


def _load_cfg() -> dict:
    if not CFG.exists():
        return {"schemes": [], "nfo_rss": []}
    return yaml.safe_load(CFG.read_text(encoding="utf-8")) or {}


def _parse_date(s: str) -> Optional[datetime]:
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:10], fmt)
        except Exception:
            continue
    return None


def _ret_from_series(data: List[dict], days: int) -> Optional[float]:
    if not data:
        return None
    try:
        latest = float(data[0]["nav"])
        t0 = _parse_date(str(data[0]["date"]))
        if not t0 or latest <= 0:
            return None
        target = None
        for row in data:
            d = _parse_date(str(row.get("date", "")))
            if not d:
                continue
            if (t0 - d).days >= days:
                target = float(row["nav"])
                break
        if not target or target <= 0:
            return None
        years = days / 365.25
        if days >= 300:
            # annualized
            return ((latest / target) ** (1 / years) - 1) * 100
        return (latest / target - 1) * 100
    except Exception:
        return None


def fetch_scheme(code: int, label: str, bucket: str) -> Optional[SchemeSnap]:
    try:
        r = requests.get(MFAPI.format(code=code), timeout=25)
        if not r.ok:
            return None
        j = r.json()
        meta = j.get("meta") or {}
        data = j.get("data") or []
        if not data:
            return None
        nav = float(data[0]["nav"])
        return SchemeSnap(
            code=code,
            label=label,
            bucket=bucket,
            name=str(meta.get("scheme_name") or label)[:60],
            nav=nav,
            ret_1m=_ret_from_series(data, 30),
            ret_1y=_ret_from_series(data, 365),
            ret_3y=_ret_from_series(data, 365 * 3),
        )
    except Exception as e:
        logger.warning("mf fetch %s: %s", code, e)
        return None


def fetch_nfo_headlines(feeds: List[str], limit: int = 6) -> List[str]:
    out: List[str] = []
    for url in feeds or []:
        try:
            r = requests.get(url, timeout=20, headers={"User-Agent": "StockScorecard/1.0"})
            if not r.ok:
                continue
            root = ET.fromstring(r.content)
            for item in root.findall(".//item"):
                title = (item.findtext("title") or "").strip()
                title = re.sub(r"<[^>]+>", "", title)
                if title and title not in out:
                    out.append(title[:140])
                if len(out) >= limit:
                    return out
        except Exception as e:
            logger.debug("nfo rss: %s", e)
    return out


def run_mf_watch() -> Dict[str, Any]:
    cfg = _load_cfg()
    schemes_cfg = cfg.get("schemes") or []
    # de-dupe codes keeping first label
    seen = set()
    snaps: List[SchemeSnap] = []
    for row in schemes_cfg:
        try:
            code = int(row.get("code"))
        except Exception:
            continue
        if code in seen:
            continue
        seen.add(code)
        s = fetch_scheme(code, str(row.get("label") or code), str(row.get("bucket") or ""))
        if s:
            snaps.append(s)

    headlines = fetch_nfo_headlines(list(cfg.get("nfo_rss") or []))
    payload = {
        "saved_at": format_ist(),
        "schemes": [
            {
                "code": s.code,
                "label": s.label,
                "bucket": s.bucket,
                "name": s.name,
                "nav": s.nav,
                "ret_1m": s.ret_1m,
                "ret_1y": s.ret_1y,
                "ret_3y": s.ret_3y,
            }
            for s in snaps
        ],
        "nfo_headlines": headlines,
    }
    try:
        OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as e:
        logger.debug("mf persist: %s", e)
    return payload


def format_mf_watch_telegram(payload: Optional[Dict[str, Any]] = None) -> str:
    if payload is None:
        payload = run_mf_watch()
    lines = [
        "<b>📊 MUTUAL FUND WATCH</b>",
        payload.get("saved_at") or format_ist(),
        "",
        "<i>Curated schemes only · past returns ≠ future · not advice</i>",
        "",
        "<b>Tracked schemes</b>",
    ]
    schemes = payload.get("schemes") or []
    if not schemes:
        lines.append("• No scheme data (check codes / network)")
    else:
        for s in schemes:
            r1 = s.get("ret_1y")
            r3 = s.get("ret_3y")
            r1t = f"{r1:+.1f}% 1Y" if isinstance(r1, (int, float)) else "1Y n/a"
            r3t = f"{r3:+.1f}% 3Y ann." if isinstance(r3, (int, float)) else "3Y n/a"
            nav = s.get("nav")
            navt = f"NAV ₹{nav:.2f}" if isinstance(nav, (int, float)) else ""
            lines.append(
                f"• <b>{s.get('label') or s.get('name')}</b>\n"
                f"  {navt} · {r1t} · {r3t}"
            )

    heads = payload.get("nfo_headlines") or []
    lines.append("")
    lines.append("<b>NFO / MF headlines (news)</b>")
    if not heads:
        lines.append("• No headlines fetched")
    else:
        for h in heads[:6]:
            lines.append(f"• {h}")

    lines.append("")
    lines.append(
        "<i>Edit list: config/mf_watch.yaml · Compare within category on "
        "Value Research. StockScorecard</i>"
    )
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3900] + "\n…"
    return text
