# Combo Catalog — Full Specifications

---

## TREND + MOMENTUM CONFIRMATION

---

### Triple Trend Pulse (`ttp`)
**Hypothesis:** Price is in a clean trend when short, mid, and long EMAs are
stacked and momentum confirms direction at the midline.

**Indicators:**
- EMA 9 (fast ribbon)
- EMA 21 (mid ribbon)
- EMA 55 (trend anchor)
- RSI 14 (momentum filter — signal fires only when RSI crosses 50)

**Signal logic:**
- Long: EMA9 > EMA21 > EMA55 AND RSI crosses above 50
- Short: EMA9 < EMA21 < EMA55 AND RSI crosses below 50
- Exit: EMA9 crosses EMA21 in opposite direction

**Display:** All EMAs pane 0. RSI pane 2 with 50 level line.

**Preset (Type A):**
```python
{"fn": "ema", "kwargs": {"length": 9}},
{"fn": "ema", "kwargs": {"length": 21}},
{"fn": "ema", "kwargs": {"length": 55}},
{"fn": "rsi", "kwargs": {}},
```
**Best TF:** 1H, 4H  
**Warm-up:** 55 bars

---

### Trend Strength Filter (`tsf`)
**Hypothesis:** Only trade in the direction of trend when ADX confirms the move
has strength, filtered by MACD histogram color.

**Indicators:**
- EMA 20 / EMA 50 (trend direction)
- ADX 14 (trend strength — trade only when ADX > 25)
- MACD (12/26/9) histogram (momentum confirmation)

**Signal logic:**
- Long: EMA20 > EMA50 AND ADX > 25 AND MACD hist > 0 and rising
- Strength filter: ADX > 40 = strong trend, add size
- Exit: MACD hist turns negative OR EMA cross

**Display:** EMAs pane 0. ADX pane 4. MACD pane 3.

**New indicator needed:** ADX (`adx`) — pandas-ta wrapper:
```python
import pandas_ta as ta

def adx(df, period=14):
    result = ta.adx(df["high"], df["low"], df["close"], length=period)
    out = pd.DataFrame(index=df.index)
    out["ADX_14"]  = result[f"ADX_{period}"]
    out["DMP_14"]  = result[f"DMP_{period}"]   # +DI
    out["DMN_14"]  = result[f"DMN_{period}"]   # -DI
    return out
```
**Best TF:** 1D  
**Warm-up:** 50 bars

---

### Keltner Squeeze (`ksqz`)
**Hypothesis:** When BBands contract inside Keltner Channel (the squeeze), a
breakout is imminent. Momentum histogram direction predicts breakout direction.

**Indicators:**
- Bollinger Bands (20, 2.0)
- Keltner Channel (20, 1.5)
- Squeeze Momentum histogram (already in codebase: `sqz`)

**Signal logic:**
- Squeeze ON: BBands width < Keltner width
- Squeeze fires: BBands expand beyond Keltner
- Direction: Squeeze histogram positive = long breakout, negative = short
- Exit: Histogram changes sign

**Display:** BBands + Keltner pane 0. SQZ histogram pane 3.

**New indicator needed:** Keltner Channel (`kc`) — pandas-ta wrapper:
```python
def keltner(df, period=20, scalar=1.5):
    result = ta.kc(df["high"], df["low"], df["close"],
                   length=period, scalar=scalar)
    out = pd.DataFrame(index=df.index)
    out["KC_UPPER"] = result[f"KCUe_{period}_{scalar}"]
    out["KC_MID"]   = result[f"KCBe_{period}_{scalar}"]
    out["KC_LOWER"] = result[f"KCLe_{period}_{scalar}"]
    return out
```
**Best TF:** 15Min, 1H  
**Warm-up:** 30 bars

---

## MEAN REVERSION

---

### BB RSI Reversal (`bbrsi`)
**Hypothesis:** When price tags a BB extreme AND RSI diverges from the price
move AND volume spikes, mean reversion is high probability.

**Indicators:**
- Bollinger Bands (20, 2.0) — already in codebase
- RSI 14 — already in codebase
- Volume (pane 1) — already displayed

**Signal logic:**
- Long setup: Close < BB_lower AND RSI < 35 AND volume > 1.5× 20-bar avg volume
- Short setup: Close > BB_upper AND RSI > 65 AND volume > 1.5× 20-bar avg volume
- Confirmation: Next bar closes back inside BB
- Exit: Price reaches BB midline (SMA 20)

