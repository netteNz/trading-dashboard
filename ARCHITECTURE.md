# Trading Dashboard — Architecture

> Stack: React 18 + Vite 5 · Flask 3 + Flask-SocketIO · Python 3.13

---

## Overview

Self-hosted, real-time trading dashboard for individual traders and quants. Multi-pane charting, dynamic indicator panel with custom indicators and preset bundles, live WebSocket streaming (Alpaca) or historical data (yfinance). Extended via a clean builder pattern for new indicators.

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
| `backend/app.py` | Flask entry point. REST routes + SocketIO events. Holds `INDICATOR_PRESETS` dict and `_build_engine()` dispatcher. |
| `backend/data/source.py` | `DataSource` — `get_bars()` fan-out to yfinance or Alpaca historical. `AlpacaStream` — live WebSocket, normalises bars to candle dict. |
| `backend/indicators/engine.py` | `IndicatorEngine` — chainable builder. `serialize()` returns `{candles, indicators}` JSON contract consumed by frontend. |
| `backend/indicators/custom/vwap_band.py` | `vwap_band(df)` → `VWAP`, `VWAP_UPPER`, `VWAP_LOWER` |
| `backend/indicators/custom/momentum.py` | `momentum_oscillator(df)` → `MOM_OSC/SIGNAL/HIST`; `squeeze_momentum(df)` → `SQZ_VAL/ON` |
| `backend/indicators/custom/triple_ma.py` | `triple_ma(df)` → `TMA_{fast/mid/slow}`, `TMA_ALIGN`, `TMA_BUY/SELL` |
| `backend/ws/stream.py` | Thread manager for `AlpacaStream`. `init_stream()`, `subscribe()`, `unsubscribe()`, `stop()`. Exponential backoff on reconnect (max 5 retries). |
| `backend/requirements.txt` | flask, flask-cors, flask-socketio, pandas-ta, yfinance, alpaca-py, eventlet |

### Frontend

| File | Role |
|------|------|
| `frontend/src/App.jsx` | Root state: `symbol`, `timeframe`, `preset`, `indicators`, `sidebarOpen`, `rlMetricsCollapsed`. Composes all components. Derives `latestCandle` for OHLCV header readout. |
| `frontend/src/components/TradingChart.jsx` | lightweight-charts v4. Main pane (candlestick + pane-0 overlays) + dynamic sub-panes for pane > 0. Syncs time scales across panes. ResizeObserver for responsiveness. |
| `frontend/src/components/IndicatorPanel.jsx` | Sidebar accordion: Watchlist · Active · Combos · grouped indicator library. Combo presets: VRB, MBurst, VCS. Param input modal for configurable indicators. |
| `frontend/src/components/RLAgentMetrics.jsx` | Collapsible right panel. Displays RL ensemble P&L metrics and leaderboard stats fetched from `/api/signals/<symbol>`. |
| `frontend/src/components/SymbolSearch.jsx` | Controlled input with dropdown. Enter key submits; debounced calls to `/api/search?q=`; POPULAR list as fallback. |
| `frontend/src/components/Toolbar.jsx` | Timeframe (1m–1W) + preset (trend/momentum/scalp/full) selectors. Shows live price from lastTick. |
| `frontend/src/hooks/useChartData.js` | Fetches `/api/chart/{symbol}?tf=&preset=&limit=600`. AbortController per request. Returns `{data, loading, error, refetch}`. |
| `frontend/src/hooks/useWebSocket.js` | Singleton `socket.io-client`. Emits `subscribe`/`unsubscribe`, listens for `tick`. Returns `{lastTick, connected}`. |
| `frontend/vite.config.js` | Dev proxy: `/api` → `:5000`; `/socket.io` → `:5000` (ws). |

### Infrastructure

