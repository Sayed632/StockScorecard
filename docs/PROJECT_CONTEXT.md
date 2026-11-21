# StockScorecard — Project context (discussion migration)

Last updated: 2026-11-21  
Purpose: Carry forward product decisions from long design chats so work continues in this repo/project, not only in chat history.

## Product goal

- Decision-support for NSE swing + multi-day strength (not a broker, not SEBI advice).
- Usable by operator and spouse: simple labels, Streamlit watch, Telegram alerts.
- Free-tier first (GitHub Actions, Yahoo, Streamlit Community Cloud, Telegram).

## Locked UX decisions

| Topic | Decision |
|--------|----------|
| Smart Digest location | **Streamlit only** |
| Telegram | **Keep all existing flow messages** (do not replace with digest-only) |
| AI cost | **Free only** — rule-based digest always; OpenRouter only if free model works |
| Buy discipline | **CONTINUE + stop + small size**; never chase Wide/Raising alone |
| Streamlit role | **Observe graphs/lists** — not a buy button |

## Core list architecture

1. **RAISING STOCKS** (radar)  
   - Gate: 5D ≥ +8% **OR** 10D ≥ +12% (10D not negative).  
   - Larger shortlist; tags: STILL, EXTENDED.

2. **FILTERED STOCKS** (discipline)  
   - Subset of Raising + liquidity/price floor + anti-chase.  
   - Labels: **CONTINUE / WAIT / SKIP**.  
   - EXTENDED (e.g. 1D ≥ +12% or large 5D) → usually WAIT, not chase.

3. **Wide Parallel Scan**  
   - Separate: 1D strength + volume bursts (not the same as Raising).

4. **Next-day plan**  
   - Re-scores saved wide watch → CONTINUE / WAIT / FADE style.

## Known root cause: “missed rallies”

- Lists are **ranked shortlists** (top N), not all names up over 1W.
- Scans are **fresh snapshots**; latest JSON **overwrites** (thin history until alert log).
- Recognition is after multi-day evidence; **extended** spikes are easy to see late and poor to buy.
- Examples discussed: MSTC, BALAXI, MMFL-type — in universe but often not in published top N.

## Storage model

| Store | Behaviour |
|--------|-----------|
| `config/*_latest.json` | Latest only (overwrite) |
| `config/raising_prev_symbols.json` | Prior Raising symbols (STILL tag) |
| `config/alert_history.jsonl` | Append live Raising/Filtered alerts |
| `config/backtest_latest.json` | Sample historical rule stats |

## Backtest engine

- Sample universe, 1y Yahoo daily data.
- Signal on **first day** of a new Raising stretch.
- Forward returns +1/+3/+5/+10d; compare all Raising vs Filtered-only.
- Workflow: `.github/workflows/backtest.yml` (manual + weekly).

## Flows: silo vs merge

- **Mostly silo:** each flow → own Telegram.
- **Light merge:** Streamlit reads several JSONs; Brief can show multi-layer; All Actionable runs sequentially but does not fuse logic.
- **Not built yet as core:** full cross-flow interpreter (Smart Digest) — planned free rule-based on Streamlit first.

## OpenRouter / AI (optional)

- Allowed only on **free** path.
- Role: summarise lists + optional news notes; **never invent symbols**.
- Fallback: rule-based digest if no key / free model fails.
- Not a self-training profit agent; outcome log + rule tweaks are real “learning.”

## Mutual funds

- Separate weekly **MF Watch** (`config/mf_watch.yaml`) — curated NAVs + NFO headlines.
- Not mixed into swing CONTINUE logic.

## Operating checklist (human)

```text
1) Read Filtered CONTINUE / Next-day CONTINUE
2) Skip EXTENDED / vertical tip chase
3) Small size + stop always
4) Streamlit = watch; Telegram = detail feeds
5) Review backtest + alert history periodically
```

## Next build priorities (when approved)

1. Free **Smart Digest** on Streamlit (rule-based pack of Raising + Filtered + Wide + Brief).
2. Optional OpenRouter free model behind same digest.
3. Outcome scoring job on `alert_history.jsonl` (did alerts rise/fall after N days?).
4. Stronger liquidity floors / larger Raising recall if timeouts allow.

## Repo

- GitHub: `https://github.com/Sayed632/StockScorecard`
- Primary automation: GitHub Actions workflows under `.github/workflows/`
