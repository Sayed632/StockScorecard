# Paste this into Grok Project: Stockcard (first message)

You are continuing the **StockScorecard** system (repo: https://github.com/Sayed632/StockScorecard).

## Locked decisions
- Smart Digest: **Streamlit only** (not replacing Telegram).
- Telegram: **keep all** existing flow messages.
- AI: **free only**; rule-based digest always; OpenRouter only if free model works.
- Buy rule: **CONTINUE + stop + small size**; do not chase Wide/Raising alone.
- Streamlit: **watch/observe**, not a broker.

## Architecture
- **RAISING**: 5D≥8% OR 10D≥12%; tags STILL, EXTENDED; broad radar.
- **FILTERED**: subset; CONTINUE / WAIT / SKIP; anti-chase on EXTENDED.
- **Wide scan**: separate 1D + volume bursts.
- Flows are **mostly silo**; Streamlit/Brief partially merge JSON.
- Latest JSON **overwrites**; `config/alert_history.jsonl` appends live alerts.
- **Backtest engine**: sample history, forward +1/+3/+5/+10d; workflow `backtest.yml`.
- Missed rallies (MSTC/BALAXI-type): top-N rank + discrete scans, not full 1W leaderboard.

## Free-only next priority
1. Rule-based Smart Digest on Streamlit from Raising + Filtered + Wide + Brief JSON.
2. Optional free OpenRouter behind same digest.
3. Outcome scoring on alert_history.

## Human checklist
Raising = watch · Filtered CONTINUE = optional entry with stop · EXTENDED = no chase.

Full detail: `docs/PROJECT_CONTEXT.md` in the repo.
