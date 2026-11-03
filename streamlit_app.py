"""
StockScorecard – Watch dashboard (graphs only, not for buying).

Deploy: Streamlit Community Cloud → main file streamlit_app.py
Local:  streamlit run streamlit_app.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
WATCH_PATH = ROOT / "config" / "wide_scan_watch.json"

st.set_page_config(
    page_title="StockScorecard Watch",
    page_icon="📊",
    layout="wide",
)


@st.cache_data(ttl=300)
def load_watch() -> Dict[str, Any]:
    if not WATCH_PATH.exists():
        return {}
    try:
        return json.loads(WATCH_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


@st.cache_data(ttl=600)
def fetch_history(symbol: str, period: str = "1mo") -> Optional[pd.DataFrame]:
    try:
        import yfinance as yf

        for suffix in (".NS", ".BO"):
            t = yf.Ticker(symbol + suffix)
            df = t.history(period=period)
            if df is not None and len(df) >= 5:
                df = df.reset_index()
                return df
    except Exception:
        return None
    return None


def main():
    st.title("📊 StockScorecard — Watch (graphs only)")
    st.caption(
        "Observe wide-scan names as charts. Not a broker. Not investment advice. "
        "Buy decisions only from Telegram CONTINUE + your own risk rules."
    )

    watch = load_watch()
    items: List[Dict[str, Any]] = list(watch.get("items") or [])

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("Captured day", watch.get("captured_day") or "—")
    with col_b:
        st.metric("Names on list", len(items))
    with col_c:
        st.metric("Saved at", (watch.get("saved_at") or "—")[:22])

    if not items:
        st.warning(
            "No watchlist file yet. Run **Wide Parallel Scan** on GitHub Actions "
            "so `config/wide_scan_watch.json` is updated."
        )
        st.stop()

    symbols = [str(it.get("symbol", "")).upper() for it in items if it.get("symbol")]
    st.subheader("Copy symbols")
    st.code(",".join(symbols), language=None)

    st.subheader("List")
    table = pd.DataFrame(
        [
            {
                "Symbol": it.get("symbol"),
                "Name": it.get("name"),
                "Capture ₹": it.get("capture_price"),
                "1D %": it.get("capture_ret_1d"),
                "5D %": it.get("capture_ret_5d"),
                "Vol×": it.get("capture_vol_ratio"),
                "Score": it.get("capture_score"),
            }
            for it in items
        ]
    )
    st.dataframe(table, use_container_width=True, hide_index=True)

    st.subheader("Charts (observe only)")
    period = st.selectbox("History", ["1mo", "3mo", "6mo"], index=0)
    max_charts = st.slider("How many charts", 4, min(20, len(items)), min(12, len(items)))

    cols = st.columns(2)
    for i, it in enumerate(items[:max_charts]):
        sym = str(it.get("symbol", "")).upper()
        name = it.get("name") or sym
        with cols[i % 2]:
            st.markdown(f"**{sym}** — {name}")
            df = fetch_history(sym, period=period)
            if df is None or df.empty:
                st.caption("No chart data")
                continue
            price_col = "Close" if "Close" in df.columns else df.columns[-1]
            st.line_chart(df.set_index(df.columns[0])[price_col], height=180)
            cap = it.get("capture_price")
            if cap:
                st.caption(f"Capture ₹{cap}")

    st.divider()
    st.markdown(
        "**How to use:** Telegram alerts → this page for graphs → "
        "only consider buys when Next-Day Plan says CONTINUE."
    )


if __name__ == "__main__":
    main()
