import pandas as pd
import numpy as np


def momentum_oscillator(df: pd.DataFrame, period: int = 14, smooth: int = 3) -> pd.DataFrame:
    """
    Custom momentum oscillator: RSI-core with a signal line and histogram.

    Columns added:
        MOM_OSC      — raw oscillator (0–100)
        MOM_SIGNAL   — EMA smoothed signal line
        MOM_HIST     — oscillator minus signal (histogram)
    """
    delta = df["close"].diff()
    gain  = delta.clip(lower=0).ewm(span=period, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(span=period, adjust=False).mean()

    rs  = gain / loss.replace(0, np.nan)
    osc = 100 - (100 / (1 + rs))

    signal = osc.ewm(span=smooth, adjust=False).mean()

    result = pd.DataFrame(index=df.index)
    result["MOM_OSC"]    = osc
    result["MOM_SIGNAL"] = signal
    result["MOM_HIST"]   = osc - signal
    return result


def squeeze_momentum(df: pd.DataFrame, bb_period: int = 20, kc_period: int = 20,
                     bb_mult: float = 2.0, kc_mult: float = 1.5) -> pd.DataFrame:
    """
    Lazybear Squeeze Momentum indicator.

    Columns added:
        SQZ_VAL    — momentum value (histogram)
        SQZ_ON     — True when squeeze is active (BB inside KC)
        SQZ_OFF    — True when squeeze just fired
    """
    close = df["close"]
    high  = df["high"]
    low   = df["low"]

    # Bollinger Bands
    bb_mid   = close.rolling(bb_period).mean()
    bb_std   = close.rolling(bb_period).std()
    bb_upper = bb_mid + bb_mult * bb_std
    bb_lower = bb_mid - bb_mult * bb_std

    # Keltner Channels
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)

    kc_mid   = close.rolling(kc_period).mean()
    atr      = tr.rolling(kc_period).mean()
    kc_upper = kc_mid + kc_mult * atr
    kc_lower = kc_mid - kc_mult * atr

    # Squeeze condition
    sqz_on  = (bb_lower > kc_lower) & (bb_upper < kc_upper)

    # Momentum value (delta of midline regression)
    highest_high = high.rolling(kc_period).max()
    lowest_low   = low.rolling(kc_period).min()
    mid          = (highest_high + lowest_low) / 2
    delta_val    = close - ((mid + kc_mid) / 2)

    # Linear regression of delta over kc_period
    def linreg_series(s, window):
        vals = []
        for i in range(len(s)):
            if i < window - 1:
                vals.append(np.nan)
            else:
                y = s.iloc[i - window + 1: i + 1].values
                x = np.arange(window)
                coef = np.polyfit(x, y, 1)
                vals.append(coef[0] * (window - 1) + coef[1])
        return pd.Series(vals, index=s.index)

    mom_val = linreg_series(delta_val, kc_period)

    result = pd.DataFrame(index=df.index)
    result["SQZ_VAL"] = mom_val
    result["SQZ_ON"]  = sqz_on.astype(float)
    return result
