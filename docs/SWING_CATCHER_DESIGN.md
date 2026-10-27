# Swing Catcher – Do Not Miss Design

## Goal
Identify **multi-day swing stocks** across a **wide NSE universe** so names like
ONESOURCE / JUSTDIAL / CMLL are not missed only because they were absent from a small sector list.

## Pipeline
1. **Universe** – NSE equity master (cached) + tickers.yaml + broad_universe + sectors + IPO list + **force list**
2. **Parallel scan** – 1D/5D/10D returns, volume vs avg, 20DMA, near 60D high, higher-low
3. **Buckets**
   - 🟢 ACTIONABLE SWING – primary list to act on (with your own stop)
   - 👀 BUILDING – early watch
   - 🔥 EXTENDED – awareness only, high chase risk
4. **Telegram** – `🎯 SWING CATCHER – Do Not Miss` several times per trading day

## vs sector Daily Decision
| Engine | Role |
|--------|------|
| Sector + Q/G/V/T scores | Quality + structured swing/long-term |
| Swing Catcher | Breadth – catch momentum across full universe |

Both should run. Swing Catcher is the **miss-avoidance** layer.

## Ops
- Actions → **Swing Catcher (Do Not Miss)** → Run workflow
- Env: `SWING_CATCHER_MAX` (default 1500), `SWING_CATCHER_WORKERS` (default 22)
- Add permanent misses to `config/broad_universe.yaml` and force list in `nse_universe.py`
