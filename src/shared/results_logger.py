"""
Results logger – stores every recommended idea for later outcome tracking.
CSV append-only log under data/results_log.csv
"""

from pathlib import Path
from datetime import datetime
from typing import List, Optional
import csv
import logging

from src.shared.models import StockIdea, ScanResult

logger = logging.getLogger(__name__)

LOG_PATH = Path("data/results_log.csv")
FIELDNAMES = [
    "logged_at",
    "scan_time",
    "frequency",
    "symbol",
    "name",
    "sector",
    "engine",
    "action",
    "score",
    "probability",
    "reason",
    "market_cap_cr",
    "market_cap_bucket",
    "catalysts",
    # Outcome fields (filled later manually or by a follow-up job)
    "outcome_checked_at",
    "return_5d_pct",
    "return_10d_pct",
    "return_20d_pct",
    "hit_target",
    "notes",
]


def _ensure_header(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size == 0:
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=FIELDNAMES).writeheader()


def log_scan_result(result: ScanResult) -> Path:
    """Append all ideas from a scan to the results log."""
    _ensure_header(LOG_PATH)
    now = datetime.now().isoformat(timespec="seconds")
    rows = []

    def add(idea: StockIdea):
        rows.append({
            "logged_at": now,
            "scan_time": result.scan_time.isoformat(timespec="seconds"),
            "frequency": result.frequency,
            "symbol": idea.symbol,
            "name": idea.name,
            "sector": idea.sector,
            "engine": idea.engine.value,
            "action": idea.action.value,
            "score": idea.score,
            "probability": idea.extras.get("probability", "") if idea.extras else "",
            "reason": idea.reason,
            "market_cap_cr": idea.market_cap_cr if idea.market_cap_cr is not None else "",
            "market_cap_bucket": idea.market_cap_bucket or "",
            "catalysts": "|".join(idea.catalysts or []),
            "outcome_checked_at": "",
            "return_5d_pct": "",
            "return_10d_pct": "",
            "return_20d_pct": "",
            "hit_target": "",
            "notes": "",
        })

    for idea in result.swing_ideas + result.long_term_ideas + result.dark_horse_ideas:
        add(idea)

    if not rows:
        logger.info("Results logger: no ideas to log")
        return LOG_PATH

    with LOG_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writerows(rows)

    logger.info(f"Results logger: wrote {len(rows)} ideas → {LOG_PATH}")
    return LOG_PATH
