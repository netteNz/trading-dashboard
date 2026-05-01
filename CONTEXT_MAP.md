# Trading Dashboard — Context Map

> Last updated: 2026-05-01

## Architecture Overview

```
frontend (React 18 / Vite 5 / Tailwind 3)
  └── /api/*        ──proxy──► backend (Flask 3 / SocketIO / port 5000)
  └── /socket.io    ──ws──────► backend SocketIO

backend
  ├── DataSource   ─► yfinance (default) | alpaca-py (historical)
  ├── AlpacaStream ─► alpaca-py StockDataStream (live bars, daemon thread)
  └── IndicatorEngine ─► pandas-ta + 3 custom modules
```

---

## File Map

### Backend

| File | Role |
|------|------|
| [`backend/app.py`](backend/app.py) | Flask entry point. REST routes + SocketIO events. Holds `INDICATOR_PRESETS` dict and `_build_engine()` dispatcher. |
| [`backend/data/source.py`](backend/data/source.py) | `DataSource` class — `get_bars()` fan-out to yfinance or Alpaca historical. `AlpacaStream` class — live WebSocket, normalises bars to candle dict. |
| [`backend/indicators/engine.py`](backend/indicators/engine.py) | `IndicatorEngine` — chainable builder. `serialize()` returns `{candles, indicators}` JSON contract consumed by frontend. |
| [`backend/indicators/custom/vwap_band.py`](backend/indicators/custom/vwap_band.py) | `vwap_band(df)` → `VWAP`, `VWAP_UPPER`, `VWAP_LOWER` |
| [`backend/indicators/custom/momentum.py`](backend/indicators/custom/momentum.py) | `momentum_oscillator(df)` → `MOM_OSC/SIGNAL/HIST`; `squeeze_momentum(df)` → `SQZ_VAL/ON` |
| [`backend/indicators/custom/triple_ma.py`](backend/indicators/custom/triple_ma.py) | `triple_ma(df)` → `TMA_{fast/mid/slow}`, `TMA_ALIGN`, `TMA_BUY/SELL` |
| [`backend/ws/stream.py`](backend/ws/stream.py) | Thread manager for `AlpacaStream`. `init_stream()`, `subscribe()`, `unsubscribe()`, `stop()`. Exponential backoff on reconnect (max 5 retries). |
| [`backend/requirements.txt`](backend/requirements.txt) | flask, flask-cors, flask-socketio, pandas-ta, yfinance, alpaca-py, eventlet |

### Frontend

| File | Role |
|------|------|
| [`frontend/src/App.jsx`](frontend/src/App.jsx) | Root state: `symbol`, `timeframe`, `preset`, `indicators`, `sidebarOpen`. Composes all components. Derives `latestCandle` for OHLCV header readout. |
| [`frontend/src/components/TradingChart.jsx`](frontend/src/components/TradingChart.jsx) | lightweight-charts v4. Main pane (candlestick + pane-0 overlays) + dynamic sub-panes for pane > 0. Syncs time scales across panes. ResizeObserver for responsiveness. |
| [`frontend/src/components/IndicatorPanel.jsx`](frontend/src/components/IndicatorPanel.jsx) | Sidebar accordion: Watchlist · Active · Combos · grouped indicator library. Combo presets: VRB, MBurst, VCS. Param input modal for configurable indicators. |
| [`frontend/src/components/SymbolSearch.jsx`](frontend/src/components/SymbolSearch.jsx) | Controlled input with dropdown. Enter key submits; filters `POPULAR` list locally. Backend `/api/search` not wired yet (uses local filter only). |
| [`frontend/src/components/Toolbar.jsx`](frontend/src/components/Toolbar.jsx) | Timeframe (1m–1W) + preset (trend/momentum/scalp/full) selectors. Shows live price from lastTick. |
| [`frontend/src/hooks/useChartData.js`](frontend/src/hooks/useChartData.js) | Fetches `/api/chart/{symbol}?tf=&preset=&limit=600`. AbortController per request. Returns `{data, loading, error, refetch}`. |
| [`frontend/src/hooks/useWebSocket.js`](frontend/src/hooks/useWebSocket.js) | Singleton `socket.io-client`. Emits `subscribe`/`unsubscribe`, listens for `tick`. Returns `{lastTick, connected}`. |
| [`frontend/vite.config.js`](frontend/vite.config.js) | Dev proxy: `/api` → `:5000`; `/socket.io` → `:5000` (ws). |

### Infrastructure

