"""
BUY/SELL confluence markers for the combo presets.

Each rule rebuilds its own inputs from OHLCV, so markers don't depend on which
lines happen to be on the chart. A marker sits on the bar where the rule turns
true (not on every bar while it stays true). Only trailing data is used — every
shift is positive — so a marker never moves once its bar has closed.
"""
import pandas as pd
import pandas_ta as ta

from indicators.custom.momentum import squeeze_momentum
from indicators.custom.vwap_band import vwap_band


# ── helpers ───────────────────────────────────────────────────────────────────

def _onset(cond: pd.Series) -> pd.Series:
    cond = cond.fillna(False).astype(bool)
    return cond & ~cond.shift(1, fill_value=False)


def _cross_above(s: pd.Series, level) -> pd.Series:
    return (s > level) & (s.shift(1) <= (level.shift(1) if isinstance(level, pd.Series) else level))


def _cross_below(s: pd.Series, level) -> pd.Series:
    return (s < level) & (s.shift(1) >= (level.shift(1) if isinstance(level, pd.Series) else level))


def _pick(frame: pd.DataFrame, prefix: str) -> pd.Series:
    return frame[[c for c in frame.columns if c.startswith(prefix)][0]]


def _adx(df, length=14):
    return _pick(ta.adx(df["high"], df["low"], df["close"], length=length), "ADX_")


def _macd_hist(close):
    return _pick(ta.macd(close), "MACDh")


def _bbands(close, length=20, std=2.0):
    bb = ta.bbands(close, length=length, std=std)
    return _pick(bb, "BBL"), _pick(bb, "BBU")


def _vol_float(df):
    return df["volume"].astype(float)


# ── rules: each returns (buy, sell) boolean Series ───────────────────────────

def _ttp(df, **_):
    c = df["close"]
    e9, e21, e55 = ta.ema(c, 9), ta.ema(c, 21), ta.ema(c, 55)
    rsi = ta.rsi(c, 14)
    buy  = (e9 > e21) & (e21 > e55) & _cross_above(rsi, 50)
    sell = (e9 < e21) & (e21 < e55) & _cross_below(rsi, 50)
    return buy, sell


def _tsf(df, **_):
    c = df["close"]
    e20, e50 = ta.ema(c, 20), ta.ema(c, 50)
    adx, hist = _adx(df), _macd_hist(c)
    buy  = (e20 > e50) & (adx > 25) & _cross_above(hist, 0)
    sell = (e20 < e50) & (adx > 25) & _cross_below(hist, 0)
    return buy, sell


def _ksqz(df, **_):
    sq = squeeze_momentum(df)
    fired = (sq["SQZ_ON"] == 0) & (sq["SQZ_ON"].shift(1) == 1)
    return fired & (sq["SQZ_VAL"] > 0), fired & (sq["SQZ_VAL"] < 0)


def _bbrsi(df, **_):
    c = df["close"]
    lower, upper = _bbands(c)
    rsi = ta.rsi(c, 14)
    vol = _vol_float(df)
    spike = vol > 1.5 * vol.rolling(20).mean()
    # Setup on the prior bar, confirmation when this bar closes back inside the band.
    buy  = ((c.shift(1) < lower.shift(1)) & (rsi.shift(1) < 35) & spike.shift(1, fill_value=False)
            & (c > lower))
    sell = ((c.shift(1) > upper.shift(1)) & (rsi.shift(1) > 65) & spike.shift(1, fill_value=False)
            & (c < upper))
    return buy, sell


def _osc(df, **_):
    c = df["close"]
    lower, upper = _bbands(c)
    rsi = ta.rsi(c, 14)
    mfi = ta.mfi(df["high"], df["low"], c, _vol_float(df), length=14)
    return (rsi < 30) & (mfi < 20) & (c <= lower), (rsi > 70) & (mfi > 80) & (c >= upper)


def _tmt(df, **_):
    c = df["close"]
    s50, s100, s200 = ta.sma(c, 50), ta.sma(c, 100), ta.sma(c, 200)
    hist, rsi = _macd_hist(c), ta.rsi(c, 14)
    buy  = (s50 > s100) & (s100 > s200) & (hist > 0) & rsi.between(40, 65)
    sell = (s50 < s100) & (s100 < s200) & (hist < 0) & rsi.between(35, 60)
    return buy, sell


def _wvs(df, **_):
    c = df["close"]
    obv = ta.obv(c, _vol_float(df))
    obv_ema = ta.ema(obv, 21)
    cmf = ta.cmf(df["high"], df["low"], c, _vol_float(df), length=20)
    return (_cross_above(cmf, 0) & (obv > obv_ema)), (_cross_below(cmf, 0) & (obv < obv_ema))


def _vrb(df, anchor="session", **_):
    vw = vwap_band(df, anchor=anchor)
    k = _pick(ta.stoch(df["high"], df["low"], df["close"]), "STOCHk")
    atr = ta.atr(df["high"], df["low"], df["close"], 14)
    calm = atr < atr.rolling(20).mean()
    buy  = (df["low"]  <= vw["VWAP_LOWER"]) & (k < 20) & calm
    sell = (df["high"] >= vw["VWAP_UPPER"]) & (k > 80) & calm
    return buy, sell


def _mburst(df, **_):
    c = df["close"]
    e9, e21 = ta.ema(c, 9), ta.ema(c, 21)
    sq = squeeze_momentum(df)["SQZ_VAL"]
    vol = _vol_float(df)
    active = vol > vol.rolling(20).mean()
    buy  = (e9 > e21) & _cross_above(sq, 0) & active
    sell = (e9 < e21) & _cross_below(sq, 0) & active
    return buy, sell


def _vcs(df, anchor="session", **_):
    c = df["close"]
    vwap = vwap_band(df, anchor=anchor)["VWAP"]
    rsi7 = ta.rsi(c, 7)
    return _cross_above(c, vwap) & (rsi7 > 50), _cross_below(c, vwap) & (rsi7 < 50)


SIGNAL_RULES = {
    "ttp": _ttp, "tsf": _tsf, "ksqz": _ksqz, "bbrsi": _bbrsi, "osc": _osc,
    "tmt": _tmt, "wvs": _wvs, "vrb": _vrb, "mburst": _mburst, "vcs": _vcs,
}


def combo_signals(df: pd.DataFrame, combo: str, anchor: str = "session") -> pd.DataFrame:
    """
    Columns added:
        SIG_<COMBO>_BUY  — close on the bar where the long rule turns true, NaN elsewhere
        SIG_<COMBO>_SELL — close on the bar where the short rule turns true, NaN elsewhere
    """
    if combo not in SIGNAL_RULES:
        raise ValueError(f"unknown combo: {combo!r}")
    buy, sell = SIGNAL_RULES[combo](df, anchor=anchor)
    buy, sell = _onset(buy), _onset(sell)
    both = buy & sell           # contradictory bar: show neither
    buy, sell = buy & ~both, sell & ~both

    name = combo.upper()
    result = pd.DataFrame(index=df.index)
    result[f"SIG_{name}_BUY"]  = df["close"].where(buy)
    result[f"SIG_{name}_SELL"] = df["close"].where(sell)
    return result
