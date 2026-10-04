import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_bars(index: pd.DatetimeIndex, seed: int = 0) -> pd.DataFrame:
    """Synthetic OHLCV bars on the given (tz-aware) index."""
    rng = np.random.default_rng(seed)
    close = 100 + rng.normal(0, 1, len(index)).cumsum()
    high = close + rng.uniform(0.1, 1.0, len(index))
    low = close - rng.uniform(0.1, 1.0, len(index))
    open_ = close + rng.normal(0, 0.3, len(index))
    volume = rng.integers(1_000, 10_000, len(index)).astype(float)
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume},
                      index=index)
    df.index.name = "timestamp"
    return df


@pytest.fixture
def daily_bars():
    idx = pd.date_range("2025-01-02 05:00", periods=120, freq="B", tz="UTC")
    return make_bars(idx)


@pytest.fixture
def intraday_bars():
    # Two US sessions of 5-minute bars (14:30–20:55 UTC = 09:30–15:55 ET in winter).
    day1 = pd.date_range("2025-01-06 14:30", "2025-01-06 20:55", freq="5min", tz="UTC")
    day2 = pd.date_range("2025-01-07 14:30", "2025-01-07 20:55", freq="5min", tz="UTC")
    return make_bars(day1.append(day2))
