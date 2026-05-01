# Implementation Reference

Full file touch-points for each combo type. Read this when you're ready to code.

---

## Type A — New Preset Only

**Touch points: 2 files**

### 1. `backend/app.py`

Add to `INDICATOR_PRESETS`:
```python
INDICATOR_PRESETS["<key>"] = [
    {"fn": "<fn1>", "kwargs": {...}},
    {"fn": "<fn2>", "kwargs": {...}},
]
```

### 2. `frontend/src/components/IndicatorPanel.jsx`

Add to `AVAILABLE` list (or `PRESETS` section if one exists):
```js
{ fn: "<key>", label: "<Display Name>", params: [] }
```

---

## Type B — New Composite Indicator

**Touch points: 5 files**

### 1. `backend/indicators/custom/<name>.py`
```python
import pandas as pd
import numpy as np
# import pandas_ta as ta  (if wrapping pandas-ta)

def <name>(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    <Description>
    Warm-up: <N> bars
    Output cols: <COL_A> (<range>), <COL_B> (<range>)
    """
    result = pd.DataFrame(index=df.index)
    result["<COL_A>"] = ...
    result["<COL_B>"] = ...
    return result
```

### 2. `backend/indicators/engine.py`

Import at top:
```python
from indicators.custom.<name> import <name>
```

Add method to `IndicatorEngine`:
```python
def add_<name>(self, period: int = 14) -> "IndicatorEngine":
    result = <name>(self.df, period=period)
    self.df = pd.concat([self.df, result], axis=1)
    self._indicator_meta.append({
        "key":   "<COL_A>",
        "type":  "line",        # line | histogram | area
        "pane":  2,             # 0=price, 1=vol, 2+=sub
        "color": "#58a6ff",
        "label": "<Display>",
    })
    # add second meta entry if indicator has multiple series
    return self
```

### 3. `backend/app.py`

In `_build_engine()`:
```python
elif fn == "<key>": engine.add_<name>(**kw)
```

Add to relevant preset(s):
```python
INDICATOR_PRESETS["<preset>"].append({"fn": "<key>", "kwargs": {}})
```

### 4. `frontend/src/components/IndicatorPanel.jsx`

In `AVAILABLE`:
```js
{
  fn: "<key>",
  label: "<Display Name>",
  params: [
    { key: "period", label: "Period", type: "number", default: 14, min: 2, max: 200 }
  ]
}
```

### 5. Smoke test (run from `backend/`)
```bash
python -c "
import yfinance as yf
import pandas as pd
df = yf.Ticker('SPY').history(period='1y', interval='1d')
df.columns = [c.lower() for c in df.columns]
from indicators.custom.<name> import <name>
out = <name>(df)
print(out.tail())
print('NaN count:', out.isna().sum())
"
```

---

## Type C — Session-Aware / Stateful System

**Only needed for ORB, multi-TF indicators, or regime systems with external state.**

Structure:
```
backend/indicators/systems/<name>/
├── __init__.py
└── compute.py      ← def compute(df, **kwargs) -> pd.DataFrame
```

`compute.py` signature must match the engine's `add_*` convention:
```python
def compute(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """Returns only new columns, no OHLCV pass-through."""
    ...
```

Wire into engine:
```python
from indicators.systems.<name>.compute import compute as <name>_compute

def add_<name>(self, **kwargs) -> "IndicatorEngine":
    result = <name>_compute(self.df, **kwargs)
    self.df = pd.concat([self.df, result], axis=1)
    # append meta entries ...
    return self
```

---

## Color Palette (use these for new indicators)

```python
# Blues (trend lines)
"#58a6ff"   # bright blue — primary trend
"#388bfd"   # mid blue — secondary trend
"#1f6feb"   # deep blue — tertiary / slow MA

# Purples (momentum)
"#bc8cff"   # bright purple — oscillator line
"#8957e5"   # deep purple — signal line

# Greens (positive / bullish)
"#3fb950"   # positive histogram
"#2ea043"   # buy signal

# Reds (negative / bearish)
"#f85149"   # negative histogram
"#da3633"   # sell signal

# Yellows / Oranges (volatility, bands)
"#f0883e"   # VWAP, ATR
"#e3b341"   # BB bands, channel boundaries

# Neutral
"#8b949e"   # secondary lines, signal line
"#30363d"   # zero lines, reference levels
```

---

## Quick Combo → Preset Mapping

| Combo key | Type | New Python? | Est. time |
|-----------|------|-------------|-----------|
| `ttp`     | A    | No          | 5 min     |
| `tsf`     | B    | ADX only    | 20 min    |
| `ksqz`    | B    | Keltner     | 20 min    |
| `bbrsi`   | A    | No          | 5 min     |
| `vrb`     | A    | No          | 5 min     |
| `osc`     | B    | MFI only    | 15 min    |
| `mburst`  | A    | No          | 5 min     |
| `vcs`     | A    | No          | 5 min     |
| `tmt`     | A    | No          | 5 min     |
| `wvs`     | B    | OBV + CMF   | 30 min    |
| `mrd`     | B    | Full custom | 45 min    |
| `divs`    | B    | Full custom | 45 min    |
| `admo`    | B    | Full custom | 30 min    |