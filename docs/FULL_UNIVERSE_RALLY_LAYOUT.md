# Full-universe rally scan layout

## Goal
Scan as much of NSE as practical → rank **rally stocks** → Telegram shortlist
(so names like CMLL are not missed only because they were absent from a small sector list).

## Pipeline

```
┌─────────────────────────────┐
│ 1. Symbol master            │
│  NSE EQUITY_L.csv (cache)   │
│  + tickers.yaml             │
│  + broad_universe.yaml      │
│  + sector files             │
│  + force list (CMLL, …)     │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│ 2. Stage A – parallel light │
│  Yahoo history (batch)      │
│  3D / 5D / 10D returns      │
│  volume vs 20D avg          │
│  distance to 60D high       │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│ 3. Stage B – classify       │
│  🌱 Fresh rally             │
│  📈 Continuation            │
│  🔥 Extended (caution)      │
└─────────────┬───────────────┘
              ▼
┌─────────────────────────────┐
│ 4. Deliver                  │
│  Telegram 🚀 RALLY DETECTOR │
│  Optional: feed Daily Brief │
└─────────────────────────────┘
```

## Limits (honest)
- Not every tick of every stock (no paid market data firehose).
- Cap per run (e.g. 800–1500 names) under GitHub Actions time/rate limits.
- New IPOs: weekly ticker sync + NSE master refresh reduces misses.

## Ops
- Workflow: Rally Detector (multi times / day)
- Manual: Actions → Rally Detector → Run workflow
- Add urgent symbols to config/broad_universe.yaml
