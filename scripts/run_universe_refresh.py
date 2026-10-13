#!/usr/bin/env python3
"""Refresh NSE equity symbol cache for full-universe scans."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.data_fetch.nse_universe import fetch_nse_equity_symbols, load_merged_universe

rows = fetch_nse_equity_symbols()
print("NSE symbols:", len(rows))
merged = load_merged_universe()
print("Merged universe:", len(merged))
print("CMLL in merged:", any(s == "CMLL" for s, _ in merged))