**Display:** BBands + SMA 20 pane 0. RSI pane 2.

**Type A preset — no new code needed.**

**Best TF:** 1H, 1D  
**Warm-up:** 20 bars

---

### VWAP Rubber Band (`vrb`)
**Hypothesis:** Intraday, price snaps back to VWAP after extending to the 2σ
band. Stochastic exhaustion + ATR confirms overextension.

**Indicators:**
- VWAP + 1σ/2σ bands (already in codebase: `vwap`)
- Stochastic 14,3,3 (already in codebase: `stoch`)
- ATR 14 as filter (already in codebase: `atr`)

**Signal logic:**
- Long: Price at VWAP_LOWER (2σ) AND Stoch K < 20 AND ATR < 20-bar ATR avg
- Target: VWAP midline
- Stop: 1 ATR below entry

**Type A preset — no new code needed.**

**Best TF:** 5Min, 15Min  
**Warm-up:** 20 bars

---

### Oversold Confluence (`osc`)
**Hypothesis:** Triple oversold confirmation across price, money flow, and
momentum gives high-conviction mean reversion entries.

**Indicators:**
- RSI 14 < 30
- MFI 14 < 20
- Price at or below BB_lower

**New indicator needed:** Money Flow Index (`mfi`) — pandas-ta wrapper:
```python
def mfi(df, period=14):
    raw = ta.mfi(df["high"], df["low"], df["close"], df["volume"], length=period)
    out = pd.DataFrame(index=df.index)
    out["MFI_14"] = raw
    return out
```
**Best TF:** 1D  
**Warm-up:** 14 bars

---

## SCALP / INTRADAY

---

### Momentum Burst (`mburst`)
**Hypothesis:** The highest-probability scalp entries occur when a squeeze fires
into a ribbon breakout with above-average volume.

**Indicators:**
- EMA 9 / EMA 21 ribbon (already in codebase)
- Squeeze Momentum histogram (already in codebase: `sqz`)
- Volume vs 20-bar average (already displayed)

**Signal logic:**
- Long: EMA9 > EMA21 AND SQZ histogram crosses above 0 AND volume > avg
- Hold: SQZ histogram positive and rising
- Exit: EMA9 crosses below EMA21 OR SQZ turns negative

**Type A preset — no new code needed.**

**Best TF:** 1Min, 5Min  
**Warm-up:** 21 bars

---

### VWAP Cross Scalp (`vcs`)
**Hypothesis:** Price crossing VWAP with RSI momentum and ATR-defined range
is the cleanest intraday signal on liquid instruments.

**Indicators:**
- VWAP + bands (already in codebase)
- RSI 7 (faster RSI for scalping — need to expose `length` param)
- ATR 14 (already in codebase)

**Signal logic:**
- Long: Price crosses above VWAP AND RSI_7 > 50 AND ATR is contracting
- Short: Price crosses below VWAP AND RSI_7 < 50
- Stop: Opposite VWAP band

**Type A preset (RSI 7 requires kwargs):**
```python
{"fn": "rsi", "kwargs": {"length": 7}},
{"fn": "vwap", "kwargs": {}},
{"fn": "atr",  "kwargs": {}},
```
**Best TF:** 1Min, 5Min  
**Warm-up:** 14 bars

---

### Opening Range Break (`orb`)
**Hypothesis:** The high/low of the first N minutes defines the session range.
A breakout of that range with volume confirms directional bias for the day.

**Indicators:**
- ORB high/low levels (custom — session-aware, Type C)
- EMA 9 (trend filter)
- Volume confirmation

**New indicator needed:** `orb` — session-aware, complex (Type C).
This requires knowing session open time and is time-of-day dependent.
Skip for now unless user explicitly requests it.

**Best TF:** 5Min  

---

## SWING / POSITION

---

### Triple MA Trend System (`tmt`)
**Hypothesis:** Classic institutional trend system. All three MAs aligned +
MACD confirms momentum + RSI avoids buying extended moves.

**Indicators:**
- SMA 50 / SMA 100 / SMA 200
- MACD (12/26/9)
- RSI 14 (buy only RSI 40–65, sell only 35–60)

