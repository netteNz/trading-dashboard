import pandas as pd
import numpy as np
import pandas_ta as ta

from indicators.custom.vwap_band import vwap_band
from indicators.custom.momentum  import momentum_oscillator, squeeze_momentum


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
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self._indicator_meta: list[dict] = []

    # ── Standard indicators (pandas-ta) ──────────────────────────────────────

    def add_ema(self, length: int = 20, color: str = None) -> "IndicatorEngine":
        col = f"EMA_{length}"
        self.df[col] = ta.ema(self.df["close"], length=length)
        self._indicator_meta.append({"key": col, "type": "line", "pane": 0,
                                     "color": color or self._auto_color(col), "label": f"EMA {length}"})
        return self

    def add_sma(self, length: int = 20, color: str = None) -> "IndicatorEngine":
        col = f"SMA_{length}"
        self.df[col] = ta.sma(self.df["close"], length=length)
        self._indicator_meta.append({"key": col, "type": "line", "pane": 0,
                                     "color": color or self._auto_color(col), "label": f"SMA {length}"})
        return self

    def add_bbands(self, length: int = 20, std: float = 2.0) -> "IndicatorEngine":
        bb = ta.bbands(self.df["close"], length=length, std=std)
        if bb is not None:
            upper_col = [c for c in bb.columns if "BBU" in c][0]
            mid_col   = [c for c in bb.columns if "BBM" in c][0]
            lower_col = [c for c in bb.columns if "BBL" in c][0]
            self.df["BB_UPPER"] = bb[upper_col]
            self.df["BB_MID"]   = bb[mid_col]
            self.df["BB_LOWER"] = bb[lower_col]
            for key, label in [("BB_UPPER", f"BB Upper"), ("BB_MID", "BB Mid"), ("BB_LOWER", "BB Lower")]:
                self._indicator_meta.append({"key": key, "type": "line", "pane": 0,
                                             "color": "#64748b", "label": label, "lineStyle": "dashed"})
        return self

    def add_rsi(self, length: int = 14) -> "IndicatorEngine":
        col = f"RSI_{length}"
        self.df[col] = ta.rsi(self.df["close"], length=length)
        self._indicator_meta.append({"key": col, "type": "line", "pane": 1,
                                     "color": "#a78bfa", "label": f"RSI {length}",
                                     "levels": [{"value": 70, "color": "#ef4444"},
                                                {"value": 30, "color": "#22c55e"}]})
        return self

    def add_macd(self, fast: int = 12, slow: int = 26, signal: int = 9) -> "IndicatorEngine":
        macd = ta.macd(self.df["close"], fast=fast, slow=slow, signal=signal)
        if macd is not None:
            macd_col   = [c for c in macd.columns if c.startswith("MACD_")][0]
            signal_col = [c for c in macd.columns if "MACDs" in c][0]
            hist_col   = [c for c in macd.columns if "MACDh" in c][0]
            self.df["MACD"]        = macd[macd_col]
            self.df["MACD_SIGNAL"] = macd[signal_col]
            self.df["MACD_HIST"]   = macd[hist_col]
            self._indicator_meta.append({"key": "MACD",        "type": "line",      "pane": 2, "color": "#38bdf8", "label": "MACD"})
            self._indicator_meta.append({"key": "MACD_SIGNAL", "type": "line",      "pane": 2, "color": "#fb923c", "label": "Signal"})
            self._indicator_meta.append({"key": "MACD_HIST",   "type": "histogram", "pane": 2, "color": "#6ee7b7", "label": "Hist"})
        return self

    def add_atr(self, length: int = 14) -> "IndicatorEngine":
        col = f"ATR_{length}"
        self.df[col] = ta.atr(self.df["high"], self.df["low"], self.df["close"], length=length)
        self._indicator_meta.append({"key": col, "type": "line", "pane": 3,
                                     "color": "#fbbf24", "label": f"ATR {length}"})
        return self

    def add_stoch(self, k: int = 14, d: int = 3, smooth_k: int = 3) -> "IndicatorEngine":
        stoch = ta.stoch(self.df["high"], self.df["low"], self.df["close"],
                         k=k, d=d, smooth_k=smooth_k)
        if stoch is not None:
            stoch_k_col = [c for c in stoch.columns if "STOCHk" in c][0]
            stoch_d_col = [c for c in stoch.columns if "STOCHd" in c][0]
            self.df["STOCH_K"] = stoch[stoch_k_col]
            self.df["STOCH_D"] = stoch[stoch_d_col]
            self._indicator_meta.append({"key": "STOCH_K", "type": "line", "pane": 4, "color": "#34d399", "label": "Stoch K"})
            self._indicator_meta.append({"key": "STOCH_D", "type": "line", "pane": 4, "color": "#f87171", "label": "Stoch D"})
        return self

    def add_volume_profile(self) -> "IndicatorEngine":
        """Attach a simple volume MA overlay on the main pane"""
        self.df["VOL_MA"] = ta.sma(self.df["volume"], length=20)
        self._indicator_meta.append({"key": "volume", "type": "histogram", "pane": 5,
                                     "color": "#374151", "label": "Volume"})
        self._indicator_meta.append({"key": "VOL_MA",   "type": "line",      "pane": 5,
                                     "color": "#fbbf24", "label": "Vol MA 20"})
        return self

    # ── Custom indicators ─────────────────────────────────────────────────────

    def add_vwap_band(self, std_mult: float = 2.0, period: int = 20) -> "IndicatorEngine":
        result = vwap_band(self.df, std_mult=std_mult, period=period)
        self.df = pd.concat([self.df, result], axis=1)
        self._indicator_meta.append({"key": "VWAP",       "type": "line", "pane": 0, "color": "#f0883e", "label": "VWAP"})
        self._indicator_meta.append({"key": "VWAP_UPPER", "type": "line", "pane": 0, "color": "#f0883e44", "label": "VWAP Upper", "lineStyle": "dashed"})
        self._indicator_meta.append({"key": "VWAP_LOWER", "type": "line", "pane": 0, "color": "#f0883e44", "label": "VWAP Lower", "lineStyle": "dashed"})
        return self

    def add_momentum_oscillator(self, period: int = 14, smooth: int = 3) -> "IndicatorEngine":
        result = momentum_oscillator(self.df, period=period, smooth=smooth)
        self.df = pd.concat([self.df, result], axis=1)
        self._indicator_meta.append({"key": "MOM_OSC",    "type": "line",      "pane": 6, "color": "#c084fc", "label": "Mom Osc"})
        self._indicator_meta.append({"key": "MOM_SIGNAL", "type": "line",      "pane": 6, "color": "#fb923c", "label": "Signal"})
        self._indicator_meta.append({"key": "MOM_HIST",   "type": "histogram", "pane": 6, "color": "#6ee7b7", "label": "Hist"})
        return self

    def add_squeeze_momentum(self) -> "IndicatorEngine":
        result = squeeze_momentum(self.df)
        self.df = pd.concat([self.df, result], axis=1)
        self._indicator_meta.append({"key": "SQZ_VAL", "type": "histogram", "pane": 7, "color": "#818cf8", "label": "Squeeze"})
        self._indicator_meta.append({"key": "SQZ_ON",  "type": "line",      "pane": 7, "color": "#ef4444", "label": "Sqz On"})
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
        df = self.df.copy().replace([np.inf, -np.inf], np.nan)
        df = df.reset_index()

        # Normalise timestamp to Unix seconds (int)
        if "timestamp" in df.columns:
            df["time"] = (
                pd.to_datetime(df["timestamp"], utc=True)
                .astype(np.int64) // 10**9
            )
        elif "index" in df.columns:
            df["time"] = (
                pd.to_datetime(df["index"], utc=True)
                .astype(np.int64) // 10**9
            )

        records = df.to_dict(orient="records")
        # Replace NaN with None for JSON serialisation
        clean = [
            {k: (None if isinstance(v, float) and np.isnan(v) else v)
             for k, v in row.items()}
            for row in records
        ]

        return {
            "candles":    clean,
            "indicators": self._indicator_meta,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    _COLOR_WHEEL = [
        "#38bdf8", "#34d399", "#fb923c", "#a78bfa",
        "#f472b6", "#fbbf24", "#6ee7b7", "#c084fc",
    ]

    def _auto_color(self, key: str) -> str:
        return self._COLOR_WHEEL[hash(key) % len(self._COLOR_WHEEL)]
