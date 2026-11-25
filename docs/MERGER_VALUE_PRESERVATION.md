# Merger value preservation (do not lose)

Goal: when folding Claudeown / Stock-Screener-Bot / SwingNifty150 / Sectorial-RRG into **StockScorecard**, keep every **value-adding idea**. Duplicate Telegram noise is optional; **logic and process** must not be forgotten.

Last updated: 2026-11-25

---

## A) Claudeown — value checklist

| Value | What it adds | StockScorecard status |
|-------|----------------|------------------------|
| Early volume (pre-spike) | Catch interest before top-gainer list | **Ported** `early_volume.py` |
| Early volume **follow-up** | Track names after first volume alert | **Gap** — port follow-up next |
| Steady climber (R² trend) | Smooth quality uptrend vs spike junk | **Ported** `steady_climber.py` |
| Top gainers (NSE-style) | Market-wide day leaders | **Covered** by Wide scan (not identical API) |
| Dark horse weekly | Quiet mid-cap momentum + room | **Partial** Brief dark horse; can harden |
| Penny surge + red flags | Caution layer on cheap names | **Partial** `penny_screener` |
| FII/DII scanner | Institutional flow context | **Partial** big_money / FII-DII style |
| MF screener / rankings | Fund-side signals | **Partial** `mf_watch` (curated) |
| Sector early volume | Volume by sector sleeve | **Gap** — optional |
| Swing scan | Multi-day swing candidates | **Covered** Swing Catcher / Decision |
| Intraday scanner | Same-day bursts | **Parked** (free-tier lag) — keep idea documented |
| Ticker maintenance | Universe hygiene | **Covered** weekly tickers / universe refresh |
| Health check | Job heartbeat | **Gap** — lightweight health workflow optional |
| Enrichment cache | Avoid re-enriching same day | **Gap** — useful pattern for news/digest |
| Sector stock lists + pending alerts | Sector-routed alert files | **Idea** — sector niches / heatmap related |
| Run-all-scans | One-click pack | **Covered** All Actionable |
| Framework research | Strategy notes | **Docs only** — not runtime |
| Crypto scanner | Non-NSE | **Out of scope** (document only) |

### Claudeown process values (keep even without full code)

1. **Plain-English scanner headers** (what / honesty limits).  
2. **Enrichment once per day** (cache).  
3. **Follow-up after early signal** (not only first print).  
4. **Separate “caution” vs “quality climber”** pens.  
5. **Universe maintenance** as a scheduled job.

---

## B) Stock-Screener-Bot — value checklist

| Value | What it adds | StockScorecard status |
|-------|----------------|------------------------|
| Multi-screen stack (Piotroski, Magic Formula, Darvas, Slater, Driehaus, Altman, Crash Recovery, Quality, Swing, FII+Promoter) | Fundamental + style diversity | **Gap** as full stack; **idea** = multi-label screens |
| Priority / screen_count scoring | Names hitting several screens rank higher | **Gap** — strong Smart Digest input |
| `performance_log` + weekly performance workflow | Closed-loop learning | **Partial** alert_history + backtest; **adopt pattern** |
| `holdings_history` | Track positions over time | **Gap** — optional for ₹10k journal |
| `swing_strategy.py` rules | Explicit swing playbook in code | **Partial** CONTINUE/WAIT; can document rules |
| Streamlit `app.py` | Single UI for results | **Covered** Streamlit watch (different layout) |

### SSB process values (must not lose)

1. **Multi-factor concurrence** (2+ screens = higher priority).  
2. **Performance log after the fact**.  
3. **Weekly performance job** (habit).  
4. **Holdings history** for real money tracking.

---

## C) SwingNifty150 — value checklist

| Value | What it adds | StockScorecard status |
|-------|----------------|------------------------|
| Focused Nifty150 universe | Liquid, cleaner swing set | **Gap** as dedicated mode — optional `universe=nifty150` |
| `analysis/position.py` | Position sizing / structure | **Gap** — human checklist today |
| Tickertape / market_data helpers | Alt data path | **Optional**; Yahoo remains default free path |
| Daily scan workflow | Simple cadence | **Covered** by existing crons |

### SwingNifty150 process values

1. **Liquid-universe mode** for safer swing.  
2. **Position logic** separate from scanner.

---

## D) Sectorial-RRG — value checklist

| Value | What it adds | StockScorecard status |
|-------|----------------|------------------------|
| RRG-style sector rotation visual | Leading / improving / lagging | **Partial** sector_rotation + heatmap |
| Sector breadth treemap | Breadth at a glance | **Gap** / partial heatmap |
| Sector universe generator | Maintain sector membership | **Partial** sector lists |
| MF screener dashboard | Funds UI | **Partial** mf_watch |

### Sectorial process values

1. **Sector first, stock second**.  
2. **Visual rotation** for non-technical users (wife-friendly).

---

## E) Already strong inside StockScorecard (do not drop)

- Raising + Filtered + EXTENDED / STILL  
- Wide + next-day CONTINUE/WAIT/FADE  
- Backtest engine + `alert_history.jsonl`  
- Rally detector, hot stocks, peer watch, news/context  
- GIFT Nifty, F&O bias helpers  
- IPO / pre-IPO / multibagger / penny modules  
- Project docs: `PROJECT_CONTEXT.md`, `REPO_FLOW_MAP.md`

---

## F) Priority to close real gaps (value-preserving order)

| Priority | Item | Source | Why keep |
|----------|------|--------|----------|
| P0 | Smart Digest (Streamlit) merging all list JSONs | Discussion + SSB UI idea | Stops missed value in noise |
| P0 | Early volume **follow-up** | Claudeown | Don’t lose second-day confirmation |
| P1 | Multi-screen **priority score** (lightweight) | SSB | Confluence = value |
| P1 | Weekly **performance** on alert_history | SSB | Learning loop |
| P1 | Streamlit sections: Early Volume + Steady Climber | Ports | Value already computed |
| P2 | Dark horse rules hardened | Claudeown | Mid-cap quiet strength |
| P2 | Nifty150 liquid mode flag | SwingNifty150 | Safer swing sleeve |
| P2 | Sector breadth visual refresh | Sectorial-RRG | Sector value |
| P3 | Enrichment cache pattern | Claudeown | Efficiency |
| P3 | Holdings journal (simple JSON) | SSB | ₹10k accountability |
| — | Intraday high-freq | Claudeown | Keep documented; don’t prioritize free tier |
| — | Crypto | Claudeown | Explicit non-goal |

---

## G) Rule for future merges

```text
1) List value in this file first
2) Mark Covered / Partial / Gap / Out of scope
3) Port Gap only if it adds signal or process (not duplicate Telegram)
4) Prefer JSON + Streamlit digest over another silo channel
```

---

## H) One-line merger principle

**Merge ideas and feedback loops into StockScorecard; do not merge every silo message.**
