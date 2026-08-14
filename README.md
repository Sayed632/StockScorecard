# StockScorecard

**Automated Swing + Long-term + Dark Horse Decision System for Indian Equities**

Fully aligned with approved User Requirements Specification (URS 1.1).

## What it does

Every day (or multiple times when market conditions require) the system:

1. Automatically decides scanning frequency (1x / 2x / 3x)
2. Scans sectors in parallel (Pharmaceuticals fully implemented – others follow same template)
3. Produces three separate lists:
   - 🟢 **Swing Trade** ideas
   - 🔵 **Long-term Investment** ideas
   - 🦄 **Dark Horse** ideas
4. Sends a clean, emoji-based report to Telegram (`@nsepyscan`)

Header always shows: **📊 StockScorecard | Daily Decision Report**

## Quick Start

```bash
git clone https://github.com/Sayed632/StockScorecard.git
cd StockScorecard

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create your secret file
cp .env.example .env
# Edit .env and add:
# TELEGRAM_BOT_TOKEN=your_new_token
# TELEGRAM_CHAT_ID=@nsepyscan

# Run the full decision system
python scripts/run_decision.py

# Run without sending to Telegram
python scripts/run_decision.py --no-telegram
```

## Project Structure

```
src/
├── orchestrator/          # Frequency decision + main runner
├── sectors/               # One scanner per sector (Pharma complete)
├── engines/               # (reserved for shared engine logic)
├── decision/              # Ranking & final lists
├── delivery/              # Telegram report formatter
├── shared/                # Models (Action, StockIdea, etc.)
├── data_fetch/            # Prices + fundamentals
└── factors/               # Q / G / V / T building blocks
```

## Current Status

| Component                    | Status      |
|-----------------------------|-------------|
| URS 1.1                     | Approved    |
| Architecture                | Approved    |
| Pharmaceuticals             | Implemented |
| Banks & Financial Services  | Implemented |
| Information Technology      | Implemented |
| Automobile & EV             | Implemented |
| Defence & Aerospace         | Implemented |
| Chemicals                   | Implemented |
| FMCG & Consumer             | Implemented |
| Swing / Long-term / Dark Horse | Working  |
| Auto frequency (1x/2x/3x)   | Working     |
| Telegram delivery           | Working     |
| Remaining sectors           | Next batch  |

## Important

- This is a **decision-support tool**, not investment advice.
- Always use stop-losses for swing trades.
- Never commit your real `.env` file.

## License

MIT

## Automated Daily Run (GitHub Actions)

The workflow `.github/workflows/daily_decision.yml` runs automatically on weekdays:

| Slot | IST (approx) | UTC cron |
|------|--------------|----------|
| Pre-open | 08:50 | `20 3 * * 1-5` |
| Post-close | 16:00 | `30 10 * * 1-5` |

### One-time setup (required)

1. Go to the repo → **Settings → Secrets and variables → Actions**
2. Add two repository secrets:
   - `TELEGRAM_BOT_TOKEN` → your bot token from @BotFather
   - `TELEGRAM_CHAT_ID` → `@nsepyscan` (or numeric chat id)
3. The workflow will then post reports automatically.

You can also trigger it manually: **Actions → Daily Decision Report → Run workflow**.
