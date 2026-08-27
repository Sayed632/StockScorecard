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
from src.shared.fii_dii import fetch_fii_dii, fetch_sector_fpi, format_flows_telegram_message
from src.intelligence.sector_rotation import format_sector_rotation_telegram
from src.intelligence.penny_screener import format_penny_telegram
from src.intelligence.multibagger_screener import format_multibagger_telegram
from src.shared.results_logger import log_scan_result
from src.strategies.madhusudan_kela import run_kela_strategy, format_kela_telegram
from src.strategies.minervini_oneil import run_minervini_oneil, format_mo_telegram
from src.intelligence.news_layer import format_news_telegram_message
from src.intelligence.nse_announcements import format_nse_telegram_message
from src.intelligence.horizon_monitor import format_horizon_telegram
from src.intelligence.hot_stocks import format_hot_telegram
from src.intelligence.trade_plans import format_trade_plans_telegram
from src.intelligence.fresh_buys import format_fresh_buys_telegram
from src.intelligence.daily_digest import format_daily_digest_telegram
from src.intelligence.ipo_performance import format_ipo_telegram
from src.telegram_notify import send_message as telegram_send
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

    # Auto-sync ticker registry from sector/strategy files (no manual update needed)
    try:
        import importlib.util
        from pathlib import Path as _P
        _root = _P(__file__).resolve().parents[2]
        _spec = importlib.util.spec_from_file_location(
            "sync_tickers", _root / "scripts" / "sync_tickers.py"
        )
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        _n_disc, _n_add, _added = _mod.sync()
        if _n_add:
            logger.info("Ticker sync: added %s new symbols: %s", _n_add, _added[:15])
        else:
            logger.info("Ticker sync: registry up to date (%s symbols discovered)", _n_disc)
    except Exception as e:
        logger.warning("Ticker sync skipped: %s", e)

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
        cfg=cfg,
    )

    # 4. Deliver
    report_text = format_report(scan_result)
    print("\n" + "=" * 60)
    print(report_text.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", ""))
    print("=" * 60 + "\n")

    if send_telegram:
        ok = send_daily_report(scan_result)

        # Digest first (with regular messages after)
        try:
            digest_text = format_daily_digest_telegram()
            if len(digest_text) > 4000:
                digest_text = digest_text[:3900] + "\n\n… (truncated)"
            logger.info("Daily digest Telegram: %s", "sent" if telegram_send(digest_text) else "failed")
        except Exception as e:
            logger.warning("Daily digest failed: %s", e)
        if ok:
            logger.info("Report successfully sent to Telegram")
        else:
            logger.warning("Telegram delivery failed – check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")

        # Fresh buys – single sorted list
        try:
            sec_text = format_sector_rotation_telegram()
            if len(sec_text) > 4000:
                sec_text = sec_text[:3900] + "\n\n… (truncated)"
            logger.info("Sector rotation Telegram: %s", "sent" if telegram_send(sec_text) else "failed")
        except Exception as e:
            logger.warning("Sector rotation failed: %s", e)

        try:
            flows_text = format_flows_telegram_message()
            if len(flows_text) > 4000:
                flows_text = flows_text[:3900] + "\n\n… (truncated)"
            logger.info("FII/DII flows Telegram: %s", "sent" if telegram_send(flows_text) else "failed")
        except Exception as e:
            logger.warning("FII/DII flows message failed: %s", e)

        try:
            fb_text = format_fresh_buys_telegram()
            if len(fb_text) > 4000:
                fb_text = fb_text[:3900] + "\n\n… (truncated)"
            fb_ok = telegram_send(fb_text)
            logger.info("Fresh buys Telegram: %s", "sent" if fb_ok else "failed")
        except Exception as e:
            logger.warning("Fresh buys failed: %s", e)

        # Separate message: Madhusudan Kela strategy sleeve
        try:
            kela = run_kela_strategy()
            kela_text = format_kela_telegram(kela)
            if len(kela_text) > 4000:
                kela_text = kela_text[:3900] + "\n\n… (truncated)"
            kok = telegram_send(kela_text)
            logger.info("Kela strategy Telegram: %s", "sent" if kok else "failed")
        except Exception as e:
            logger.warning("Kela strategy sleeve failed: %s", e)

        # Separate message: Minervini/O'Neil strategy
        try:
            mo = run_minervini_oneil()
            mo_text = format_mo_telegram(mo)
            if len(mo_text) > 4000:
                mo_text = mo_text[:3900] + "\n\n… (truncated)"
            mok = telegram_send(mo_text)
            logger.info("Minervini/O'Neil Telegram: %s", "sent" if mok else "failed")
        except Exception as e:
            logger.warning("Minervini/O'Neil sleeve failed: %s", e)

        # Separate message: News intelligence
        try:
            news_text = format_news_telegram_message()
            if len(news_text) > 4000:
                news_text = news_text[:3900] + "\n\n… (truncated)"
            nok = telegram_send(news_text)
            logger.info("News intelligence Telegram: %s", "sent" if nok else "failed")
        except Exception as e:
            logger.warning("News intelligence failed: %s", e)

        try:
            nse_text = format_nse_telegram_message()
            if len(nse_text) > 4000:
                nse_text = nse_text[:3900] + "\n\n… (truncated)"
            nse_ok = telegram_send(nse_text)
            logger.info("NSE announcements Telegram: %s", "sent" if nse_ok else "failed")
        except Exception as e:
            logger.warning("NSE announcements failed: %s", e)

        try:
            hz = format_horizon_telegram()
            if len(hz) > 4000:
                hz = hz[:3900] + "\n\n… (truncated)"
            hok = telegram_send(hz)
            logger.info("Horizon monitor Telegram: %s", "sent" if hok else "failed")
        except Exception as e:
            logger.warning("Horizon monitor failed: %s", e)

        try:
            hot_text = format_hot_telegram()
            if len(hot_text) > 4000:
                hot_text = hot_text[:3900] + "\n\n… (truncated)"
            hot_ok = telegram_send(hot_text)
            logger.info("Hot stocks Telegram: %s", "sent" if hot_ok else "failed")
        except Exception as e:
            logger.warning("Hot stocks failed: %s", e)

        try:
            penny_text = format_penny_telegram()
            if len(penny_text) > 4000:
                penny_text = penny_text[:3900] + "\n\n… (truncated)"
            logger.info("Penny screener Telegram: %s", "sent" if telegram_send(penny_text) else "failed")
        except Exception as e:
            logger.warning("Penny screener failed: %s", e)

        try:
            mb_text = format_multibagger_telegram()
            if len(mb_text) > 4000:
                mb_text = mb_text[:3900] + "\n\n… (truncated)"
            logger.info("Multibagger Telegram: %s", "sent" if telegram_send(mb_text) else "failed")
        except Exception as e:
            logger.warning("Multibagger screener failed: %s", e)

        try:
            ipo_text = format_ipo_telegram()
            if len(ipo_text) > 4000:
                ipo_text = ipo_text[:3900] + "\n\n… (truncated)"
            logger.info("IPO performance Telegram: %s", "sent" if telegram_send(ipo_text) else "failed")
        except Exception as e:
            logger.warning("IPO performance failed: %s", e)

        try:
            tp_text = format_trade_plans_telegram()
            if len(tp_text) > 4000:
                tp_text = tp_text[:3900] + "\n\n… (truncated)"
            tp_ok = telegram_send(tp_text)
            logger.info("Trade plans Telegram: %s", "sent" if tp_ok else "failed")
        except Exception as e:
            logger.warning("Trade plans failed: %s", e)

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