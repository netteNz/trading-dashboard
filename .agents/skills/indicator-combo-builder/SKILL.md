---
name: indicator-combo-builder
description: >
  Dedicated custom indicator designer and combination strategist for the TradeView
  trading dashboard. Use this skill whenever the user wants to propose, design, or
  implement a new indicator combination, composite signal, or multi-indicator strategy.
  Trigger on phrases like "add a combo", "what indicators work well together",
  "design a strategy for scalping/swing/trend", "build a confluence indicator",
  "I want to see divergence + volume", "create a new preset", "combine RSI with X",
  or any request to wire multiple indicators into a single signal or pane.
  Also trigger when the user asks for indicator recommendations by trading style,
  timeframe, or asset class. Always use this skill before proposing any indicator
  combination or new composite indicator — it contains the full catalog of vetted
  combos and the exact implementation pattern for this project.
---

# Indicator Combo Builder

You are the combo strategist and senior quant dev for the TradeView dashboard.
Your job is to recommend, design, and implement multi-indicator combinations that
give traders meaningful confluence signals — not just stacking noise on a chart.

---

## How to Use This Skill

1. **User asks for a combo or strategy** → pick from the Combo Catalog below,
   explain the logic, confirm with the user, then implement following the
   Architecture section.

2. **User wants something not in the catalog** → design it from first principles
   using the Design Framework, then add it to the catalog before implementing.

3. **User wants a new preset** → compose from existing `fn` keys in `app.py`
   `INDICATOR_PRESETS`, no new Python code needed.

Read `references/combos.md` for the full combo catalog with formulas.
Read `references/implementation.md` for exact file touch-points per combo type.

---

## Combo Catalog (summary — full specs in references/combos.md)

### Trend + Momentum Confirmation
| Combo | Key Signals | Best TF | Preset key |
|-------|------------|---------|------------|
| **Triple Trend Pulse** | EMA 9/21/55 + RSI midline cross | 1H, 4H | `ttp` |
| **Trend Strength Filter** | ADX + EMA 20/50 + MACD histogram | 1D | `tsf` |
| **Keltner Squeeze** | Keltner Channel + BBands + Mom Oscillator | 15Min, 1H | `ksqz` |

### Mean Reversion
| Combo | Key Signals | Best TF | Preset key |
|-------|------------|---------|------------|
| **BB RSI Reversal** | BBands extremes + RSI divergence + Volume spike | 1H, 1D | `bbrsi` |
| **VWAP Rubber Band** | VWAP bands + Stochastic + ATR filter | 5Min, 15Min | `vrb` |
| **Oversold Confluence** | RSI < 30 + MFI < 20 + price at lower BB | 1D | `osc` |

### Scalp / Intraday
| Combo | Key Signals | Best TF | Preset key |
|-------|------------|---------|------------|
| **Momentum Burst** | EMA 9/21 ribbon + SQZ histogram + Volume delta | 1Min, 5Min | `mburst` |
| **VWAP Cross Scalp** | VWAP ± 1σ bands + RSI 7 + ATR trailing | 1Min, 5Min | `vcs` |
| **Opening Range Break** | ORB levels + EMA 9 + Volume confirmation | 5Min | `orb` |

### Swing / Position
| Combo | Key Signals | Best TF | Preset key |
|-------|------------|---------|------------|
| **Triple MA Trend System** | SMA 50/100/200 + MACD + RSI 14 filter | 1D | `tmt` |
| **Ichimoku Full Cloud** | Cloud + Tenkan/Kijun cross + RSI | 4H, 1D | `ichi` |
| **Wyckoff Volume Spread** | OBV + CMF + Squeeze + custom spread | 1D | `wvs` |

### Composite / Novel
| Combo | Key Signals | Best TF | Preset key |
|-------|------------|---------|------------|
| **Market Regime Detector** | ADX + VIX proxy (ATR%) + RSI zone | 1D | `mrd` |
| **Divergence Scanner** | RSI divergence + MACD divergence + OBV divergence | 1H, 1D | `divs` |
| **Adaptive Momentum** | Dynamic RSI (variable period via ATR) + EMA cross | 1H | `admo` |

---

## Design Framework (for new combos)

Before writing any code, answer all 7 questions:

1. **Trading hypothesis** — What market condition does this combo detect?
   (trend continuation / reversal / breakout / range / regime)

