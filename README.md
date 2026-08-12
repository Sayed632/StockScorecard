# StockScorecard

**Transparent Q-G-V-T Stock Scorecard for Indian Equities**

A clean, open-source implementation of a four-factor stock scoring model inspired by Moneycontrol / MarketsMojo style scorecards.

It produces an **Overall score (0-100)** plus four sub-scores for every stock:

| Factor | Name | What it measures |
|--------|------|------------------|
| **Q** | Quality | Financial strength & quality of earnings (ROE, ROA, leverage, margins, liquidity) |
| **G** | Growth  | Historical financial performance & growth trend (revenue/earnings growth, margin quality) |
| **V** | Valuation | Relative & absolute valuation attractiveness (PE, PB, PEG, PS – higher score = cheaper) |
| **T** | Technical | Price trend & momentum on charts (MAs, momentum, RSI, volume) |

Results are also grouped by **Market Cap** (Large / Mid / Small) and **Sector**.

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/Sayed632/StockScorecard.git
cd StockScorecard

# 2. Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run (scores ~30 liquid NSE stocks by default)
python scripts/run_scorecard.py

# More stocks
python scripts/run_scorecard.py --limit 50

# Custom output path
python scripts/run_scorecard.py --limit 40 --output data/my_scores.csv
```

---

## Sample Output

```
TOP 15 STOCKS BY OVERALL SCORE
symbol       name                          market_cap_bucket  sector              Overall    Q    G    V    T
LAURUSLABS   Laurus Labs Ltd               Mid                Healthcare             72.4  78  85  28  91
...
```

CSV columns include: `symbol, name, sector, industry, market_cap_cr, market_cap_bucket, Overall, Q, G, V, T, pe, pb, roe, ...`

---

## Configuration

Edit `config.yaml`:

```yaml
market_cap_buckets:
  large: 20000   # ≥ 20,000 Cr
  mid: 5000      # 5,000 – 20,000 Cr
  # small < 5,000 Cr

factor_weights:
  Q: 0.30
  G: 0.25
  V: 0.25
  T: 0.20
```

---

## Project Structure

```
StockScorecard/
├── config.yaml
├── requirements.txt
├── README.md
├── scripts/
│   └── run_scorecard.py          # CLI entry point
├── src/
│   ├── data_fetch/
│   │   ├── universe.py           # NSE list + market-cap classification
│   │   ├── prices.py             # yfinance OHLCV
│   │   └── fundamentals.py       # key ratios via yfinance
│   ├── factors/
│   │   ├── quality.py            # Q-Factor
│   │   ├── growth.py             # G-Factor
│   │   ├── valuation.py          # V-Factor
│   │   └── technical.py          # T-Factor
│   └── scoring.py                # orchestration + summary
└── data/                         # generated CSVs (git-ignored)
```

---

## Important Notes

- This is a **simplified, transparent** model. It is **not** a 1:1 copy of Moneycontrol / MarketsMojo (their exact formulas are proprietary).
- Data comes primarily from **Yahoo Finance** via `yfinance`. Coverage and freshness for some Indian small-caps can vary.
- Scores are relative and for educational / research purposes only. **Not investment advice.**
- For production use you can later plug better fundamental sources (Screener.in APIs, paid data vendors, etc.).

---

## Extending the Model

- Improve fundamental data quality (add quarterly results, consistency scores, promoter pledge, etc.).
- Add peer-relative ranking inside each sector.
- Back-test the overall score against future returns.
- Add a simple Streamlit dashboard on top of the CSV output.

---

## License

MIT – use freely, modify, and share.

---

Built for systematic, rules-based research on Indian equities.
