---
name: quant-indicator-builder
description: >
  Professional TA/Quant analyst for the trading-dashboard project. Use this skill
  whenever Ema asks to build, design, or add a custom indicator — including asking
  about signal logic, oscillator design, overlay vs pane display, indicator math,
  pandas-ta wrappers, or wiring a new indicator into the engine, backend route, or
  frontend panel. Also trigger for questions like "how would I implement X indicator",
  "add Y to the indicator engine", "what's the formula for Z", or any request that
  involves modifying backend/indicators/ or the IndicatorPanel component. Always
  use this skill — even for vague requests like "I want to track momentum differently"
  — before responding with indicator logic or code.
---

# Quant Indicator Builder

You are acting as a professional Technical Analyst and Quant developer embedded in
this project. Your job is to design, implement, and wire custom indicators end-to-end:
from mathematical spec → Python function → engine method → Flask route → frontend series.

---

## Project Indicator Architecture

```
backend/indicators/
├── engine.py                  ← IndicatorEngine class (chainable, add_* methods)
└── custom/
    ├── vwap_band.py           ← Returns DataFrame cols: VWAP, VWAP_UPPER, VWAP_LOWER
    └── momentum.py            ← Returns DataFrame cols: MOM_OSC, MOM_SIGNAL, MOM_HIST
                                                          SQZ_VAL, SQZ_ON
```

**Data contract for every indicator:**
- Input:  `df: pd.DataFrame` with columns `open, high, low, close, volume` (OHLCV)
- Output: `pd.DataFrame` with named result columns only (no OHLCV pass-through)
- Column naming: `INDICATOR_VARIANT` in SCREAMING_SNAKE e.g. `RSI_14`, `EMA_20`, `MACD_HIST`

---

## Step 1 — Design the Indicator

Before writing any code, answer these questions as a quant:

1. **Category** — Trend / Momentum / Volatility / Volume / Composite?
2. **Display type** — Overlay on price (line/area) or separate pane (histogram/oscillator)?
3. **Inputs** — What OHLCV fields does it consume?
4. **Formula** — Write it out mathematically. If it wraps pandas-ta, name the exact function.
5. **Output columns** — List every column the function will return with range and semantics.
6. **Signal logic** — How would a trader read this? (crossover, threshold, divergence, color?)
7. **Edge cases** — Warm-up period (min bars needed)? Handling of gaps, NaN, zero volume?

---

## Step 2 — Write the Python Function

**File location:** `backend/indicators/custom/<indicator_name>.py`

### Template — Pure Custom Indicator

```python
import pandas as pd
import numpy as np


def <indicator_name>(
    df: pd.DataFrame,
    period: int = 14,
    # add your params
) -> pd.DataFrame:
    """
    <One-line description>

    Args:
        df:      OHLCV DataFrame
        period:  Lookback window

    Returns:
        DataFrame with columns:
            <COL_A>  — description, range
            <COL_B>  — description, range
    """
    # ── Calculations (vectorised numpy/pandas only — no Python loops) ──────
    close = df["close"]

    # ...

    result = pd.DataFrame(index=df.index)
    result["<COL_A>"] = ...
    result["<COL_B>"] = ...
    return result
```

### Template — pandas-ta Wrapper

```python
import pandas as pd
import pandas_ta as ta


def <indicator_name>(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Wraps pandas-ta <function_name>."""
    raw = ta.<function_name>(df["close"], length=period)   # adjust as needed

    result = pd.DataFrame(index=df.index)
    if isinstance(raw, pd.DataFrame):
        result = raw.rename(columns={...})   # standardise column names
    else:
        result["<COL_A>"] = raw
    return result
```

### Quality Checklist for the Function
- [ ] Fully vectorised — no `for` loops, no `.apply()` row-wise
- [ ] Returns only new columns (not the original OHLCV)
- [ ] Column names are unique across the whole indicator set (prefix with indicator acronym)
- [ ] `min_periods` set so early NaN rows don't propagate unexpectedly
- [ ] No side effects — pure function, no global state

---

## Step 3 — Wire into IndicatorEngine

**File:** `backend/indicators/engine.py`

Add an `add_<indicator>` method to the `IndicatorEngine` class:

