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
