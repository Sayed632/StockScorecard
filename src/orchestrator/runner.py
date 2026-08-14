"""
Main Orchestrator – runs the full daily decision cycle.
"""

import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import logging

from src.orchestrator.frequency import decide_scanning_frequency, is_results_season, get_scan_slots
from src.sectors.pharmaceuticals import PharmaceuticalsScanner
from src.sectors.banks_financials import BanksFinancialsScanner
from src.sectors.information_technology import InformationTechnologyScanner
from src.sectors.automobile_ev import AutomobileEVScanner
from src.sectors.defence_aerospace import DefenceAerospaceScanner
from src.sectors.chemicals import ChemicalsScanner
from src.sectors.fmcg import FMCGScanner
from src.sectors.penny_monitor import PennyMonitorScanner
from src.sectors.metals_mining import MetalsMiningScanner
from src.sectors.energy_oil_gas_power import EnergyOilGasPowerScanner
from src.sectors.capital_goods_infra import CapitalGoodsInfraScanner
from src.sectors.realty import RealtyScanner
from src.sectors.telecom import TelecomScanner
from src.sectors.media import MediaScanner
from src.sectors.textiles import TextilesScanner
from src.sectors.others_residual import OthersResidualScanner
from src.decision.ranking import merge_and_rank
from src.shared.fii_dii import fetch_fii_dii, fetch_sector_fpi
from src.shared.results_logger import log_scan_result
from src.delivery.telegram_report import send_daily_report, format_report
from src.shared.models import ScanResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# Registry of available sector scanners
SECTOR_REGISTRY = {
    "pharmaceuticals": PharmaceuticalsScanner,
    "banks_financials": BanksFinancialsScanner,
    "information_technology": InformationTechnologyScanner,
    "automobile_ev": AutomobileEVScanner,
    "defence_aerospace": DefenceAerospaceScanner,
    "chemicals": ChemicalsScanner,
    "fmcg": FMCGScanner,
    "penny_monitor": PennyMonitorScanner,
    "metals_mining": MetalsMiningScanner,
    "energy_oil_gas_power": EnergyOilGasPowerScanner,
    "capital_goods_infra": CapitalGoodsInfraScanner,
    "realty": RealtyScanner,
    "telecom": TelecomScanner,
    "media": MediaScanner,
    "textiles": TextilesScanner,
    "others_residual": OthersResidualScanner,
}


def run_full_scan(
    config_path: str = "config.yaml",
    send_telegram: bool = True,
    force_frequency: int = None,
) -> ScanResult:
    """
    Execute one full decision cycle.
    """
    cfg = load_config(config_path)
    max_ideas = cfg.get("max_ideas_per_list", 8)

    # 1. Decide frequency
    if force_frequency:
        freq = force_frequency
        freq_reason = "Forced"
    else:
        freq, freq_reason = decide_scanning_frequency(
            volatility_high=False,          # can be connected to real VIX later
            results_season=is_results_season(),
            major_event=False,
            heavy_news_density=False,
        )

    logger.info(f"=== StockScorecard Scan Started | Frequency {freq}x ({freq_reason}) ===")
    logger.info(f"Slots: {get_scan_slots(freq)}")

    # 2. Run active sector scanners in sequence (parallel later)
    sector_results = {}
    active = cfg.get("active_sectors", ["pharmaceuticals"])

    for sector_key in active:
        scanner_cls = SECTOR_REGISTRY.get(sector_key)
        if not scanner_cls:
            logger.warning(f"No scanner registered for {sector_key} – skipping")
            continue

        logger.info(f"Scanning sector: {sector_key}")
        scanner = scanner_cls(config=cfg)
        try:
            result = scanner.run()
            sector_results[sector_key] = result
            logger.info(
                f"  → Swing: {len(result['swing'])} | "
                f"Long-term: {len(result['long_term'])} | "
                f"Dark Horse: {len(result['dark_horse'])}"
            )
        except Exception as e:
            logger.error(f"Sector {sector_key} failed: {e}")

    # 3. Institutional flows
    fii_snap = fetch_fii_dii(include_history=True)
    sector_fpi = fetch_sector_fpi()
    if fii_snap:
        logger.info(f"FII net={fii_snap.fii_net:.0f} | DII net={fii_snap.dii_net:.0f} | bias={fii_snap.swing_bias_points()[0]:+.0f}")
    logger.info(f"Sector FPI rows: {len(sector_fpi)}")

    # 4. Merge & rank (with FII/DII + sector FPI swing bias)
    scan_result = merge_and_rank(
        sector_results,
        max_per_list=max_ideas,
        frequency=freq,
        frequency_reason=freq_reason,
        fii_dii=fii_snap,
        sector_fpi=sector_fpi,
    )

    # 4. Deliver
    report_text = format_report(scan_result)
    print("\n" + "=" * 60)
    print(report_text.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", ""))
    print("=" * 60 + "\n")

    if send_telegram:
        ok = send_daily_report(scan_result)
        if ok:
            logger.info("Report successfully sent to Telegram")
        else:
            logger.warning("Telegram delivery failed – check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")

    # 5. Save CSV snapshot
    _save_snapshot(scan_result)
    log_scan_result(scan_result)

    logger.info("=== Scan Complete ===")
    return scan_result


def _save_snapshot(result: ScanResult):
    import pandas as pd
    from pathlib import Path

    rows = []
    for idea in result.swing_ideas + result.long_term_ideas + result.dark_horse_ideas:
        rows.append({
            "symbol": idea.symbol,
            "name": idea.name,
            "sector": idea.sector,
            "engine": idea.engine.value,
            "action": idea.action.value,
            "reason": idea.reason,
            "score": idea.score,
            "market_cap_cr": idea.market_cap_cr,
            "bucket": idea.market_cap_bucket,
        })

    if not rows:
        return

    df = pd.DataFrame(rows)
    out_dir = Path("data")
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"decision_{result.scan_time.strftime('%Y%m%d_%H%M')}.csv"
    df.to_csv(path, index=False)
    logger.info(f"Snapshot saved → {path}")