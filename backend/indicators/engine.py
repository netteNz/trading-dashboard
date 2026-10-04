import zlib

import pandas as pd
import numpy as np
import pandas_ta as ta

from indicators.custom.vwap_band import vwap_band
from indicators.custom.momentum  import momentum_oscillator, squeeze_momentum
from indicators.custom.triple_ma import triple_ma


class IndicatorEngine:
    """
    Chainable indicator engine.  All .add_*() methods return self so you
    can chain them builder-style:

        engine = (
            IndicatorEngine(df)
            .add_ema(20).add_ema(50)
            .add_bbands()
            .add_rsi()
            .add_macd()
            .add_vwap_band()
            .add_momentum_oscillator()
        )
        payload = engine.serialize()

    Adding the same indicator twice never overwrites the first one's columns:
    the second call gets a "_2" suffix on every column key ("_3" for the third,
    and so on). The first call keeps the plain key.
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self._indicator_meta: list[dict] = []

    # ── Standard indicators (pandas-ta) ──────────────────────────────────────

    def add_ema(self, length: int = 20, color: str = None) -> "IndicatorEngine":
        col = f"EMA_{length}"
        col += self._suffix(col)
        self.df[col] = ta.ema(self.df["close"], length=length)
        self._indicator_meta.append({"key": col, "type": "line", "pane": 0,
                                     "color": color or self._auto_color(col), "label": f"EMA {length}"})
        return self

    def add_sma(self, length: int = 20, color: str = None) -> "IndicatorEngine":
        col = f"SMA_{length}"
        col += self._suffix(col)
        self.df[col] = ta.sma(self.df["close"], length=length)
        self._indicator_meta.append({"key": col, "type": "line", "pane": 0,
                                     "color": color or self._auto_color(col), "label": f"SMA {length}"})
        return self

    def add_bbands(self, length: int = 20, std: float = 2.0) -> "IndicatorEngine":
        bb = ta.bbands(self.df["close"], length=length, std=std)
        if bb is not None:
            sfx = self._suffix("BB_UPPER")
            upper_col = [c for c in bb.columns if "BBU" in c][0]
            mid_col   = [c for c in bb.columns if "BBM" in c][0]
            lower_col = [c for c in bb.columns if "BBL" in c][0]
            self.df["BB_UPPER" + sfx] = bb[upper_col]
            self.df["BB_MID"   + sfx] = bb[mid_col]
            self.df["BB_LOWER" + sfx] = bb[lower_col]
            for key, label in [("BB_UPPER", "BB Upper"), ("BB_MID", "BB Mid"), ("BB_LOWER", "BB Lower")]:
                self._indicator_meta.append({"key": key + sfx, "type": "line", "pane": 0,
                                             "color": "#64748b", "label": label, "lineStyle": "dashed"})
        return self

    def add_rsi(self, length: int = 14) -> "IndicatorEngine":
        col = f"RSI_{length}"
        col += self._suffix(col)
        self.df[col] = ta.rsi(self.df["close"], length=length)
        self._indicator_meta.append({"key": col, "type": "line", "pane": 1,
                                     "color": "#a78bfa", "label": f"RSI {length}",
                                     "levels": [{"value": 70, "color": "#ef4444"},
                                                {"value": 30, "color": "#22c55e"}]})
        return self

    def add_macd(self, fast: int = 12, slow: int = 26, signal: int = 9) -> "IndicatorEngine":
        macd = ta.macd(self.df["close"], fast=fast, slow=slow, signal=signal)
        if macd is not None:
            sfx = self._suffix("MACD")
            macd_col   = [c for c in macd.columns if c.startswith("MACD_")][0]
            signal_col = [c for c in macd.columns if "MACDs" in c][0]
            hist_col   = [c for c in macd.columns if "MACDh" in c][0]
            self.df["MACD"        + sfx] = macd[macd_col]
            self.df["MACD_SIGNAL" + sfx] = macd[signal_col]
            self.df["MACD_HIST"   + sfx] = macd[hist_col]
            self._indicator_meta.append({"key": "MACD"        + sfx, "type": "line",      "pane": 2, "color": "#38bdf8", "label": "MACD"})
            self._indicator_meta.append({"key": "MACD_SIGNAL" + sfx, "type": "line",      "pane": 2, "color": "#fb923c", "label": "Signal"})
            self._indicator_meta.append({"key": "MACD_HIST"   + sfx, "type": "histogram", "pane": 2, "color": "#6ee7b7", "label": "Hist"})
        return self

    def add_atr(self, length: int = 14) -> "IndicatorEngine":
        col = f"ATR_{length}"
        col += self._suffix(col)
        self.df[col] = ta.atr(self.df["high"], self.df["low"], self.df["close"], length=length)
        self._indicator_meta.append({"key": col, "type": "line", "pane": 3,
                                     "color": "#fbbf24", "label": f"ATR {length}"})
        return self

    def add_stoch(self, k: int = 14, d: int = 3, smooth_k: int = 3) -> "IndicatorEngine":
        stoch = ta.stoch(self.df["high"], self.df["low"], self.df["close"],
                         k=k, d=d, smooth_k=smooth_k)
        if stoch is not None:
            sfx = self._suffix("STOCH_K")
            stoch_k_col = [c for c in stoch.columns if "STOCHk" in c][0]
            stoch_d_col = [c for c in stoch.columns if "STOCHd" in c][0]
            self.df["STOCH_K" + sfx] = stoch[stoch_k_col]
            self.df["STOCH_D" + sfx] = stoch[stoch_d_col]
            self._indicator_meta.append({"key": "STOCH_K" + sfx, "type": "line", "pane": 4, "color": "#34d399", "label": "Stoch K"})
            self._indicator_meta.append({"key": "STOCH_D" + sfx, "type": "line", "pane": 4, "color": "#f87171", "label": "Stoch D"})
        return self

    def add_volume_profile(self) -> "IndicatorEngine":
        """Volume histogram + 20-bar volume MA in their own sub-pane."""
        col = "VOL_MA" + self._suffix("VOL_MA")
        self.df[col] = ta.sma(self.df["volume"], length=20)
        self._indicator_meta.append({"key": "volume", "type": "histogram", "pane": 5,
                                     "color": "#374151", "label": "Volume"})
        self._indicator_meta.append({"key": col,      "type": "line",      "pane": 5,
                                     "color": "#fbbf24", "label": "Vol MA 20"})
        return self

    # ── Custom indicators ─────────────────────────────────────────────────────

    def add_vwap_band(self, std_mult: float = 2.0, period: int = 20,
                      anchor: str = "session") -> "IndicatorEngine":
        sfx = self._suffix("VWAP")
        result = vwap_band(self.df, std_mult=std_mult, period=period, anchor=anchor)
        self._concat(result, sfx)
        label = "VWAP" if anchor == "session" else f"VWAP ({period})"
        self._indicator_meta.append({"key": "VWAP"       + sfx, "type": "line", "pane": 0, "color": "#f0883e", "label": label})
        self._indicator_meta.append({"key": "VWAP_UPPER" + sfx, "type": "line", "pane": 0, "color": "#f0883e44", "label": "VWAP Upper", "lineStyle": "dashed"})
        self._indicator_meta.append({"key": "VWAP_LOWER" + sfx, "type": "line", "pane": 0, "color": "#f0883e44", "label": "VWAP Lower", "lineStyle": "dashed"})
        return self

    def add_momentum_oscillator(self, period: int = 14, smooth: int = 3) -> "IndicatorEngine":
        sfx = self._suffix("MOM_OSC")
        result = momentum_oscillator(self.df, period=period, smooth=smooth)
        self._concat(result, sfx)
        self._indicator_meta.append({"key": "MOM_OSC"    + sfx, "type": "line",      "pane": 6, "color": "#c084fc", "label": "Mom Osc"})
        self._indicator_meta.append({"key": "MOM_SIGNAL" + sfx, "type": "line",      "pane": 6, "color": "#fb923c", "label": "Signal"})
        self._indicator_meta.append({"key": "MOM_HIST"   + sfx, "type": "histogram", "pane": 6, "color": "#6ee7b7", "label": "Hist"})
        return self

    def add_squeeze_momentum(self) -> "IndicatorEngine":
        sfx = self._suffix("SQZ_VAL")
        result = squeeze_momentum(self.df)
        self._concat(result, sfx)
        self._indicator_meta.append({"key": "SQZ_VAL" + sfx, "type": "histogram", "pane": 7, "color": "#818cf8", "label": "Squeeze"})
        self._indicator_meta.append({"key": "SQZ_ON"  + sfx, "type": "line",      "pane": 7, "color": "#ef4444", "label": "Sqz On"})
        return self

    def add_triple_ma(self, fast: int = 3, mid: int = 7, slow: int = 20) -> "IndicatorEngine":
        """Add Triple MA crossover — 3 overlay lines + buy/sell signal markers."""
        sfx = self._suffix("TMA_ALIGN")
        result = triple_ma(self.df, fast=fast, mid=mid, slow=slow)
        self._concat(result, sfx)

        self._indicator_meta.append({"key": f"TMA_{fast}{sfx}", "type": "line", "pane": 0, "color": "#58a6ff", "label": f"SMA {fast}"})
        self._indicator_meta.append({"key": f"TMA_{mid}{sfx}",  "type": "line", "pane": 0, "color": "#f0883e", "label": f"SMA {mid}"})
        self._indicator_meta.append({"key": f"TMA_{slow}{sfx}", "type": "line", "pane": 0, "color": "#bc8cff", "label": f"SMA {slow}"})
        self._indicator_meta.append({"key": "TMA_BUY"   + sfx,  "type": "scatter", "pane": 0, "color": "#3fb950", "label": "TMA Buy"})
        self._indicator_meta.append({"key": "TMA_SELL"  + sfx,  "type": "scatter", "pane": 0, "color": "#f85149", "label": "TMA Sell"})
        self._indicator_meta.append({"key": "TMA_ALIGN" + sfx,  "type": "histogram", "pane": 8, "color": "#3fb950", "label": "TMA Align"})

        return self

    # ── Generic passthrough ───────────────────────────────────────────────────

    def add(self, indicator: str, pane: int = 0, color: str = "#94a3b8", **kwargs) -> "IndicatorEngine":
        """Attach any pandas-ta indicator by name."""
        fn = getattr(ta, indicator, None)
        if fn is None:
            raise ValueError(f"Unknown pandas-ta indicator: {indicator}")
        result = fn(self.df["close"], **kwargs)
        if isinstance(result, pd.DataFrame):
            for col in result.columns:
                self.df[col] = result[col]
                self._indicator_meta.append({"key": col, "type": "line", "pane": pane,
                                             "color": color, "label": col})
        else:
            col = indicator.upper()
            self.df[col] = result
            self._indicator_meta.append({"key": col, "type": "line", "pane": pane,
                                         "color": color, "label": col})
        return self

    # ── Serialization ─────────────────────────────────────────────────────────

    def serialize(self) -> dict:
        df = self.df.replace([np.inf, -np.inf], np.nan)
        df = df.reset_index()

        # Normalise timestamp to Unix seconds (int)
        # pandas 3.x stores DatetimeTZDtype as datetime64[s] (not ns),
        # so .astype(int64) or .view(int64) return seconds, not nanoseconds.
        # Epoch subtraction via total_seconds() is resolution-agnostic.
        _epoch = pd.Timestamp("1970-01-01", tz="UTC")

        def _to_unix(series: pd.Series) -> pd.Series:
            dt = pd.to_datetime(series, utc=True)
            return (dt - _epoch).dt.total_seconds().astype("int64")

        for ts_col in ("timestamp", "index"):
            if ts_col in df.columns:
                df["time"] = _to_unix(df[ts_col])
                break
        # Drop the raw datetime columns: jsonify would otherwise send each one
        # as an HTTP-date string, and NaT can't be serialised at all.
        df = df.drop(columns=[c for c in ("timestamp", "index") if c in df.columns])

        # Object dtype + to_dict boxes every cell as a native Python type,
        # with NaN replaced by None for JSON.
        clean = df.astype(object).where(df.notna(), None).to_dict(orient="records")

        return {
            "candles":    clean,
            "indicators": self._indicator_meta,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _suffix(self, base_key: str) -> str:
        """Return "" if base_key is free, otherwise the first free "_N" suffix."""
        if base_key not in self.df.columns:
            return ""
        n = 2
        while f"{base_key}_{n}" in self.df.columns:
            n += 1
        return f"_{n}"

    def _concat(self, result: pd.DataFrame, sfx: str) -> None:
        if sfx:
            result = result.rename(columns=lambda c: c + sfx)
        self.df = pd.concat([self.df, result], axis=1)

    _COLOR_WHEEL = [
        "#38bdf8", "#34d399", "#fb923c", "#a78bfa",
        "#f472b6", "#fbbf24", "#6ee7b7", "#c084fc",
    ]

    def _auto_color(self, key: str) -> str:
        # crc32, not hash(): Python salts str hashes per process, which made
        # line colours change on every server restart.
        return self._COLOR_WHEEL[zlib.crc32(key.encode()) % len(self._COLOR_WHEEL)]