**Signal logic:**
- Long: SMA50 > SMA100 > SMA200 AND MACD hist > 0 AND RSI 40–65
- Exit: SMA50 crosses below SMA100

**Type A preset:**
```python
{"fn": "sma", "kwargs": {"length": 50}},
{"fn": "sma", "kwargs": {"length": 100}},
{"fn": "sma", "kwargs": {"length": 200}},
{"fn": "macd","kwargs": {}},
{"fn": "rsi", "kwargs": {}},
```
**Best TF:** 1D  
**Warm-up:** 200 bars

---

### Wyckoff Volume Spread (`wvs`)
**Hypothesis:** Accumulation and distribution phases show as divergence between
price spread and volume. OBV + CMF + Squeeze confirm institutional footprint.

**Indicators:**
- OBV (volume trend)
- CMF 20 (money flow direction)
- Squeeze Momentum (volatility compression)

**New indicators needed:**
- OBV (`obv`) — pandas-ta wrapper:
```python
def obv_indicator(df):
    raw = ta.obv(df["close"], df["volume"])
    out = pd.DataFrame(index=df.index)
    out["OBV"] = raw
    out["OBV_EMA"] = raw.ewm(span=21, adjust=False).mean()
    return out
```
- CMF (`cmf`) — pandas-ta wrapper:
```python
def cmf(df, period=20):
    raw = ta.cmf(df["high"], df["low"], df["close"], df["volume"], length=period)
    out = pd.DataFrame(index=df.index)
    out["CMF_20"] = raw
    return out
```
**Best TF:** 1D  
**Warm-up:** 21 bars

---

## COMPOSITE / NOVEL

---

### Market Regime Detector (`mrd`)
**Hypothesis:** Markets cycle through 4 regimes: Trending Up, Trending Down,
Ranging, High Volatility. Identifying regime first prevents strategy mismatch.

**Inputs:**
- ADX 14 (trend strength)
- ATR% = ATR/Close × 100 (normalised volatility)
- RSI 14 zone: <40 bear, 40-60 neutral, >60 bull

**Output columns:**
- `MRD_REGIME`: 0=range, 1=trend_up, 2=trend_down, 3=high_vol
- `MRD_ADX`: raw ADX value
- `MRD_ATRPCT`: ATR as % of price

**Logic:**
```python
conditions = [
    (adx > 25) & (rsi > 55),           # trending up
    (adx > 25) & (rsi < 45),           # trending down
    atr_pct > atr_pct.rolling(50).quantile(0.85),  # high vol
]
choices = [1, 2, 3]
regime = np.select(conditions, choices, default=0)
```
**Type B — new custom indicator.**  
**Best TF:** 1D  
**Warm-up:** 50 bars

---

### Divergence Scanner (`divs`)
**Hypothesis:** When price makes a new high/low but RSI and MACD do not
confirm, the trend is exhausting. Triple divergence = very high conviction.

**Output columns:**
- `DIV_RSI`: +1 bullish, -1 bearish, 0 none
- `DIV_MACD`: +1 bullish, -1 bearish, 0 none
- `DIV_SCORE`: sum of above (-2 to +2) — plot as histogram

**Implementation:** Uses `_detect_divergence()` pattern from quant-indicator-builder.

**Type B — new custom indicator.**  
**Best TF:** 1H, 1D  
**Warm-up:** 26 bars (MACD slow)

---

### Adaptive Momentum (`admo`)
**Hypothesis:** RSI's fixed period causes lag in volatile markets and whipsaws
in quiet ones. Dynamically adjusting the period via ATR improves signal quality.

**Formula:**
```
ATR_norm  = ATR_14 / ATR_14.rolling(50).mean()   # normalised ATR (1.0 = average)
period    = clamp(round(14 / ATR_norm), 5, 30)    # inverse: high vol → shorter period
ARSI      = RSI(close, period=period)             # computed per-bar with dynamic period
```

**Implementation note:** True dynamic per-bar RSI requires a loop — acceptable
here because it's a single pass. Document in code comments.

**Output columns:**
- `ARSI`: adaptive RSI value (0–100)
- `ARSI_PERIOD`: the dynamic period used (useful for debugging)

**Type B — new custom indicator.**  
**Best TF:** 1H  
**Warm-up:** 50 bars (ATR normalisation window)