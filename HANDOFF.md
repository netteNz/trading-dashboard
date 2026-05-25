# Trading Dashboard — RL Bot Handoff
> Generated: 2026-05-24 · Stack: React 18 + Vite · Flask + SocketIO · Python 3.13

---

## Quick Start
```bash
# Backend — activate venv first
cd backend && source venv/bin/activate && python app.py   # macOS/Linux
cd backend && venv\Scripts\activate && python app.py       # Windows

# Frontend
cd frontend && npm run dev
```
URLs: Backend → http://localhost:5000 · Frontend → http://localhost:3000

---

## Directory Tree

```
trading-dashboard/
├── docker-compose.yml
├── backend/
│   ├── app.py                    ← Flask entry point, all HTTP + SocketIO routes
│   ├── .env / .env.example       ← Alpaca credentials + DATA_PROVIDER
│   ├── data/
│   │   └── source.py             ← DataSource (yfinance/Alpaca historical) + AlpacaStream
│   ├── indicators/
│   │   ├── engine.py             ← IndicatorEngine builder (chainable)
│   │   └── custom/
│   │       ├── vwap_band.py      ← Anchored VWAP + std dev bands
│   │       ├── momentum.py       ← RSI-core oscillator + Squeeze Momentum (Lazybear)
│   │       └── triple_ma.py      ← Triple MA crossover + buy/sell signal markers
│   └── ws/
│       └── stream.py             ← Alpaca WebSocket manager, emits Socket.IO "tick" events
└── frontend/
    ├── vite.config.js             ← Dev proxy: /api + /socket.io → localhost:5000
    ├── tailwind.config.js
    └── src/
        ├── App.jsx                ← Root: all state (symbol, timeframe, preset, indicators)
        ├── main.jsx
        ├── components/
        │   ├── TradingChart.jsx   ← lightweight-charts renderer, multi-pane management
        │   ├── SymbolSearch.jsx   ← Debounced autocomplete, calls /api/search
        │   ├── IndicatorPanel.jsx ← Sidebar: add/remove indicators, load combos
        │   └── Toolbar.jsx        ← Timeframe buttons, preset selector, live price badge
        └── hooks/
            ├── useChartData.js    ← GET /api/chart/{symbol}?tf=&indicators= (cancellable)
            └── useWebSocket.js    ← Socket.IO singleton, emits subscribe/unsubscribe
```

---

## Component Wiring

```
App.jsx (state: symbol, timeframe, preset, indicators, lastTick, connected)
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
└── <TradingChart data lastTick />
      ├── pane 0: candles + overlay indicators (EMA, VWAP, BB)
      ├── panes 1-N: oscillators (RSI, MACD, Stoch, Squeeze, Momentum)
      └── scatter markers: Triple MA buy/sell signals
```

---

## API Surface

| Method | Route | Key Params | Returns |
|--------|-------|------------|---------|
| GET | `/api/health` | — | `{status, provider}` |
| GET | `/api/chart/<symbol>` | `tf`, `limit`, `preset`, `indicators` (JSON) | `{candles[], indicators[]}` |
| GET | `/api/search` | `q` | `[{symbol, name, exchange}]` |
| GET | `/api/indicators` | — | `{standard[], custom[]}` |
| GET | `/api/presets` | — | `string[]` |
| GET | `/api/presets/<name>` | — | `[{fn, kwargs}]` |

`tf` values: `1Min 5Min 15Min 30Min 1Hour 1Day 1Week`

---

## WebSocket Events (Socket.IO)

| Event | Direction | Payload |
|-------|-----------|---------|
| `subscribe` | Client → Server | `{symbol}` |
| `unsubscribe` | Client → Server | `{symbol}` |
| `tick` | Server → Client | `{symbol, time, open, high, low, close, volume}` |

---

## Data Structures

### Candle (from `/api/chart`)
```json
{
  "time": 1704067200,
  "open": 476.32,
  "high": 478.91,
  "low": 475.10,
  "close": 477.85,
  "volume": 82341200
}
```

### Indicator columns appended to candles
`EMA_20`, `EMA_50`, `RSI_14`, `MACD`, `MACD_signal`, `MACD_hist`,
`BB_upper`, `BB_mid`, `BB_lower`, `VWAP`, `ATR_14`, `STOCH_k`, `STOCH_d`,
`MOM_osc`, `SQZ_momentum`

### Indicator metadata (per series)
```json
{
  "key": "EMA_20",
  "type": "line",
  "pane": 0,
  "color": "#38bdf8",
  "label": "EMA 20",
  "lineStyle": "solid",
  "levels": [
    { "value": 70, "color": "#ef4444" },
    { "value": 30, "color": "#22c55e" }
  ]
}
```

### Indicator request format (for `indicators` query param)
```json
[
  { "fn": "ema", "kwargs": { "length": 20 } },
  { "fn": "rsi", "kwargs": {} },
  { "fn": "tma", "kwargs": { "fast": 3, "mid": 7, "slow": 20 } }
]
```

---

## Data Flow

