# Full-universe parallel swing (no one-by-one adds)

## Policy
Do **not** rely on manually adding each miss (AEROFLEX, ONESOURCE, …).

1. Maintain `config/nse_equity_cache.yaml` (~2000+ NSE symbols from public mirrors + force list)
2. **Swing Catcher** scans this list in **parallel** every trading day
3. Output only movers: ACTIONABLE / BUILDING / EXTENDED
4. Weekly **Universe Refresh** tries to update the cache from GitHub/NSE mirrors

## Limits
- Cache can lag brand-new listings by days until refresh
- Yahoo rate limits → some symbols fail (`data-fail` in Telegram)
- Not tick-by-tick; multi-day swing focus

## Ops
Actions → **Swing Catcher (Do Not Miss)** → Run workflow