| File | Role |
|------|------|
| `docker-compose.yml` | Two services: `backend` (:5000) + `frontend` (:3000). Frontend sets `VITE_API_URL=http://backend:5000`. |
| `backend/.env` | `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `DATA_PROVIDER` (yfinance\|alpaca), `FLASK_PORT` |

---

## Component Wiring

```
App.jsx (state: symbol, timeframe, preset, indicators, lastTick, connected, rlMetricsCollapsed)
│
├── useChartData(symbol, timeframe, indicators)
│     └── GET /api/chart/{symbol}?tf=&indicators=
│           └── backend: DataSource → IndicatorEngine → serialize()
│
├── useWebSocket(symbol)
│     └── socket.io: subscribe(symbol) → receives "tick" events
│           └── backend: AlpacaStream → stream.py → socketio.emit("tick")
│
├── <Toolbar symbol timeframe preset lastTick connected />
│     └── onTimeframeChange → setTimeframe → re-fetch
│     └── onPresetChange → GET /api/presets/{name} → setIndicators
│
├── <SymbolSearch value onChange />
│     └── onChange → setSymbol → re-fetch + re-subscribe
│
├── <IndicatorPanel active onChange symbol onSymbolChange />
│     └── onChange → setIndicators → re-fetch
│
├── <TradingChart data lastTick />
│     ├── pane 0: candles + overlay indicators (EMA, VWAP, BB)
│     ├── panes 1-N: oscillators (RSI, MACD, Stoch, Squeeze, Momentum)
│     └── scatter markers: Triple MA buy/sell signals
│
└── <RLAgentMetrics symbol isCollapsed onToggleCollapse />
      └── GET /api/signals/{symbol} → ensemble_metrics + leaderboard_aggregate
```

---

## API Surface

| Method | Route | Key Params | Returns |
|--------|-------|------------|---------|
| GET | `/api/health` | — | `{status, provider}` |
| GET | `/api/chart/<symbol>` | `tf`, `limit`, `preset`, `indicators` (JSON array) | `{candles[], indicators[]}` |
| GET | `/api/search` | `q` | `[{symbol, name, exchange}]` |
| GET | `/api/indicators` | — | `{standard[], custom[]}` with params schema |
| GET | `/api/presets` | — | `string[]` |
| GET | `/api/presets/<name>` | — | `[{fn, kwargs}]` |
| GET | `/api/signals/<symbol>` | — | `{ensemble_metrics, leaderboard_aggregate, signals[]}` |

`tf` values: `1Min 5Min 15Min 30Min 1Hour 1Day 1Week`

---

## WebSocket Events (Socket.IO)

| Event | Direction | Payload |
|-------|-----------|---------|
| `subscribe` | Client → Server | `{symbol}` |
| `unsubscribe` | Client → Server | `{symbol}` |
| `tick` | Server → Client | `{symbol, time, open, high, low, close, volume}` |

---

## Data Contract — `IndicatorEngine.serialize()`

```json
{
  "candles": [
    { "time": 1704067200, "open": 476.32, "high": 478.91, "low": 475.10, "close": 477.85,
      "volume": 82341200, "EMA_20": 477.1, "RSI_14": 58.3 }
  ],
  "indicators": [
    { "key": "EMA_20", "type": "line", "pane": 0, "color": "#38bdf8", "label": "EMA 20" },
    { "key": "RSI_14", "type": "line", "pane": 1, "color": "#a78bfa", "label": "RSI 14",
      "levels": [{"value": 70, "color": "#ef4444"}, {"value": 30, "color": "#22c55e"}] }
  ]
}
```

### Pane Assignment

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

### Indicator request format (for `indicators` query param)

```json
[
  { "fn": "ema", "kwargs": { "length": 20 } },
  { "fn": "rsi", "kwargs": {} },
  { "fn": "tma", "kwargs": { "fast": 3, "mid": 7, "slow": 20 } }
]
```

### `/api/signals/<symbol>` payload

```json
{
  "symbol": "NVDA",
  "interval": "1d",
  "last_updated_utc": "2026-05-03T09:51:29Z",
  "model_count": 5,
  "ensemble_metrics": {
    "simulated_return_pct": 33169.86,
    "simulated_max_dd_pct": 3.62,
    "simulated_final_balance": 332698.59,
    "simulated_trade_count": 1
  },
  "leaderboard_aggregate": {
    "model_count": 202,
    "avg_sharpe": 0.52,
    "max_sharpe": 1.83
  },
  "signals": []
}
```

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

## Preset Registry

Defined in two mirrored locations: `backend/app.py` (`INDICATOR_PRESETS`) and `frontend/src/App.jsx` (`INDICATOR_PRESETS`). Both must stay in sync.

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

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `DATA_PROVIDER` | yes | `yfinance` | `yfinance` or `alpaca` |
| `ALPACA_API_KEY` | if alpaca | — | Alpaca market data key |
| `ALPACA_SECRET_KEY` | if alpaca | — | Alpaca secret |
| `ALPACA_BASE_URL` | no | `paper-api.alpaca.markets` | Paper or live endpoint |
| `FLASK_PORT` | no | `5000` | Backend port |

Alpaca WS stream only starts if `ALPACA_API_KEY` is set and ≠ `your_alpaca_key_here`.

---

## Running Locally

```bash
# Backend
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
cp .env.example .env           # fill in keys if using Alpaca
python app.py

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

