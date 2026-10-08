import json
import os
import subprocess
import sys

from indicators.engine import IndicatorEngine


def test_repeated_indicator_gets_suffixed_columns(daily_bars):
    engine = IndicatorEngine(daily_bars).add_bbands(length=20).add_bbands(length=10)
    keys = [m["key"] for m in engine._indicator_meta]
    assert keys == ["BB_UPPER", "BB_MID", "BB_LOWER", "BB_UPPER_2", "BB_MID_2", "BB_LOWER_2"]
    # The second call must not overwrite the first one's values.
    assert not engine.df["BB_UPPER"].equals(engine.df["BB_UPPER_2"])


def test_repeated_custom_indicator_suffixed(daily_bars):
    engine = (IndicatorEngine(daily_bars)
              .add_vwap_band(anchor="rolling")
              .add_vwap_band(anchor="rolling", period=5))
    assert {"VWAP", "VWAP_2", "VWAP_UPPER_2", "VWAP_LOWER_2"} <= set(engine.df.columns)
    engine = IndicatorEngine(daily_bars).add_triple_ma().add_triple_ma()
    assert {"TMA_BUY", "TMA_BUY_2", "TMA_ALIGN_2"} <= set(engine.df.columns)


def test_auto_color_is_stable_across_processes(daily_bars):
    # hash() is salted per process; run the lookup in a fresh interpreter to prove it isn't used.
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    code = ("import pandas as pd; from indicators.engine import IndicatorEngine; "
            "print(IndicatorEngine(pd.DataFrame())._auto_color('EMA_20'))")
    other = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                           check=True, cwd=backend_dir)
    assert other.stdout.strip() == IndicatorEngine(daily_bars)._auto_color("EMA_20")


def test_serialize_shape(daily_bars):
    payload = IndicatorEngine(daily_bars).add_rsi().add_triple_ma().serialize()
    candle = payload["candles"][0]
    assert "timestamp" not in candle and "index" not in candle
    assert isinstance(candle["time"], int)
    assert candle["time"] == int(daily_bars.index[0].timestamp())
    assert candle["RSI_14"] is None                       # warm-up NaN → None
    assert isinstance(payload["candles"][-1]["RSI_14"], float)
    assert isinstance(payload["candles"][-1]["TMA_ALIGN"], int)
    json.dumps(payload)                                   # plain-JSON serialisable


# ── New indicators ────────────────────────────────────────────────────────────

def test_new_indicators_columns_and_suffix(daily_bars):
    engine = (IndicatorEngine(daily_bars)
              .add_adx().add_keltner().add_mfi().add_obv().add_cmf().add_market_regime()
              .add_adx(length=10))
    keys = [m["key"] for m in engine._indicator_meta]
    assert keys == ["ADX_14", "DMP_14", "DMN_14", "KC_UPPER", "KC_MID", "KC_LOWER", "MFI_14",
                    "OBV", "OBV_EMA", "CMF_20", "MRD_REGIME", "ADX_10", "DMP_10", "DMN_10"]
    assert set(keys) <= set(engine.df.columns)
    regime = engine.df["MRD_REGIME"].dropna()
    assert len(regime) and set(regime.unique()) <= {-1.0, 0.0, 1.0, 2.0}


def test_volume_indicators_accept_integer_volume(daily_bars):
    df = daily_bars.copy()
    df["volume"] = df["volume"].astype("int64")
    engine = IndicatorEngine(df).add_obv().add_mfi().add_cmf()
    for col in ("OBV", "OBV_EMA", "MFI_14", "CMF_20"):
        assert engine.df[col].dtype.kind == "f", col
        assert engine.df[col].notna().any(), col


# ── Combo signals ─────────────────────────────────────────────────────────────

def test_combo_signals_never_look_ahead():
    import pandas as pd
    from tests.conftest import make_bars
    from indicators.custom.combo_signals import SIGNAL_RULES, combo_signals

    df = make_bars(pd.date_range("2023-01-02", periods=400, freq="B", tz="UTC"), seed=3)
    cut = 300
    for combo in SIGNAL_RULES:
        full = combo_signals(df, combo, anchor="rolling")
        part = combo_signals(df.iloc[:cut], combo, anchor="rolling")
        pd.testing.assert_frame_equal(full.iloc[:cut], part, obj=combo)
        buy, sell = full.iloc[:, 0], full.iloc[:, 1]
        assert not (buy.notna() & sell.notna()).any(), combo


def test_combo_signals_meta_are_scatter_markers(daily_bars):
    engine = IndicatorEngine(daily_bars).add_combo_signals("ttp", anchor="rolling")
    assert [(m["key"], m["type"], m["pane"]) for m in engine._indicator_meta] == [
        ("SIG_TTP_BUY", "scatter", 0), ("SIG_TTP_SELL", "scatter", 0)]