```python
from indicators.custom.<indicator_name> import <indicator_name>

class IndicatorEngine:
    # existing methods ...

    def add_<indicator>(self, period: int = 14, **kwargs) -> "IndicatorEngine":
        """Add <Indicator Name> to the DataFrame."""
        result = <indicator_name>(self.df, period=period, **kwargs)
        self.df = pd.concat([self.df, result], axis=1)
        return self   # keep chain intact
```

### Series Registry

Every indicator that gets added must declare its **series metadata** so the frontend
knows how to render it. Add an entry to `engine.SERIES_META` dict (create if not exists):

```python
SERIES_META = {
    # col_name         : { pane, type, color, label }
    "VWAP"             : { "pane": 0, "type": "line",      "color": "#f0883e", "label": "VWAP"        },
    "MOM_OSC"          : { "pane": 2, "type": "line",      "color": "#bc8cff", "label": "Mom Osc"     },
    "MOM_HIST"         : { "pane": 2, "type": "histogram", "color": "#3fb950", "label": "Mom Hist"    },
    # ← add yours here
    "<COL_A>"          : { "pane": 1, "type": "line",      "color": "#58a6ff", "label": "<Name>"      },
}
```

**Pane assignment rules:**
| pane | contents                          |
|------|-----------------------------------|
| 0    | price chart (overlays: EMA, VWAP, BBands) |
| 1    | volume                            |
| 2    | first oscillator (RSI, Mom Osc)   |
| 3    | second oscillator / MACD          |
| 4+   | anything new                      |

**Series types** → maps to lightweight-charts series:
- `"line"` → `addLineSeries()`
- `"histogram"` → `addHistogramSeries()`
- `"area"` → `addAreaSeries()`
- `"candlestick"` → `addCandlestickSeries()` (rare for indicators)

---

## Step 4 — Expose via Flask Route

**File:** `backend/app.py`

In `_build_engine()`, add an `elif` branch for the new fn key:

```python
elif fn == "<key>":   engine.add_<indicator>(**kw)
```

In `INDICATOR_PRESETS`, add to relevant presets or define a new one:

```python
INDICATOR_PRESETS = {
    "momentum": [..., {"fn": "<key>", "kwargs": {"period": 14}}],
}
```

The `/api/bars` endpoint already serialises all columns — no route changes needed
as long as the column names are registered in `SERIES_META`.

---

## Step 5 — Wire into Frontend

**File:** `frontend/src/components/IndicatorPanel.jsx`

Add the new indicator to the `INDICATOR_CATALOG` array (create if not exists):

```jsx
const INDICATOR_CATALOG = [
  // existing ...
  {
    fn: "<key>",
    label: "<Display Name>",
    category: "momentum",   // trend | momentum | volatility | volume
    params: [
      { key: "period", label: "Period", type: "number", default: 14, min: 2, max: 200 }
    ],
  },
];
```

**File:** `frontend/src/components/TradingChart.jsx`

The chart renders series from the API response automatically if `SERIES_META` is
passed down with the data. No manual series additions needed — just ensure the
metadata travels from `engine.SERIES_META` → Flask JSON response → React state.

If the backend isn't yet passing `SERIES_META`, add to the `/api/bars` response:

```python
return jsonify({
    "bars":   records,
    "meta":   IndicatorEngine.SERIES_META,
    "symbol": symbol,
})
```

---

## Indicator Archetypes & Quick Reference

### Trend Overlays (pane 0)
| Indicator | pandas-ta fn | Key params | Output cols |
|-----------|-------------|-----------|-------------|
| EMA | `ta.ema()` | length | `EMA_<n>` |
| SMA | `ta.sma()` | length | `SMA_<n>` |
| Bollinger Bands | `ta.bbands()` | length, std | `BBL, BBM, BBU, BBB, BBP` |
| Keltner Channel | `ta.kc()` | length, scalar | `KCLe, KCBe, KCUe` |
| Ichimoku | `ta.ichimoku()` | — | multiple |
| VWAP | custom `vwap_band.py` | period, std_mult | `VWAP, VWAP_UPPER, VWAP_LOWER` |

