"""
T-Factor: Price Trend on Technical Charts
Higher score = stronger uptrend / momentum.
"""

import pandas as pd
import numpy as np
from typing import Optional


def score_technical(price_df: Optional[pd.DataFrame]) -> float:
    """
    Compute T score 0-100 from daily OHLCV.
    Simple transparent rules:
      - Price vs 50-DMA and 200-DMA
      - 50-DMA vs 200-DMA (golden/death cross style)
      - 3-month and 6-month momentum
      - RSI (14)
      - Volume trend (recent vs longer average)
    """
    if price_df is None or len(price_df) < 60:
        return 50.0

    df = price_df.copy()
    close = df["close"]
    volume = df["volume"]

    scores = []

    # Moving averages
    ma50 = close.rolling(50).mean().iloc[-1]
    ma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else np.nan
    last = close.iloc[-1]

    # Price vs MA50
    if not np.isnan(ma50) and ma50 > 0:
        ratio = last / ma50
        s = np.clip((ratio - 0.85) / 0.30 * 100, 0, 100)
        scores.append(s)

    # Price vs MA200
    if not np.isnan(ma200) and ma200 > 0:
        ratio = last / ma200
        s = np.clip((ratio - 0.80) / 0.40 * 100, 0, 100)
        scores.append(s)

    # MA50 vs MA200 (trend structure)
    if not np.isnan(ma50) and not np.isnan(ma200) and ma200 > 0:
        ratio = ma50 / ma200
        s = np.clip((ratio - 0.90) / 0.20 * 100, 0, 100)
        scores.append(s)

    # Momentum 63 trading days (~3 months)
    if len(close) >= 63:
        ret_3m = close.iloc[-1] / close.iloc[-63] - 1
        s = np.clip((ret_3m + 0.15) / 0.50 * 100, 0, 100)
        scores.append(s)

    # Momentum 126 trading days (~6 months)
    if len(close) >= 126:
        ret_6m = close.iloc[-1] / close.iloc[-126] - 1
        s = np.clip((ret_6m + 0.20) / 0.70 * 100, 0, 100)
        scores.append(s)

    # Simple RSI(14)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    last_rsi = rsi.iloc[-1]
    if not np.isnan(last_rsi):
        # Prefer 40-70 zone, penalize extremes a bit
        if 45 <= last_rsi <= 70:
            s = 80 + (last_rsi - 45) * 0.5
        elif last_rsi > 70:
            s = 70 - (last_rsi - 70) * 1.5
        else:
            s = last_rsi * 1.2
        scores.append(np.clip(s, 0, 100))

    # Volume trend (recent 20d vs 60d)
    if len(volume) >= 60:
        vol_ratio = volume.tail(20).mean() / volume.tail(60).mean()
        s = np.clip((vol_ratio - 0.6) / 1.0 * 100, 0, 100)
        scores.append(s * 0.6)  # lower weight

    if not scores:
        return 50.0

    return float(np.mean(scores))