2. **Signal hierarchy** — Which indicator is the *filter* (context) and which
   is the *trigger* (entry)? Never treat all indicators equally.

3. **Confluence rule** — What is the minimum number of agreeing signals required?
   (e.g. "2 of 3 must confirm", "filter must be green before trigger fires")

4. **Timeframe alignment** — Primary TF + higher-TF context TF?

5. **Display layout** — Which panes? Which as overlays vs sub-panes?
   Follow pane rules: 0=price, 1=vol, 2=first osc, 3=second osc, 4+=new

6. **Risk context** — Does this combo include a volatility/ATR element?
   Every complete system should have one.

7. **Exit signal** — What does "combo off" look like? (opposite crossover,
   RSI re-entry into neutral zone, VWAP reclaim, etc.)

---

## Implementation Pattern

Every combo maps to one of three implementation types:

### Type A — New Preset (no new Python code)
Compose existing `fn` keys. Edit only `app.py`:
```python
INDICATOR_PRESETS["<key>"] = [
    {"fn": "ema",    "kwargs": {"length": 9}},
    {"fn": "ema",    "kwargs": {"length": 21}},
    {"fn": "rsi",    "kwargs": {}},
    # ...
]
```
Also add to `IndicatorPanel.jsx` AVAILABLE if it should appear in the UI.

### Type B — New Composite Indicator (single Python file)
When the combo requires a derived signal (e.g. divergence score, regime label)
that doesn't exist as a standalone indicator. Follow the 5-step pattern from
`quant-indicator-builder`:
1. `backend/indicators/custom/<name>.py`
2. `IndicatorEngine.add_<name>()`
3. `SERIES_META` entry
4. `_build_engine()` elif branch in `app.py`
5. `IndicatorPanel.jsx` AVAILABLE entry

### Type C — Multi-file System (rare)
When the combo requires its own state (e.g. ORB levels computed at 9:30 AM,
regime that updates on higher TF). Requires a standalone module under
`backend/indicators/systems/<name>/` with a `compute(df, **kwargs) → DataFrame`
entrypoint. Discuss with user before implementing.

---

## Proposed New Custom Indicators (not yet in codebase)

These are greenfield — full specs in `references/combos.md`:

| Name | fn key | Type | Complexity |
|------|--------|------|-----------|
| ADX Strength | `adx` | pandas-ta wrapper | Low |
| Money Flow Index | `mfi` | pandas-ta wrapper | Low |
| OBV Trend | `obv` | pandas-ta wrapper | Low |
| Keltner Channel | `kc` | pandas-ta wrapper | Low |
| RSI Divergence | `rdiv` | Custom signal | Medium |
| Adaptive RSI | `arsi` | Custom math | Medium |
| Opening Range Break | `orb` | Session-aware | High |
| Market Regime | `mrd` | Multi-input composite | High |
| Volume Delta Proxy | `vdelta` | Custom math | Medium |

---

## Pane Layout Reference

```
Pane 0  ── Price (candles)
           └── overlays: EMA, SMA, BBands, Keltner, VWAP bands, Ichimoku cloud

Pane 1  ── Volume bars
           └── overlays: OBV line, CMF line

Pane 2  ── Primary oscillator
           └── RSI, Stochastic, MFI, Williams %R, CCI, Adaptive RSI

Pane 3  ── Secondary oscillator / MACD
           └── MACD (line+hist), Mom Oscillator, Squeeze Momentum

Pane 4  ── Tertiary / regime
           └── ADX, ATR%, Market Regime, Volume Delta

Pane 5+ ── Divergence signals, composite scores
```

**Rule:** Never put more than 3 line series in the same pane. If a combo needs
more, split into a new pane and note it in the combo spec.

---

## Quick Validation Checklist

Before wiring any combo to the frontend:

- [ ] Smoke test: `python -c "from indicators.custom.X import X; import yfinance as yf; df=yf.download('SPY','2023-01-01'); print(X(df).tail(5))"`
- [ ] No NaN bleed past warm-up period (first N rows only)
- [ ] No forward-looking calculations (no negative `.shift()`)
- [ ] Column names don't collide with existing SERIES_META keys
- [ ] Pane assignment follows layout reference above
- [ ] Preset added to both `INDICATOR_PRESETS` (backend) and `AVAILABLE` (frontend)