"""
Peer Watch – when a mover prints, check theme siblings (config/peer_groups.yaml).

Not Groww-level ML similarity; fixed theme lists (packaging, chemicals, defence…).
"""

from __future__ import annotations

from src.shared.time_ist import format_ist, now_ist

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import logging
import math
import yaml

from src.data_fetch.prices import fetch_price_history

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
PEER_YAML = ROOT / "config" / "peer_groups.yaml"
WATCH_JSON = ROOT / "config" / "wide_scan_watch.json"


def _load_groups() -> List[Dict[str, Any]]:
    if not PEER_YAML.exists():
        return []
    data = yaml.safe_load(PEER_YAML.read_text(encoding="utf-8")) or {}
    return list(data.get("groups") or {}).values() if isinstance(data.get("groups"), dict) else list(
        (data.get("groups") or [])
    )


def load_peer_index() -> Dict[str, List[Tuple[str, str]]]:
    """
    symbol -> list of (group_label, peer_symbol)
    """
    raw = yaml.safe_load(PEER_YAML.read_text(encoding="utf-8")) if PEER_YAML.exists() else {}
    groups = raw.get("groups") or {}
    idx: Dict[str, List[Tuple[str, str]]] = {}
    if isinstance(groups, dict):
        iterable = groups.items()
        for _key, g in iterable:
            label = str(g.get("label") or _key)
            syms = [str(s).upper() for s in (g.get("symbols") or [])]
            for s in syms:
                for p in syms:
                    if p != s:
                        idx.setdefault(s, []).append((label, p))
    return idx


def _ret_1d_5d(symbol: str) -> Optional[Tuple[float, float, float]]:
    """price, ret_1d_pct, ret_5d_pct"""
    try:
        df = fetch_price_history(f"{symbol}.NS", period="1mo")
        if df is None or len(df) < 6:
            df = fetch_price_history(f"{symbol}.BO", period="1mo")
        if df is None or len(df) < 3:
            return None
        c = df["close"].astype(float).dropna()
        px = float(c.iloc[-1])
        if px <= 0 or math.isnan(px):
            return None
        r1 = (px / float(c.iloc[-2]) - 1) * 100 if len(c) >= 2 else 0.0
        r5 = (px / float(c.iloc[-6]) - 1) * 100 if len(c) >= 6 else None
        return px, r1, r5 if r5 is not None else 0.0
    except Exception:
        return None


def peers_for_symbols(symbols: List[str]) -> List[str]:
    idx = load_peer_index()
    out: List[str] = []
    seen: Set[str] = set()
    for s in symbols:
        s = s.upper()
        for _label, p in idx.get(s, []):
            if p not in seen and p not in symbols:
                seen.add(p)
                out.append(p)
    return out


def run_peer_watch(
    seed_symbols: Optional[List[str]] = None,
    max_seeds: int = 12,
    max_peers: int = 25,
) -> Dict[str, Any]:
    """
    seed_symbols: from wide-scan watch or explicit.
    Returns co-moving peers with 1D/5D strength.
    """
    seeds = [s.upper() for s in (seed_symbols or [])]
    if not seeds and WATCH_JSON.exists():
        try:
            import json

            w = json.loads(WATCH_JSON.read_text(encoding="utf-8"))
            seeds = [str(it.get("symbol", "")).upper() for it in (w.get("items") or [])[:max_seeds]]
            seeds = [s for s in seeds if s]
        except Exception:
            seeds = []

    idx = load_peer_index()
    peer_set: List[Tuple[str, str, str]] = []  # peer, label, seed
    seen: Set[str] = set()
    for s in seeds:
        for label, p in idx.get(s, []):
            if p in seen or p in seeds:
                continue
            seen.add(p)
            peer_set.append((p, label, s))
            if len(peer_set) >= max_peers:
                break
        if len(peer_set) >= max_peers:
            break

    hits = []
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(_ret_1d_5d, p): (p, label, seed) for p, label, seed in peer_set}
        for fut in as_completed(futs):
            p, label, seed = futs[fut]
            got = fut.result()
            if not got:
                continue
            px, r1, r5 = got
            # surface if peer also moving
            if r1 >= 1.5 or r5 >= 4:
                hits.append(
                    {
                        "symbol": p,
                        "price": px,
                        "ret_1d": r1,
                        "ret_5d": r5,
                        "group": label,
                        "because_of": seed,
                    }
                )

    hits.sort(key=lambda x: (-x["ret_1d"], -x["ret_5d"]))
    return {
        "scan_time": now_ist(),
        "seeds": seeds,
        "peers_checked": len(peer_set),
        "hits": hits[:15],
    }


def format_peer_watch_telegram(result: Optional[Dict[str, Any]] = None) -> str:
    if result is None:
        result = run_peer_watch()
    now = format_ist(result.get("scan_time"))
    hits = result.get("hits") or []
    lines = [
        "<b>🔗 PEER WATCH</b>",
        now,
        f"<i>Theme siblings of recent movers · checked {result.get('peers_checked', 0)} peers</i>",
        "",
        "<b>👩 Simple</b>",
        "• These are <b>related</b> stocks (same theme), not auto-buy",
        "• Use only with CONTINUES from main plan + stop",
        "",
    ]
    if not hits:
        lines.append("• No peer co-moves above threshold right now")
    else:
        lines.append("<b>Peers also moving</b>")
        for h in hits:
            lines.append(
                f"• <b>{h['symbol']}</b> ₹{h['price']:.2f} · "
                f"1D {h['ret_1d']:+.1f}% · 5D {h['ret_5d']:+.1f}%"
            )
            lines.append(f"   {h['group']} · linked to {h['because_of']}")
    lines.append("")
    lines.append(
        "<i>Fixed theme lists (packaging, chemicals, defence…). "
        "Not Groww full similarity. Not advice. StockScorecard</i>"
    )
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3900] + "\n\n… (truncated)"
    return text
