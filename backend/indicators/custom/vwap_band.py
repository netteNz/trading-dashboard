import pandas as pd
import numpy as np

ANCHORS = ("session", "rolling")


def vwap_band(df: pd.DataFrame, std_mult: float = 2.0, period: int = 20,
              anchor: str = "session") -> pd.DataFrame:
    """
    VWAP with dynamic standard-deviation bands.

    anchor="session" — resets at the start of each trading session (US calendar
        day). Correct for intraday bars; a running cumsum across the whole
        fetched history would drift further from price the more days are loaded.
    anchor="rolling" — volume-weighted mean of the last `period` bars. Used for
        daily/weekly bars, where each session is a single bar and a
        session-anchored VWAP would collapse onto the bar's typical price.

    Columns added:
        VWAP        — volume-weighted average price
        VWAP_UPPER  — VWAP + std_mult * rolling stddev of typical price
        VWAP_LOWER  — VWAP - std_mult * rolling stddev of typical price
    """
    if anchor not in ANCHORS:
        raise ValueError(f"anchor must be one of {ANCHORS}, got {anchor!r}")

    tp = (df["high"] + df["low"] + df["close"]) / 3
    tp_vol = tp * df["volume"]

    if anchor == "rolling":
        vwap = (tp_vol.rolling(window=period, min_periods=1).sum()
                / df["volume"].rolling(window=period, min_periods=1).sum())
    else:
        idx = pd.DatetimeIndex(df.index)
        # Data is stored in UTC; convert to US market time before taking the
        # session date so the boundary falls at US midnight, not UTC midnight
        # (matters for any pre/post-market bars that cross the UTC day rollover).
        if idx.tz is not None:
            idx = idx.tz_convert("America/New_York").tz_localize(None)
        session = idx.normalize()

        cum_vol    = df["volume"].groupby(session).cumsum()
        cum_tp_vol = tp_vol.groupby(session).cumsum()
        vwap = cum_tp_vol / cum_vol

    rolling_std = tp.rolling(window=period, min_periods=1).std()

    result = pd.DataFrame(index=df.index)
    result["VWAP"]       = vwap
    result["VWAP_UPPER"] = vwap + std_mult * rolling_std
    result["VWAP_LOWER"] = vwap - std_mult * rolling_std
    return result
