# TradeView — Agent Handoff
> Generated: 2026-04-28T20:59:00-04:00  ·  Stack: React 18 + Vite · Flask + SocketIO · Python 3.13

## Quick Start
```bash
# Backend — activate venv first (Windows)
cd backend && venv\Scripts\activate && python app.py

# Frontend
cd frontend && npm run dev
```
URLs: Backend → http://localhost:5000  ·  Frontend → http://localhost:3000

## File Map
```
backend/
  app.py               ← Flask app, routes, _build_engine(), SocketIO events
  requirements.txt
  .env.example / .env
  data/
    source.py          ← DataSource class (yfinance + Alpaca)
  indicators/
    engine.py          ← IndicatorEngine — wraps df, exposes add_*() methods
    custom/
      momentum.py      ← add_momentum_oscillator(), add_squeeze_momentum()
      vwap_band.py     ← add_vwap_band()
  ws/
    stream.py          ← Alpaca WS → socketio.emit("tick")
frontend/
  index.html
  vite.config.js
  src/
    App.jsx            ← root; orchestrates symbol/tf/indicator state
    main.jsx
    components/
      TradingChart.jsx ← Lightweight Charts; pane 0 = main, pane 1+ = sub
      IndicatorPanel.jsx ← AVAILABLE list; emits indicator config to App
      Toolbar.jsx      ← timeframe selector, preset picker
      SymbolSearch.jsx ← calls /api/search
    hooks/
      useChartData.js  ← fetches /api/chart/:symbol, returns {candles, indicators}
      useWebSocket.js  ← socket.io-client; subscribes, streams ticks to TradingChart
docker-compose.yml
```

## Stack
| Layer | Tech | Version | Notes |
|-------|------|---------|-------|
| Frontend runtime | React | ^18.3.0 | Vite 5.4, ESM |
| Charts | Lightweight Charts | ^4.2.0 | pane-based, no Canvas workaround needed |
| Styling | Tailwind CSS | ^3.4.10 | |
| WS client | socket.io-client | ^4.7.5 | |
| Backend runtime | Python | 3.13.x | |
| Web server | Flask + Flask-SocketIO | 3.0.3 / 5.3.6 | eventlet async_mode |
| Indicators | pandas-ta | 0.4.71b0 | **not** 0.4.67 (posix bug on Windows) |
| Data (default) | yfinance | ≥1.3.0 (resolved) | pinned as ≥0.2.40 |
| Data (live) | alpaca-py | 0.26.0 | requires keys in .env |
| DataFrame | pandas / numpy | ≥3.0.2 / ≥2.2.6 | 1.x numpy breaks on Py 3.13 |

## Environment — `backend/.env`
| Var | Required | Purpose |
|-----|----------|---------|
| `DATA_PROVIDER` | yes | `yfinance` (default) or `alpaca` |
| `ALPACA_API_KEY` | if alpaca | Alpaca market data key |
| `ALPACA_SECRET_KEY` | if alpaca | Alpaca secret |
| `ALPACA_BASE_URL` | no | defaults to paper-api.alpaca.markets |
| `FLASK_ENV` | no | `development` |
| `FLASK_PORT` | no | `5000` |

Alpaca WS stream only starts if `ALPACA_API_KEY` is set and ≠ `your_alpaca_key_here`.

## API Surface
| Method | Route | Key Params | Returns |
|--------|-------|-----------|---------|
| GET | `/api/health` | — | `{status, provider}` |
| GET | `/api/chart/:symbol` | `tf` `limit` `preset` `indicators` (JSON) | `{candles[], indicators[]}` |
| GET | `/api/presets` | — | `string[]` |
| GET | `/api/indicators` | — | `{standard[], custom[]}` |
| GET | `/api/search?q=` | `q` | `{symbol, name, exchange}[]` |
| WS | `subscribe` event | `{symbol}` | streams `tick` events |

`tf` values: `1Min 5Min 15Min 30Min 1Hour 1Day 1Week`  
`preset` values: `trend momentum scalp full`  
Candle shape: `{ time: unix_seconds, open, high, low, close, volume, ...indicator_keys }`  
Indicator meta shape: `{ key, type: "line"|"histogram", pane: int, color, label }`

## Data Flow
```
GET /api/chart/:symbol
  → app._build_engine()        app.py:41
  → DataSource.get_bars()      data/source.py:47   (yfinance or Alpaca REST)
  → IndicatorEngine(df)        indicators/engine.py (loads OHLCV into self.df)
      .add_*()                                      (mutates df + appends _indicator_meta)
  → engine.serialize()                              → {candles[], indicators[]}
  → useChartData()             hooks/useChartData.js
  → TradingChart.jsx           pane 0 = main chart, pane 1+ = sub-panes

Live tick:
  Alpaca WS → ws/stream.py → socketio.emit("tick") → useWebSocket.js → TradingChart update
```

## Key Abstractions
| Name | File | Purpose |
|------|------|---------|
| `DataSource` | `backend/data/source.py` | Unified OHLCV fetch; provider switch via env |
| `IndicatorEngine` | `backend/indicators/engine.py` | Fluent builder; mutates df, tracks meta |
| `_build_engine()` | `backend/app.py:41` | Dispatches `fn` strings → engine.add_*() calls |
| `INDICATOR_PRESETS` | `backend/app.py:31` | Named bundles of indicator configs |
| `TradingChart` | `frontend/src/components/TradingChart.jsx` | Lightweight Charts wrapper; multi-pane |
| `useChartData` | `frontend/src/hooks/useChartData.js` | Fetches + normalizes chart API response |
| `useWebSocket` | `frontend/src/hooks/useWebSocket.js` | socket.io-client; live tick injection |
| `IndicatorPanel` | `frontend/src/components/IndicatorPanel.jsx` | AVAILABLE list; add here to expose UI |

## Extend — Custom Indicator (3 touch points)
1. Create `backend/indicators/custom/<name>.py` — fn signature: `(df: DataFrame, **kwargs) → DataFrame`
2. Add `add_<name>()` method to `IndicatorEngine` in `backend/indicators/engine.py` — append to `_indicator_meta`
3. Wire `elif fn == "<shortname>": engine.add_<name>(**kw)` in `_build_engine()` — `backend/app.py:47–58`
4. Expose in frontend: append `{ fn, label, params }` to `AVAILABLE` in `IndicatorPanel.jsx`

## Constraints & Gotchas
- **pandas-ta**: use `0.4.71b0` — `0.4.67b0` imports `posix` module (Linux-only), crashes on Windows
- **numpy**: must be `>=2.0.0` — `1.26.x` does not support Python 3.13
- **pandas**: must be `>=2.3.2` — required by pandas-ta 0.4.x; pip resolves to 3.0.2
- **yfinance**: `0.2.40` pin in original README is stale — pip resolves to 1.3.0, works fine
- **eventlet**: Flask-SocketIO async_mode is `eventlet` — do not switch to `threading` without testing WS
- **vite port**: frontend dev server runs on 3000 (configured in vite.config.js), not the Vite default 5173
- **Alpaca 1Week**: `TimeFrame.Week` not mapped in `_get_bars_alpaca()` — falls back to Day silently
- **search_symbols**: returns single-item list via `fast_info` — not a real search index

## Out of Scope
- `backend/ws/stream.py` Alpaca streaming: stubbed for paper keys; not testable without live Alpaca credentials
- Docker: `docker-compose.yml` exists but has not been validated against the updated requirements
