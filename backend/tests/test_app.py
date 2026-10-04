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


def test_indicators_endpoint_lists_params(client):
    body = client.get("/api/indicators").get_json()
    assert "ema" in body["standard"] and "vwap" in body["custom"]
    assert body["params"]["ema"]["length"] == {"type": "int", "min": 1, "max": 500}
