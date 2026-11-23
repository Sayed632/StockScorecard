# Flows from other repos → StockScorecard

## Policy
- **Do not** run every Claudeown scanner as a second Telegram flood.
- **Port unique logic** into StockScorecard modules + one workflow each.
- Prefer existing StockScorecard equivalents when already present.

## Mapping

| Other repo flow | StockScorecard equivalent / port |
|-----------------|----------------------------------|
| Claudeown top_gainers | **Wide Parallel Scan** (1D + volume) |
| Claudeown early_volume | **Early Volume** (ported idea) |
| Claudeown steady_climber | **Steady Climber** (ported idea) |
| Claudeown dark_horse | Daily Brief dark horse + dark-horse style lists |
| Claudeown penny | `run_penny.py` / penny flows |
| Claudeown fii_dii | Big money / FII DII style flows |
| Claudeown mf_screener | **MF Watch** |
| Claudeown swing_scan | Swing Catcher / Daily Decision |
| Claudeown intraday | Parked (free-tier lag; not primary) |
| Claudeown crypto | Out of scope for NSE StockScorecard |
| Stock-Screener-Bot backtest | **Backtest Engine** |
| Sectorial-RRG | Sector rotation + sector heatmap |
| SwingNifty150 | Optional niche; Nifty150 not full system |

## Telegram policy (locked)
Keep existing messages; do not duplicate the same idea twice under two names.
