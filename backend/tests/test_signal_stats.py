import numpy as np
import pandas as pd
import pytest

import app as app_module
from auth import AuthConfig
from indicators.custom.combo_signals import combo_signals
from indicators.custom.signal_stats import score_markers
from tests.conftest import make_bars


def _frame(close) -> pd.DataFrame:
    close = np.asarray(close, dtype=float)
    idx = pd.date_range("2025-01-02", periods=len(close), freq="B", tz="UTC")
    return pd.DataFrame({"open": close, "high": close + 0.5, "low": close - 0.5,
                         "close": close, "volume": 1000.0}, index=idx)


# ── scorecard ─────────────────────────────────────────────────────────────────

@pytest.fixture
def ramp():
    # Flat at 100 for 20 bars, then +0.1 a bar. High-low is always 1 and no gap
    # beats it, so ATR(14) is exactly 1.
    close = [100.0] * 20 + [100 + 0.1 * i for i in range(20)]
    return _frame(close)


def _mask(df, *positions):
    m = pd.Series(False, index=df.index)
    m.iloc[list(positions)] = True
    return m


def test_score_markers_counts_moves_and_drawdown(ramp):
    buy, sell = _mask(ramp, 20, 35), _mask(ramp, 25)
    s = score_markers(ramp, buy, sell, horizon=10)

    assert s["horizon"] == 10
    # Bar 20 → bar 30: 100 → 101 (+1%); worst low 100.1 - 0.5 → 0.4 ATR against.
    assert s["buy"] == {"n": 1, "open": 1, "hit": 1.0, "median_move_pct": 1.0, "median_mae_atr": 0.4}
    # Sell at 100.5 → 101.5: price rose, a miss; highest high 102.0 → 1.5 ATR against.
    assert s["sell"]["n"] == 1 and s["sell"]["hit"] == 0.0
    assert s["sell"]["median_move_pct"] == pytest.approx(-1.0, abs=0.01)
    assert s["sell"]["median_mae_atr"] == 1.5
    # 30 bars have a full window; closes rose on bars 11–29.
    assert s["base_up"] == pytest.approx(19 / 30, abs=1e-3)


def test_score_markers_only_counts_the_window(ramp):
    buy, sell = _mask(ramp, 20, 35), _mask(ramp, 25)
    s = score_markers(ramp, buy, sell, horizon=10, last=12)     # rows 28–39
    assert s["buy"] == {"n": 0, "open": 1, "hit": None, "median_move_pct": None, "median_mae_atr": None}
    assert s["sell"]["n"] == 0 and s["sell"]["open"] == 0
    assert s["base_up"] == 1.0                                  # rows 28, 29


# ── confirmed RSI divergence ──────────────────────────────────────────────────

def _divergence_close():
    up      = list(np.linspace(100, 103, 30))
    crash   = list(np.linspace(102, 90, 5))           # fast drop: deep RSI low at 90
    bounce  = list(np.linspace(91, 96, 8))
    drift   = list(np.linspace(95.5, 89.5, 12))       # slow drift to a lower low: milder RSI
    recover = list(np.linspace(90.5, 95, 8))
    return up + crash + bounce + drift + recover


def test_rdiv_marks_the_confirmation_bar_only():
    close = _divergence_close()
    df = _frame(close)
    p2 = 30 + 5 + 8 + 12 - 1                          # bar of the lower low
    out = combo_signals(df, "rdiv", anchor="rolling")
    buys = np.flatnonzero(out["SIG_RDIV_BUY"].notna().to_numpy())
    assert list(buys) == [p2 + 3]
    assert out["SIG_RDIV_SELL"].isna().all()
    # Nothing is known before the confirmation bar: truncating there drops it.
    early = combo_signals(df.iloc[:p2 + 3], "rdiv", anchor="rolling")
    assert early["SIG_RDIV_BUY"].isna().all()


# ── /api/chart: warm-up and stats ─────────────────────────────────────────────

@pytest.fixture
def long_client(monkeypatch):
    bars = make_bars(pd.date_range("2023-01-02", periods=500, freq="B", tz="UTC"), seed=3)
    requested = []

    def get_bars(symbol, tf, limit=500):
        requested.append(limit)
        return bars.tail(limit)

    monkeypatch.setattr(app_module.ds, "get_bars", get_bars)
    monkeypatch.setitem(app_module.app.config, "AUTH", AuthConfig(disabled=True))
    return app_module.app.test_client(), requested


def test_chart_fetches_warmup_and_trims(long_client):
    client, requested = long_client
    body = client.get("/api/chart/SPY?limit=100&preset=tmt").get_json()
    assert requested == [100 + app_module.WARMUP_BARS]
    assert len(body["candles"]) == 100
    assert body["candles"][0]["SMA_200"] is not None


def test_chart_stats_per_combo(long_client):
    client, _ = long_client
    body = client.get("/api/chart/SPY?limit=200&preset=ttp").get_json()
    ttp = body["stats"]["TTP"]
    assert ttp["horizon"] == app_module.HORIZON_BARS
    marked = sum(c["SIG_TTP_BUY"] is not None for c in body["candles"])
    assert ttp["buy"]["n"] + ttp["buy"]["open"] == marked
    assert client.get("/api/chart/SPY?limit=200&preset=full").get_json()["stats"] == {}
