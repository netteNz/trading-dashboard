import pandas as pd
import pytest

from data.source import DataSource


class _FakeClient:
    def __init__(self, df):
        self.df = df
        self.request = None

    def get_stock_bars(self, request):
        self.request = request
        return type("Resp", (), {"df": self.df})()


def _alpaca_frame(n=5):
    ts = pd.date_range("2025-01-06", periods=n, freq="W-MON", tz="UTC")[::-1]   # newest first
    idx = pd.MultiIndex.from_arrays([["SPY"] * n, ts], names=["symbol", "timestamp"])
    return pd.DataFrame({"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 100.0}, index=idx)


def test_request_params_and_ordering(monkeypatch):
    from alpaca.common.enums import Sort
    from alpaca.data.enums import DataFeed
    from alpaca.data.timeframe import TimeFrameUnit

    monkeypatch.delenv("ALPACA_FEED", raising=False)
    fake = _FakeClient(_alpaca_frame())
    ds = DataSource(provider="alpaca")
    ds._alpaca = fake
    out = ds.get_bars("spy", "1Week", limit=3)

    req = fake.request
    assert req.sort == Sort.DESC
    assert req.feed == DataFeed.IEX
    assert req.timeframe.unit_value == TimeFrameUnit.Week
    assert len(out) == 3
    assert out.index.is_monotonic_increasing                        # re-sorted ascending
    assert out.index[-1] == pd.Timestamp("2025-02-03", tz="UTC")    # newest bar kept


def test_empty_response_raises():
    ds = DataSource(provider="alpaca")
    ds._alpaca = _FakeClient(pd.DataFrame([]))
    with pytest.raises(ValueError, match="No data"):
        ds.get_bars("SPY", "5Min", limit=10)