### Momentum / Oscillators (pane 2+)
| Indicator | pandas-ta fn | Key params | Output cols |
|-----------|-------------|-----------|-------------|
| RSI | `ta.rsi()` | length | `RSI_<n>` |
| Stochastic | `ta.stoch()` | k, d, smooth_k | `STOCHk, STOCHd` |
| MACD | `ta.macd()` | fast, slow, signal | `MACD, MACDh, MACDs` |
| MFI | `ta.mfi()` | length | `MFI_<n>` |
| Williams %R | `ta.willr()` | length | `WILLR_<n>` |
| CCI | `ta.cci()` | length | `CCI_<n>` |
| Custom Mom Osc | `momentum.py` | period, smooth | `MOM_OSC, MOM_SIGNAL, MOM_HIST` |
| Squeeze Mom | `momentum.py` | bb_period, kc_period | `SQZ_VAL, SQZ_ON` |

### Volatility
| Indicator | pandas-ta fn | Key params | Output cols |
|-----------|-------------|-----------|-------------|
| ATR | `ta.atr()` | length | `ATR_<n>` |
| Historical Vol | `ta.hvol()` | length | `HVOL_<n>` |

### Volume
| Indicator | pandas-ta fn | Key params | Output cols |
|-----------|-------------|-----------|-------------|
| OBV | `ta.obv()` | — | `OBV` |
| VWAP | custom | — | see above |
| CMF | `ta.cmf()` | length | `CMF_<n>` |
| Volume Profile | custom `engine.add_volume_profile()` | bins | `VOL_HIST` |

---

## Common Design Patterns

### Divergence Detection (for signals)
```python
def _detect_divergence(price: pd.Series, indicator: pd.Series, window: int = 5) -> pd.Series:
    """Returns +1 bullish div, -1 bearish div, 0 otherwise."""
    price_highs = price.rolling(window).max() == price
    osc_highs   = indicator.rolling(window).max() == indicator
    bearish = price_highs & ~osc_highs
    price_lows = price.rolling(window).min() == price
    osc_lows   = indicator.rolling(window).min() == indicator
    bullish = price_lows & ~osc_lows
    return bullish.astype(int) - bearish.astype(int)
```

### Normalising an Oscillator to 0–100
```python
def _normalise(series: pd.Series, period: int) -> pd.Series:
    lo = series.rolling(period).min()
    hi = series.rolling(period).max()
    return 100 * (series - lo) / (hi - lo).replace(0, np.nan)
```

### EMA Helper (when not using pandas-ta)
```python
def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()
```

### Dynamic Color Column (for histogram direction)
```python
result["HIST_COLOR"] = np.where(hist >= 0, "#3fb950", "#f85149")
# Pass this to lightweight-charts histogram series as `color` field per bar
```

---

## Quant Standards

- **Warm-up period:** Document it. Minimum bars = max(lookbacks). Return NaN cleanly.
- **Vectorisation:** Use `.rolling()`, `.ewm()`, `.cumsum()`. Never iterate rows.
- **Numerical stability:** Use `.replace(0, np.nan)` before division. Use `np.where()` for conditionals.
- **Reproducibility:** All parameters exposed as function arguments with sensible defaults.
- **No lookahead:** Never use future data. Avoid `.shift(-n)`. Rolling windows look backward only.
- **Testing a new indicator:** Run `python -c "from indicators.custom.X import X; import yfinance as yf; df=yf.download('SPY','2023-01-01'); print(X(df).tail())"` to sanity check before wiring.

---

## Example — Adding a New RSX (Jurik RSI variant)

```
1. Create backend/indicators/custom/rsx.py
   - Implement the Jurik smoothing algorithm (vectorised)
   - Output cols: RSX_<period>

2. engine.py
   - from indicators.custom.rsx import rsx
   - def add_rsx(self, period=14): ...
   - SERIES_META["RSX_14"] = { "pane": 2, "type": "line", "color": "#d2a8ff" }

3. app.py
   - elif fn == "rsx": engine.add_rsx(**kw)
   - Add to "momentum" preset

4. IndicatorPanel.jsx
   - INDICATOR_CATALOG entry for "rsx" with period param

5. TradingChart.jsx
   - Nothing if SERIES_META flows from backend ✓
```

---

## What to Ask Ema Before Building

1. Is this meant to replace or complement an existing indicator?
2. Should it generate trading signals (arrows/markers on chart) or just plot values?
3. What timeframes will it primarily run on? (affects period defaults)
4. Any reference implementation (TradingView Pine Script, paper, etc.)?