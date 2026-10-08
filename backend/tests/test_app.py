import json

import pandas as pd
import pytest

import app as app_module
from auth import AuthConfig
from tests.conftest import make_bars


@pytest.fixture
def client(monkeypatch, daily_bars):
    monkeypatch.setattr(app_module.ds, "get_bars", lambda symbol, tf, limit=500: daily_bars.tail(limit))
    monkeypatch.setitem(app_module.app.config, "AUTH", AuthConfig(disabled=True))
    return app_module.app.test_client()


def _chart(client, indicators):
    return client.get("/api/chart/SPY", query_string={"indicators": json.dumps(indicators)})


def test_bad_limit_is_400(client):
    res = client.get("/api/chart/SPY?limit=abc")
    assert res.status_code == 400
    assert "limit" in res.get_json()["error"]


def test_unknown_indicator_and_bad_param_warn(client):
    res = _chart(client, [{"fn": "nope"},
                          {"fn": "ema", "kwargs": {"length": 0}},
                          {"fn": "rsi", "kwargs": {"length": 14}}])
    body = res.get_json()
    assert res.status_code == 200
    assert any("nope" in w for w in body["warnings"])
    assert any("length" in w for w in body["warnings"])
    assert [m["key"] for m in body["indicators"]] == ["RSI_14"]


def test_duplicate_indicator_skipped(client):
    res = _chart(client, [{"fn": "ema", "kwargs": {"length": 20}},
                          {"fn": "ema", "kwargs": {"length": 20.0}}])
    assert [m["key"] for m in res.get_json()["indicators"]] == ["EMA_20"]


def test_vwap_anchor_follows_timeframe():
    df = make_bars(pd.date_range("2025-01-02", periods=40, freq="B", tz="UTC"))
    engine, _ = app_module._build_engine(df, [{"fn": "vwap", "kwargs": {}}], "1Day")
    assert engine._indicator_meta[0]["label"] == "VWAP (20)"
    engine, _ = app_module._build_engine(df, [{"fn": "vwap", "kwargs": {}}], "5Min")
    assert engine._indicator_meta[0]["label"] == "VWAP"
    # 24/7 crypto has no US session: intraday VWAP anchors at the UTC day.
    engine, _ = app_module._build_engine(df, [{"fn": "vwap", "kwargs": {}}], "5Min", "BTC-USD")
    assert engine._indicator_meta[0]["label"] == "VWAP (UTC)"
    engine, _ = app_module._build_engine(df, [{"fn": "vwap", "kwargs": {}}], "1Day", "BTC-USD")
    assert engine._indicator_meta[0]["label"] == "VWAP (20)"


def test_indicators_endpoint_lists_params(client):
    body = client.get("/api/indicators").get_json()
    assert "ema" in body["standard"] and "vwap" in body["custom"]
    assert body["params"]["ema"]["length"] == {"type": "int", "min": 1, "max": 500}


# ── Presets ───────────────────────────────────────────────────────────────────

def test_presets_endpoint_shape(client):
    body = client.get("/api/presets").get_json()
    names = [p["name"] for p in body]
    assert set(names) == set(app_module.INDICATOR_PRESETS)
    kinds = [p["kind"] for p in body]
    assert kinds == sorted(kinds, key=lambda k: k != "core")       # core first
    for p in body:
        assert p["label"] and p["desc"] and p["tf"]
        assert p["markets"] and set(p["markets"]) <= set(app_module.MARKETS), p["name"]
        assert p["indicators"] == app_module.INDICATOR_PRESETS[p["name"]]


def test_every_preset_is_valid():
    # Every preset has display info and only uses registered fns with valid kwargs.
    assert set(app_module.PRESET_INFO) == set(app_module.INDICATOR_PRESETS)
    for name, items in app_module.INDICATOR_PRESETS.items():
        for item in items:
            assert item["fn"] in app_module.INDICATORS, (name, item)
            _, schema = app_module.INDICATORS[item["fn"]]
            for k, v in item["kwargs"].items():
                assert k in schema, (name, item)
                app_module._coerce(item["fn"], k, v, schema[k])


def test_every_preset_builds_without_warnings():
    df = make_bars(pd.date_range("2023-01-02", periods=400, freq="B", tz="UTC"))
    for name, items in app_module.INDICATOR_PRESETS.items():
        engine, warnings = app_module._build_engine(df, items, "1Day")
        assert warnings == [], (name, warnings)
        assert engine._indicator_meta, name


def test_unknown_signal_combo_warns(client):
    body = _chart(client, [{"fn": "sig", "kwargs": {"combo": "nope"}}]).get_json()
    assert any("combo" in w for w in body["warnings"])
    assert body["indicators"] == []


# ── Socket.IO stream status ───────────────────────────────────────────────────

def test_stream_status_sent_on_subscribe(client, monkeypatch):
    import ws.stream as stream
    monkeypatch.setattr(stream, "subscribe", lambda symbol: None)
    monkeypatch.setattr(stream, "unsubscribe", lambda symbol: None)
    sio = app_module.socketio.test_client(app_module.app, flask_test_client=client)
    assert sio.is_connected()
    sio.emit("subscribe", {"symbol": "SPY"})
    events = [e for e in sio.get_received() if e["name"] == "stream_status"]
    payloads = [e["args"][0] for e in events]
    assert {p["market"]: p["status"] for p in payloads} == stream.get_status()
    sio.disconnect()


def test_markets_endpoint(client):
    body = client.get("/api/markets").get_json()
    assert body["crypto"]["default"] == "BTC-USD"
    assert body["stocks"]["default"] in body["stocks"]["watchlist"]


# ── Yahoo lookback ────────────────────────────────────────────────────────────

def test_yf_lookback_fits_limit_and_yahoo_caps():
    from datetime import timedelta
    from data.source import yf_lookback, MAX_LOOKBACK_YF

    # 500 daily bars ≈ 2 years of trading days, not the old fixed 5 years.
    assert timedelta(days=500 * 7 / 5) < yf_lookback("1Day", 500) < timedelta(days=365 * 3)
    # Grows with the limit, never past Yahoo's intraday caps.
    assert yf_lookback("1Day", 5000) > yf_lookback("1Day", 500)
    for tf, cap in MAX_LOOKBACK_YF.items():
        assert yf_lookback(tf, 5000) <= cap, tf
    assert yf_lookback("1Min", 500) == timedelta(days=7)