| File | Role |
|------|------|
| [`docker-compose.yml`](docker-compose.yml) | Two services: `backend` (:5000) + `frontend` (:3000). Frontend sets `VITE_API_URL=http://backend:5000`. |
| [`backend/.env`](backend/.env) | `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `DATA_PROVIDER` (yfinance\|alpaca), `FLASK_PORT` |

---

## Data Contract — `IndicatorEngine.serialize()`

```json
{
  "candles": [
    { "time": 1704067200, "open": 476.32, "high": 478.91, "low": 475.10, "close": 477.85,
      "volume": 82341200, "EMA_20": 477.1, "RSI_14": 58.3, ... }
  ],
  "indicators": [
    { "key": "EMA_20", "type": "line", "pane": 0, "color": "#38bdf8", "label": "EMA 20" },
    { "key": "RSI_14", "type": "line", "pane": 1, "color": "#a78bfa", "label": "RSI 14",
      "levels": [{"value": 70, "color": "#ef4444"}, {"value": 30, "color": "#22c55e"}] }
  ]
}
```

**Pane assignment:**

| Pane | Contents |
|------|----------|
| 0 | Main chart (candles + overlays: EMA, SMA, BBands, VWAP, TMA) |
| 1 | RSI |
| 2 | MACD (line + signal + histogram) |
| 3 | ATR |
| 4 | Stochastic K/D |
| 5 | Volume (histogram + VOL_MA) |
| 6 | Momentum Oscillator |
| 7 | Squeeze Momentum |
| 8 | TMA Align histogram |

---

## Indicator Registry

### Standard (pandas-ta)
| fn key | Engine method | Output columns |
|--------|--------------|----------------|
| `ema` | `add_ema(length)` | `EMA_{length}` |
| `sma` | `add_sma(length)` | `SMA_{length}` |
| `bbands` | `add_bbands()` | `BB_UPPER/MID/LOWER` |
| `rsi` | `add_rsi(length)` | `RSI_{length}` |
| `macd` | `add_macd()` | `MACD`, `MACD_SIGNAL`, `MACD_HIST` |
| `atr` | `add_atr(length)` | `ATR_{length}` |
| `stoch` | `add_stoch()` | `STOCH_K`, `STOCH_D` |

### Custom
| fn key | Engine method | Output columns |
|--------|--------------|----------------|
| `vwap` | `add_vwap_band()` | `VWAP`, `VWAP_UPPER/LOWER` |
| `mom` | `add_momentum_oscillator()` | `MOM_OSC/SIGNAL/HIST` |
| `sqz` | `add_squeeze_momentum()` | `SQZ_VAL`, `SQZ_ON` |
| `vol` | `add_volume_profile()` | `VOL_MA` + `volume` passthrough |
| `tma` | `add_triple_ma(fast,mid,slow)` | `TMA_{f/m/s}`, `TMA_ALIGN/BUY/SELL` |

---

## Preset Registry (`app.py` + `IndicatorPanel.jsx`)

| Preset | Indicators |
|--------|-----------|
| `trend` | EMA 20/50, BBands, VWAP, TMA 3/7/20 |
| `momentum` | RSI, MACD, MomOsc |
| `scalp` | EMA 9/21, RSI, Stoch |
| `full` | EMA 20/50, BBands, RSI, MACD, VWAP, MomOsc, Vol |
| `vrb` (combo) | VWAP, Stoch, ATR |
| `mburst` (combo) | EMA 9/21, Squeeze |
| `vcs` (combo) | RSI 7, VWAP, ATR |

---

## Known Gaps / TODOs

- [x] `SymbolSearch` — wired to `/api/search?q=...` with 350ms debounce; POPULAR list is fallback
- [x] Combo presets — `indicators` array is now the single source of truth; `useChartData` always sends `?indicators=<json>` so panel combos trigger real refetches
- [ ] `TradingChart` — `lastTick` live update block is stubbed (no-op comment in `useEffect`)
- [ ] `Toolbar` — `isUp` (price direction) is hardcoded `true`; needs prev-close comparison
- [ ] No test files exist anywhere in the project
- [ ] `frontend/docker-compose` frontend service references a `Dockerfile` that doesn't exist in `frontend/`
- [ ] `INDICATOR_PRESETS` is now defined in two places: `backend/app.py` and `frontend/src/App.jsx` — must keep in sync when adding presets

---

## Key Dependency Chains

```
Add new indicator fn:
  1. backend/indicators/engine.py        ← add add_X() method
  2. backend/app.py (_build_engine)      ← add elif fn == "x" branch
  3. backend/indicators/custom/*.py      ← implement if custom
  4. frontend/src/components/IndicatorPanel.jsx (AVAILABLE list)

Add new preset:
  1. backend/app.py (INDICATOR_PRESETS) — backend still supports ?preset= for direct API calls
  2. frontend/src/App.jsx (INDICATOR_PRESETS) — must mirror backend; toolbar preset buttons load from here
  3. frontend/src/components/Toolbar.jsx (PRESETS list) — add the key to render the button
  4. frontend/src/components/IndicatorPanel.jsx (COMBOS) — if it's a combo/strategy preset

Change candle JSON shape:
  1. backend/indicators/engine.py (serialize)
  2. frontend/src/components/TradingChart.jsx (candleData mapping)
  3. frontend/src/App.jsx (latestCandle field access)
```