### Historical chart request
```
GET /api/chart/AAPL?tf=5Min&limit=500&indicators=[...]
  app.get_chart()
  ├── DataSource.get_bars("AAPL", "5Min", 500)    ← yfinance or Alpaca REST
  ├── _build_engine(df, [{fn, kwargs}, ...])
  │   └── IndicatorEngine(df)
  │         .add_ema(length=20)
  │         .add_rsi()
  │         ...
  │         .serialize()  →  {candles: [...], indicators: [{key, type, pane, ...}]}
  └── Return JSON → useChartData → TradingChart
```

### Live tick (WebSocket)
```
Client emits: {subscribe: {symbol: "SPY"}}
  handle_subscribe()
  ├── join_room("SPY")
  └── ws.stream.subscribe("SPY")
        └── AlpacaStream → _handle_bar(bar)
              → socketio.emit("tick", bar, room="SPY")
                    → useWebSocket receives tick
                          → App.jsx setLastTick()
                                → TradingChart series.update()
```

---

## Backend Key Abstractions

| Name | File | Purpose |
|------|------|---------|
| `DataSource` | `data/source.py` | Unified OHLCV fetch; provider switch via env |
| `AlpacaStream` | `data/source.py` | Real-time bar subscription wrapper |
| `IndicatorEngine` | `indicators/engine.py` | Fluent builder; mutates df, tracks meta |
| `_build_engine()` | `app.py` | Dispatches `fn` strings → `engine.add_*()` calls |
| `INDICATOR_PRESETS` | `app.py` | Named bundles of indicator configs |
| `init_stream()` | `ws/stream.py` | Starts Alpaca WS in daemon thread; exponential backoff retry |

### Indicator presets
| Preset | Indicators |
|--------|-----------|
| `trend` | EMA 20, EMA 50, BB, VWAP, Triple MA |
| `momentum` | RSI, MACD, Momentum Oscillator |
| `scalp` | EMA 9, EMA 21, RSI, Stochastic |
| `full` | All standard indicators |
| `vrb` | VWAP, Stochastic, ATR (VWAP Rubber Band) |
| `mburst` | EMA 9, EMA 21, Squeeze Momentum |
| `vcs` | RSI 7, VWAP, ATR (VWAP Cross Scalp) |

---

## RL Bot Integration Points

1. **Feature extraction** — `GET /api/chart/SPY?tf=5Min&limit=500&indicators=[...]`
   returns a labeled candle array ready for observation space construction.

2. **Live tick stream** — Subscribe via Socket.IO `tick` event; each completed
   bar is emitted as a candle dict with OHLCV.

3. **Signal overlay** — POST bot decisions to a new `/api/signal` endpoint
   *(not yet built)*; store in App.jsx state and pass to TradingChart as scatter
   markers (scatter marker support already exists in TradingChart).

4. **IndicatorEngine offline** — Import `IndicatorEngine` directly from
   `backend/indicators/engine.py` in your Python bot process to compute
   indicators on a local DataFrame without HTTP overhead.

---

## Environment — `backend/.env`

| Variable | Required | Purpose |
|----------|----------|---------|
| `DATA_PROVIDER` | yes | `yfinance` (default) or `alpaca` |
| `ALPACA_API_KEY` | if alpaca | Alpaca market data key |
| `ALPACA_SECRET_KEY` | if alpaca | Alpaca secret |
| `ALPACA_BASE_URL` | no | defaults to `paper-api.alpaca.markets` |
| `FLASK_PORT` | no | default `5000` |

Alpaca WS stream only starts if `ALPACA_API_KEY` is set and ≠ `your_alpaca_key_here`.

---

## Stack

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

## Extending — Add a Custom Indicator (4 touch points)

1. Create `backend/indicators/custom/<name>.py` — fn signature: `(df: DataFrame, **kwargs) → DataFrame`
2. Add `add_<name>()` to `IndicatorEngine` in `backend/indicators/engine.py` — append to `_indicator_meta`
3. Wire `elif fn == "<shortname>": engine.add_<name>(**kw)` in `_build_engine()` — `backend/app.py`
4. Expose in frontend: append `{ fn, label, params }` to `AVAILABLE` in `IndicatorPanel.jsx`

---

## Constraints & Gotchas

- **pandas-ta**: use `0.4.71b0` on Windows; on macOS/Python 3.14 use `0.4.67b0` with `numba` stubbed.
- **numpy**: must be `>=2.0.0`.
- **pandas**: must be `>=2.3.2`.
- **async_mode**: Flask-SocketIO set to `threading` (supports Python 3.14 on macOS); may need `eventlet` on Windows.
- **Timestamp serialization**: `engine.serialize()` uses `total_seconds()` for resolution-agnostic epoch conversion — do not replace with `.timestamp()`.
- **Socket singleton**: `useWebSocket` holds a module-level `_socket` variable; only one socket instance exists regardless of React re-renders.
- **AbortController**: `useChartData` cancels in-flight fetch on symbol/timeframe/indicator change — don't remove this or rapid changes will race.
