import numpy as np
import pytest

from indicators.custom.vwap_band import vwap_band


def _tp(df):
    return (df["high"] + df["low"] + df["close"]) / 3


def test_session_vwap_resets_each_session(intraday_bars):
    out = vwap_band(intraday_bars, anchor="session")
    tp = _tp(intraday_bars)
    day2 = intraday_bars.index.normalize() == intraday_bars.index[-1].normalize()
    first_of_day2 = intraday_bars.index[day2][0]
    # First bar of each session: VWAP is just that bar's typical price.
    assert out["VWAP"].iloc[0] == pytest.approx(tp.iloc[0])
    assert out.loc[first_of_day2, "VWAP"] == pytest.approx(tp.loc[first_of_day2])
    # Later bars are a cumulative blend, not the bar's own typical price.
    assert out["VWAP"].iloc[10] != pytest.approx(tp.iloc[10])


def test_session_vwap_collapses_on_daily_bars(daily_bars):
    # The regression the rolling anchor exists to avoid.
    out = vwap_band(daily_bars, anchor="session")
    np.testing.assert_allclose(out["VWAP"], _tp(daily_bars))


def test_rolling_vwap_on_daily_bars(daily_bars):
    out = vwap_band(daily_bars, anchor="rolling", period=20)
    tp = _tp(daily_bars)
    assert not np.allclose(out["VWAP"].iloc[20:], tp.iloc[20:])
    vol = daily_bars["volume"]
    expected = (tp * vol).iloc[-20:].sum() / vol.iloc[-20:].sum()
    assert out["VWAP"].iloc[-1] == pytest.approx(expected)
    assert (out["VWAP_UPPER"].iloc[1:] >= out["VWAP"].iloc[1:]).all()


def test_bad_anchor_rejected(daily_bars):
    with pytest.raises(ValueError):
        vwap_band(daily_bars, anchor="weekly")
