# Dual scan architecture (approved)

## Path A – FAST (sector niches)
- **Workflows:** `Daily Decision Report` + `Sector Niches (Fast Path)`
- **What:** Each sector module (pharma, metals, banks, IT, defence, chemicals, …)
- **Speed:** High – small universes per sector
- **Telegram:** Daily Decision Report (swing / long-term / dark horse)
- **When:** Several times per trading day

## Path B – BREADTH (full market safety net)
- **Workflow:** `Swing Catcher (Do Not Miss)`
- **What:** ~2000+ symbols from `config/nse_equity_cache.yaml` in parallel
- **Speed:** Lower – many Yahoo calls
- **Telegram:** 🎯 SWING CATCHER – Do Not Miss
- **When:** 2× per trading day (mid-morning + afternoon)

## How to use
1. Rely on **Path A** for routine swing ideas from known sectors.
2. Check **Path B** so mid-caps outside sector lists (e.g. Aeroflex-style) are less likely missed.
3. Prefer **ACTIONABLE** over **EXTENDED** on Path B.
4. Always use stops; not investment advice.
