# Streamlit Watch dashboard (graphs only)

Observe wide-scan symbols as charts. **Not for placing orders.**

## Local
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Free deploy (Streamlit Community Cloud)
1. https://share.streamlit.io (sign in with GitHub)
2. New app → repo `Sayed632/StockScorecard` → main
3. Main file: `streamlit_app.py`
4. Deploy

Data comes from `config/wide_scan_watch.json` (updated when Wide Parallel Scan runs and commits).

## Use with Telegram
- Telegram = alerts (CONTINUE / WAIT)
- Streamlit = see graphs of the watch list
- Groww/Zerodha = only if you decide to trade
