"""
StockScorecard – Watch dashboard (graphs only, not for buying).

Free dynamic features:
  - Refresh button (clears cache)
  - Optional auto-refresh every N seconds
  - Shorter data cache during market watch
  - Last price + day change when available

Deploy: Streamlit Community Cloud → streamlit_app.py
Local:  streamlit run streamlit_app.py
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
WATCH_PATH = ROOT / "config" / "wide_scan_watch.json"
IST = timezone(timedelta(hours=5, minutes=30))

st.set_page_config(
    page_title="StockScorecard Watch",
    page_icon="📊",
    layout="wide",
)


def _now_ist_str() -> str:
    return datetime.now(IST).strftime("%d %b %Y | %I:%M %p IST")


@st.cache_data(ttl=90)
def load_watch() -> Dict[str, Any]:
    if not WATCH_PATH.exists():
        return {}
    try:
        return json.loads(WATCH_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


@st.cache_data(ttl=120)
def fetch_history(symbol: str, period: str = "1mo") -> Optional[pd.DataFrame]:
    try:
        import yfinance as yf

        for suffix in (".NS", ".BO"):
            t = yf.Ticker(symbol + suffix)
            df = t.history(period=period)
            if df is not None and len(df) >= 5:
                return df.reset_index()
    except Exception:
        return None
    return None


@st.cache_data(ttl=60)
def fetch_quote_snapshot(symbol: str) -> Optional[Tuple[float, float, float]]:
    """Return (last, day_change_pct, day_change_rs) best-effort."""
    try:
        import yfinance as yf

        for suffix in (".NS", ".BO"):
            t = yf.Ticker(symbol + suffix)
            fi = getattr(t, "fast_info", None)
            if fi is not None:
                try:
                    last = float(fi.get("last_price") or fi.get("lastPrice") or 0)
                    prev = float(fi.get("previous_close") or fi.get("previousClose") or 0)
                    if last > 0 and prev > 0:
                        return last, (last / prev - 1.0) * 100.0, last - prev
                except Exception:
                    pass
            df = t.history(period="5d")
            if df is not None and len(df) >= 2:
                last = float(df["Close"].iloc[-1])
                prev = float(df["Close"].iloc[-2])
                if last > 0 and prev > 0:
                    return last, (last / prev - 1.0) * 100.0, last - prev
    except Exception:
        return None
    return None


def main():
    st.title("📊 StockScorecard — Watch")
    st.caption(
        "Graphs only · not a broker · not advice. "
        f"Page time: {_now_ist_str()}"
    )

    # --- controls ---
    c1, c2, c3, c4 = st.columns([1.2, 1.2, 1.5, 1])
    with c1:
        if st.button("🔄 Refresh data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    with c2:
        auto = st.toggle("Auto-refresh", value=False, help="Uses free rerun; tab must stay open")
    with c3:
        every = st.selectbox(
            "Every",
            options=[60, 120, 180, 300],
            format_func=lambda s: f"{s // 60} min" if s >= 60 else f"{s}s",
            index=1,
            disabled=not auto,
        )
    with c4:
        period = st.selectbox("Chart", ["5d", "1mo", "3mo"], index=1)

    if auto:
        st.info(f"Auto-refresh on · about every {every}s while this tab stays open (free tier).")
        # Non-blocking style: sleep then rerun
        time.sleep(0.3)

    watch = load_watch()
    items: List[Dict[str, Any]] = list(watch.get("items") or [])

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Captured day", watch.get("captured_day") or "—")
    with m2:
        st.metric("Names", len(items))
    with m3:
        st.metric("Watch file", (watch.get("saved_at") or "—")[:24])

    if not items:
        st.warning(
            "No watchlist yet. Run **Wide Parallel Scan** on GitHub so "
            "`config/wide_scan_watch.json` is committed."
        )
        if auto:
            time.sleep(every)
            st.rerun()
        st.stop()

    symbols = [str(it.get("symbol", "")).upper() for it in items if it.get("symbol")]
    st.subheader("Copy symbols")
    st.code(",".join(symbols), language=None)

    # Live-ish snapshots
    st.subheader("Snapshot (best-effort)")
    rows = []
    prog = st.progress(0)
    for i, it in enumerate(items):
        sym = str(it.get("symbol", "")).upper()
        snap = fetch_quote_snapshot(sym)
        last = chg = day_rs = None
        if snap:
            last, chg, day_rs = snap[0], snap[1], snap[2] if len(snap) > 2 else None
        cap = it.get("capture_price")
        delta_rs = None
        try:
            if last is not None and cap is not None:
                delta_rs = round(float(last) - float(cap), 2)
        except Exception:
            delta_rs = None
        # Simple technical score 0-100 from momentum (free, no paid API)
        tech = None
        try:
            r1 = float(it.get("capture_ret_1d") or 0)
            r5 = float(it.get("capture_ret_5d") or 0)
            vol = float(it.get("capture_vol_ratio") or 1)
            tech = max(0, min(100, 40 + r1 * 2.5 + max(r5, 0) * 0.8 + min(vol, 5) * 3))
            tech = round(tech, 1)
        except Exception:
            tech = None
        rows.append(
            {
                "Symbol": sym,
                "Name": (it.get("name") or "")[:28],
                "Last ₹": round(last, 2) if last else None,
                "Δ ₹ vs cap": delta_rs,
                "Day %": round(chg, 2) if chg is not None else None,
                "Day Δ ₹": round(day_rs, 2) if day_rs is not None else None,
                "Capture ₹": cap,
                "Cap 1D %": it.get("capture_ret_1d"),
                "Tech": tech,
                "Score": it.get("capture_score"),
            }
        )
        prog.progress((i + 1) / max(len(items), 1))
    prog.empty()
    df_tbl = pd.DataFrame(rows)

    def _focus_row(r) -> bool:
        """Stocks to focus: still green today and holding vs capture."""
        try:
            day = r.get("Day %")
            last = r.get("Last ₹")
            cap = r.get("Capture ₹")
            if day is None or last is None or cap is None:
                return False
            if float(day) < 1.0:
                return False
            if float(cap) <= 0:
                return False
            # holding at least ~flat vs capture (not broken)
            if float(last) < float(cap) * 0.98:
                return False
            return True
        except Exception:
            return False

    focus_mask = [_focus_row(r) for r in rows]
    n_focus = sum(focus_mask)
    st.markdown(
        f"**Focus (green):** {n_focus} names — Day% ≥ +1 and price holding near/above capture. "
        "Observe only; Telegram CONTINUE still rules buys."
    )

    def _style_focus(row):
        try:
            idx = row.name
            if idx < len(focus_mask) and focus_mask[idx]:
                return ["color: #0a7a2f; font-weight: 700"] * len(row)
        except Exception:
            pass
        return [""] * len(row)

    col_cfg = {
        "Day %": st.column_config.NumberColumn(format="%+.2f"),
        "Day Δ ₹": st.column_config.NumberColumn(format="%+.2f"),
        "Cap 1D %": st.column_config.NumberColumn(format="%+.1f"),
        "Δ ₹ vs cap": st.column_config.NumberColumn(format="%+.2f"),
        "Tech": st.column_config.NumberColumn(format="%.0f"),
    }
    try:
        styled = df_tbl.style.apply(_style_focus, axis=1)
        st.dataframe(
            styled,
            use_container_width=True,
            hide_index=True,
            column_config=col_cfg,
        )
    except Exception:
        st.dataframe(
            df_tbl,
            use_container_width=True,
            hide_index=True,
            column_config=col_cfg,
        )

    st.subheader("Why these may be rising (context)")
    st.caption(
        "Tech = momentum/volume score from the scan (0–100). "
        "Full fundamental ROE/PE needs Screener login per stock — shown as N/A here on free path. "
        "Reasoning is rule-based, not guaranteed news cause."
    )
    reason_rows = []
    for it, r in zip(items, rows):
        sym = r.get("Symbol")
        r1 = it.get("capture_ret_1d")
        r5 = it.get("capture_ret_5d")
        vol = it.get("capture_vol_ratio")
        bits = []
        try:
            if r1 is not None and float(r1) >= 5:
                bits.append(f"strong 1D move ({float(r1):+.1f}%)")
            if r5 is not None and float(r5) >= 8:
                bits.append(f"multi-day strength ({float(r5):+.1f}% 5D)")
            if vol is not None and float(vol) >= 2:
                bits.append(f"volume spike ({float(vol):.1f}x)")
        except Exception:
            pass
        if not bits:
            bits.append("scan momentum / relative strength")
        # crude fundamental placeholder
        fund = "N/A (free)"
        reason_rows.append(
            {
                "Symbol": sym,
                "Tech": r.get("Tech"),
                "Fund": fund,
                "Likely drivers": "; ".join(bits),
            }
        )
    st.dataframe(pd.DataFrame(reason_rows), use_container_width=True, hide_index=True)

    st.subheader("Charts (observe only)")
    max_charts = st.slider("Charts shown", 4, min(20, len(items)), min(10, len(items)))
    cols = st.columns(2)
    for i, it in enumerate(items[:max_charts]):
        sym = str(it.get("symbol", "")).upper()
        name = it.get("name") or sym
        with cols[i % 2]:
            snap = fetch_quote_snapshot(sym)
            is_focus = False
            if snap and it.get("capture_price"):
                try:
                    is_focus = snap[1] >= 1.0 and snap[0] >= float(it["capture_price"]) * 0.98
                except Exception:
                    is_focus = False
            if is_focus:
                head = f"🟢 **{sym}** — {name}"
            else:
                head = f"**{sym}** — {name}"
            if snap:
                head += f" · ₹{snap[0]:.2f} ({snap[1]:+.1f}%)"
            if is_focus:
                st.markdown(f'<span style="color:#0a7a2f;font-weight:700">{head}</span>', unsafe_allow_html=True)
            else:
                st.markdown(head)
            df = fetch_history(sym, period=period)
            if df is None or df.empty:
                st.caption("No chart data")
                continue
            price_col = "Close" if "Close" in df.columns else [c for c in df.columns if c != df.columns[0]][0]
            st.line_chart(df.set_index(df.columns[0])[price_col], height=180)
            if it.get("capture_price"):
                st.caption(f"Capture ₹{it.get('capture_price')}")

    st.divider()
    st.subheader("📰 News intelligence")
    st.caption(
        "Market headlines (Telegram news-layer family). Context only — not buy signals."
    )
    try:
        import sys

        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from src.intelligence.news_layer import fetch_market_news

        news_items = fetch_market_news(max_items=10)
        if not news_items:
            st.info("No headlines fetched right now (network/RSS).")
        else:
            for n in news_items:
                title = getattr(n, "title", "") or ""
                source = getattr(n, "source", "") or ""
                bias = getattr(n, "bias", "") or ""
                syms = getattr(n, "matched_symbols", None) or []
                extra = ""
                if syms:
                    extra = f" · _{', '.join(list(syms)[:4])}_"
                if bias and str(bias) != "Neutral":
                    extra += f" · {bias}"
                st.markdown(f"- **{title[:160]}** ({source}){extra}")
    except Exception as e:
        st.warning(f"News layer unavailable in this session: {e}")

    st.divider()
    st.markdown(
        "**Free setup limits:** Yahoo data delay · not tick-by-tick · "
        "Streamlit free may sleep · auto-refresh only while tab is open. "
        "Telegram = alerts · this page = watch graphs + news at bottom."
    )

    if auto:
        time.sleep(int(every))
        st.rerun()


if __name__ == "__main__":
    main()
