import pandas as pd
import numpy as np


def vwap_band(df: pd.DataFrame, std_mult: float = 2.0, period: int = 20) -> pd.DataFrame:
    """
    Anchored VWAP with dynamic standard-deviation bands.

    Columns added:
        VWAP        — volume-weighted average price (session-cumulative)
        VWAP_UPPER  — VWAP + std_mult * rolling stddev of typical price
        VWAP_LOWER  — VWAP - std_mult * rolling stddev of typical price
    """
    tp = (df["high"] + df["low"] + df["close"]) / 3

    cum_vol    = df["volume"].cumsum()
    cum_tp_vol = (tp * df["volume"]).cumsum()

    vwap = cum_tp_vol / cum_vol
    rolling_std = tp.rolling(window=period, min_periods=1).std()

    result = pd.DataFrame(index=df.index)
    result["VWAP"]       = vwap
    result["VWAP_UPPER"] = vwap + std_mult * rolling_std
    result["VWAP_LOWER"] = vwap - std_mult * rolling_std
    return result
