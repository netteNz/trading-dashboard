import pandas as pd
import numpy as np


def triple_ma(
    df: pd.DataFrame,
    fast: int = 3,
    mid: int = 7,
    slow: int = 20,
) -> pd.DataFrame:
    """
    Triple Moving Average Crossover — trend + signal overlay.

    Buy  signal: fast SMA crosses above mid SMA, confirmed by mid > slow.
    Sell signal: fast SMA crosses below mid SMA, confirmed by mid < slow.

    Args:
        df:   OHLCV DataFrame
        fast: Fast SMA period  (default 3)
        mid:  Medium SMA period (default 7)
        slow: Slow SMA period   (default 20)

    Returns:
        DataFrame with columns:
            TMA_3     — fast SMA, price scale
            TMA_7     — mid SMA,  price scale
            TMA_20    — slow SMA, price scale
            TMA_ALIGN — +1 bull (fast>mid>slow), -1 bear, 0 mixed
            TMA_BUY   — close price on buy-signal bar, NaN elsewhere
            TMA_SELL  — close price on sell-signal bar, NaN elsewhere
    """
    close = df["close"]

    sma_fast = close.rolling(fast,  min_periods=fast).mean()
    sma_mid  = close.rolling(mid,   min_periods=mid).mean()
    sma_slow = close.rolling(slow,  min_periods=slow).mean()

    # ── Crossover detection (1-bar event, no lookahead) ───────────────────
    prev_fast = sma_fast.shift(1)
    prev_mid  = sma_mid.shift(1)

    cross_up = (prev_fast <= prev_mid) & (sma_fast > sma_mid)
    cross_dn = (prev_fast >= prev_mid) & (sma_fast < sma_mid)

    # ── Regime filter: mid must confirm direction against slow ─────────────
    bull_regime = sma_mid > sma_slow
    bear_regime = sma_mid < sma_slow

    buy_signal  = cross_up & bull_regime
    sell_signal = cross_dn & bear_regime

    # ── Full alignment state ───────────────────────────────────────────────
    bull_align = (sma_fast > sma_mid) & (sma_mid > sma_slow)
    bear_align = (sma_fast < sma_mid) & (sma_mid < sma_slow)
    align = np.where(bull_align, 1, np.where(bear_align, -1, 0))

    result = pd.DataFrame(index=df.index)
    result[f"TMA_{fast}"]  = sma_fast
    result[f"TMA_{mid}"]   = sma_mid
    result[f"TMA_{slow}"]  = sma_slow
    result["TMA_ALIGN"]    = align
    result["TMA_BUY"]      = np.where(buy_signal,  close, np.nan)
    result["TMA_SELL"]     = np.where(sell_signal, close, np.nan)
    return result
