import asyncio
from types import SimpleNamespace

import pandas as pd
import pytest

from data.source import AlpacaStream, DataSource
from indicators.custom.combo_signals import SIGNAL_RULES, combo_signals
from indicators.custom.vwap_band import vwap_band
from markets import from_alpaca_crypto, is_crypto, market_of, to_alpaca_crypto
from tests.conftest import make_bars


# ── symbols ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("sym, crypto", [
    ("BTC-USD", True), ("eth-usd", True), ("BTC/USD", True),
    ("SPY", False), ("BRK-B", False), ("USD", False),
])
def test_is_crypto(sym, crypto):
    assert is_crypto(sym) is crypto
    assert market_of(sym) == ("crypto" if crypto else "stocks")


def test_alpaca_symbol_round_trip():
    assert to_alpaca_crypto("btc-usd") == "BTC/USD"
    assert from_alpaca_crypto("BTC/USD") == "BTC-USD"
    assert from_alpaca_crypto(to_alpaca_crypto("SOL-USD")) == "SOL-USD"


# ── UTC-anchored VWAP ─────────────────────────────────────────────────────────

def test_utc_vwap_resets_at_utc_midnight():
    # 24/7 hourly bars across three UTC days.
    df = make_bars(pd.date_range("2025-01-06 00:00", periods=72, freq="h", tz="UTC"))
    out = vwap_band(df, anchor="utc")
    tp = (df["high"] + df["low"] + df["close"]) / 3
    for midnight in ("2025-01-07 00:00", "2025-01-08 00:00"):
        ts = pd.Timestamp(midnight, tz="UTC")
        assert out.loc[ts, "VWAP"] == pytest.approx(tp.loc[ts])
    # 05:00 UTC is midnight in New York — no reset there for the UTC anchor.
    ts = pd.Timestamp("2025-01-07 05:00", tz="UTC")
    assert out.loc[ts, "VWAP"] != pytest.approx(tp.loc[ts])


# Every rule, not just the VWAP ones: 24/7 hourly bars are where crypto runs them.
@pytest.mark.parametrize("combo", list(SIGNAL_RULES))
def test_utc_anchor_has_no_lookahead(combo):
    df = make_bars(pd.date_range("2025-01-06", periods=400, freq="h", tz="UTC"), seed=3)
    full = combo_signals(df, combo, anchor="utc")
    cut = 300
    head = combo_signals(df.iloc[:cut], combo, anchor="utc")
    pd.testing.assert_frame_equal(full.iloc[:cut], head)


# ── crypto bars ───────────────────────────────────────────────────────────────

class _FakeCryptoClient:
    def __init__(self, df):
        self.df, self.request = df, None

    def get_crypto_bars(self, request):
        self.request = request
        return SimpleNamespace(df=self.df)


def _crypto_frame(n=5):
    ts = pd.date_range("2025-01-06", periods=n, freq="h", tz="UTC")[::-1]
    idx = pd.MultiIndex.from_arrays([["BTC/USD"] * n, ts], names=["symbol", "timestamp"])
    return pd.DataFrame({"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 0.25}, index=idx)


def test_crypto_bars_come_from_alpaca_crypto_whatever_the_provider():
    from alpaca.common.enums import Sort
    fake = _FakeCryptoClient(_crypto_frame())
    ds = DataSource(provider="yfinance")
    ds._alpaca_crypto = fake
    out = ds.get_bars("btc-usd", "1Hour", limit=3)
    assert fake.request.symbol_or_symbols == "BTC/USD"
    assert fake.request.sort == Sort.DESC
    assert len(out) == 3 and out.index.is_monotonic_increasing


def test_crypto_bars_fall_back_to_yahoo(monkeypatch):
    ds = DataSource()
    ds._alpaca_crypto = _FakeCryptoClient(pd.DataFrame([]))       # empty → ValueError
    sentinel = make_bars(pd.date_range("2025-01-06", periods=3, freq="h", tz="UTC"))
    monkeypatch.setattr(ds, "_get_bars_yfinance", lambda s, tf, limit: sentinel)
    pd.testing.assert_frame_equal(ds.get_bars("BTC-USD", "1Hour", limit=3), sentinel)


# ── live crypto bars ──────────────────────────────────────────────────────────

def test_crypto_stream_maps_symbol_and_keeps_fractional_volume(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "s")
    got = []
    stream = AlpacaStream(on_bar=got.append, kind="crypto")
    assert stream._wire(["BTC-USD"]) == ["BTC/USD"]
    bar = SimpleNamespace(symbol="BTC/USD", timestamp=pd.Timestamp("2025-01-06 12:00", tz="UTC"),
                          open=1, high=2, low=0.5, close=1.5, volume=0.0123)
    asyncio.run(stream._handle_bar(bar))
    assert got[0]["symbol"] == "BTC-USD"
    assert got[0]["volume"] == pytest.approx(0.0123)


def test_subscribe_routes_by_market(monkeypatch):
    import ws.stream as stream
    calls = []
    for market, ch in stream.CHANNELS.items():
        monkeypatch.setattr(ch, "subscribe", lambda sym, m=market: calls.append((m, sym)))
    stream.subscribe("btc-usd")
    stream.subscribe("aapl")
    assert calls == [("crypto", "BTC-USD"), ("stocks", "AAPL")]
