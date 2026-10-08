import pandas as pd
import pytest

import data.source as source
from data.source import DataSource
from tests.conftest import make_bars


@pytest.fixture
def counted(monkeypatch):
    """DataSource whose provider fetch is counted; the clock is controllable."""
    clock = {"t": 1000.0}
    monkeypatch.setattr(source.time, "monotonic", lambda: clock["t"])
    ds = DataSource(provider="yfinance")
    calls = []

    def fake(symbol, tf, limit):
        calls.append((symbol, tf, limit))
        return make_bars(pd.date_range("2025-01-02", periods=limit, freq="B", tz="UTC"))

    monkeypatch.setattr(ds, "_get_bars_yfinance", fake)
    return ds, calls, clock


def test_repeat_request_is_served_from_cache(counted):
    ds, calls, _ = counted
    a = ds.get_bars("spy", "1Day", 50)
    b = ds.get_bars("SPY", "1Day", 50)
    assert len(calls) == 1
    pd.testing.assert_frame_equal(a, b)


def test_timeframe_and_limit_are_separate_entries(counted):
    ds, calls, _ = counted
    ds.get_bars("SPY", "1Day", 50)
    ds.get_bars("SPY", "1Hour", 50)
    ds.get_bars("SPY", "1Day", 60)
    assert len(calls) == 3


def test_entry_expires_after_ttl(counted):
    ds, calls, clock = counted
    ds.get_bars("SPY", "5Min", 50)
    clock["t"] += source.CACHE_TTL_DEFAULT - 1
    ds.get_bars("SPY", "5Min", 50)
    assert len(calls) == 1
    clock["t"] += 2
    ds.get_bars("SPY", "5Min", 50)
    assert len(calls) == 2


def test_errors_are_not_cached(monkeypatch):
    ds = DataSource(provider="yfinance")
    calls = []

    def boom(symbol, tf, limit):
        calls.append(1)
        raise ValueError("No data returned")

    monkeypatch.setattr(ds, "_get_bars_yfinance", boom)
    for _ in range(2):
        with pytest.raises(ValueError):
            ds.get_bars("SPY", "1Day", 10)
    assert len(calls) == 2


def test_callers_get_a_copy(counted):
    ds, _, _ = counted
    got = ds.get_bars("SPY", "1Day", 50)
    got["close"] = 0.0
    assert (ds.get_bars("SPY", "1Day", 50)["close"] != 0.0).all()


def test_cache_is_bounded(counted, monkeypatch):
    ds, _, _ = counted
    monkeypatch.setattr(source, "CACHE_MAX", 3)
    for n in range(10, 16):
        ds.get_bars("SPY", "1Day", n)
    assert len(ds._cache) <= 3
