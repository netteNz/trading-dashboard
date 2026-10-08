import numpy as np
import pandas as pd
import pandas_ta as ta

# Histogram colour per regime value (string keys: they travel through JSON).
REGIME_COLORS = {
    "1":  "#3fb950",   # trend up
    "-1": "#f85149",   # trend down
    "2":  "#d29922",   # high volatility
    "0":  "#484f58",   # range
}


def market_regime(df: pd.DataFrame, adx_len: int = 14, rsi_len: int = 14,
                  atr_len: int = 14, vol_window: int = 50, vol_pct: float = 0.85,
                  adx_trend: float = 25.0) -> pd.DataFrame:
    """
    Market Regime Detector: classify each bar so the right combo gets used.

    Columns added:
        MRD_REGIME — 1 trend up (ADX > 25 and RSI > 55), -1 trend down (ADX > 25 and
                     RSI < 45), 2 high volatility (ATR% above its rolling 85th percentile),
                     0 range. NaN while the inputs warm up.

    Trend takes precedence over high volatility: a strong, directional move is
    expected to be volatile. Every input is trailing, so nothing looks ahead.
    """
    close = df["close"]
    adx_df = ta.adx(df["high"], df["low"], close, length=adx_len)
    adx = adx_df[[c for c in adx_df.columns if c.startswith("ADX_")][0]]
    rsi = ta.rsi(close, length=rsi_len)
    atr_pct = ta.atr(df["high"], df["low"], close, length=atr_len) / close * 100
    hi_vol_line = atr_pct.rolling(vol_window).quantile(vol_pct)

    regime = np.select(
        [(adx > adx_trend) & (rsi > 55), (adx > adx_trend) & (rsi < 45), atr_pct > hi_vol_line],
        [1.0, -1.0, 2.0],
        default=0.0,
    )
    warm = adx.notna() & rsi.notna() & hi_vol_line.notna()

    result = pd.DataFrame(index=df.index)
    result["MRD_REGIME"] = pd.Series(regime, index=df.index).where(warm)
    return result