```bash
# Docker (full stack)
docker compose up --build
```

---

## Extending the Codebase

### Add a Custom Indicator (4 touch points)

1. `backend/indicators/custom/<name>.py` — fn signature: `(df: DataFrame, **kwargs) → DataFrame`
2. `backend/indicators/engine.py` — add `add_<name>()` method, append to `_indicator_meta`
3. `backend/app.py` (`_build_engine`) — add `elif fn == "<shortname>": engine.add_<name>(**kw)`
4. `frontend/src/components/IndicatorPanel.jsx` — append `{ fn, label, params }` to `AVAILABLE`

### Add a New Preset (4 touch points)

1. `backend/app.py` (`INDICATOR_PRESETS`) — backend supports `?preset=` for direct API calls
2. `frontend/src/App.jsx` (`INDICATOR_PRESETS`) — must mirror backend; toolbar loads from here
3. `frontend/src/components/Toolbar.jsx` (`PRESETS` list) — add key to render the button
4. `frontend/src/components/IndicatorPanel.jsx` (`COMBOS`) — if it's a combo/strategy preset

### Change Candle JSON Shape (3 touch points)

1. `backend/indicators/engine.py` (`serialize`)
2. `frontend/src/components/TradingChart.jsx` (candleData mapping)
3. `frontend/src/App.jsx` (latestCandle field access)

---

## Tech Stack

| Layer | Tech | Version |
|-------|------|---------|
| Frontend runtime | React | ^18.3.0 |
| Charts | Lightweight Charts | ^4.2.0 |
| Styling | Tailwind CSS | ^3.4.10 |
| WS client | socket.io-client | ^4.7.5 |
| Backend runtime | Python | 3.13.x |
| Web server | Flask + Flask-SocketIO | 3.0.3 / 5.3.6 |
| Indicators | pandas-ta | 0.4.71b0 |
| Data (default) | yfinance | ≥1.3.0 |
| Data (live) | alpaca-py | 0.26.0 |
| DataFrame | pandas / numpy | ≥3.0.2 / ≥2.2.6 |

---

## Constraints & Gotchas

- **pandas-ta**: use `0.4.71b0` on Windows; `0.4.67b0` on macOS/Python 3.14 with `numba` stubbed. Do not upgrade.
- **numpy**: must be `≥2.0.0`; pandas-ta breaks with 1.x on Python 3.13.
- **pandas**: must be `≥2.3.2`.
- **async_mode**: Flask-SocketIO is set to `threading` (Python 3.14 macOS compatible); may need `eventlet` on Windows.
- **Timestamp serialization**: `engine.serialize()` uses `total_seconds()` for resolution-agnostic epoch conversion — do not replace with `.timestamp()`.
- **Socket singleton**: `useWebSocket` holds a module-level `_socket`; only one socket instance exists regardless of React re-renders.
- **AbortController**: `useChartData` cancels in-flight fetch on symbol/timeframe/indicator change — removing this causes race conditions on rapid changes.
- **Preset sync**: `INDICATOR_PRESETS` is defined in both `backend/app.py` and `frontend/src/App.jsx` — both must be updated when adding or changing presets.
- **Docker**: frontend service references a `Dockerfile` that doesn't exist in `frontend/`; treat Docker config as a starting point only.
- **`TradingChart` live tick**: `lastTick` update block is stubbed (no-op comment in `useEffect`).
- **`Toolbar` price direction**: `isUp` is hardcoded `true`; needs prev-close comparison to be accurate.
