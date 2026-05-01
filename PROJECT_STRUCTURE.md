# Trading Dashboard — Project Structure & Description

## Overview

A self-hosted, real-time trading dashboard built for individual traders and quants. Provides multi-pane charting, a dynamic indicator panel with custom indicators, preset bundles, and live WebSocket streaming (Alpaca) or historical data (yfinance). Designed to be extended with new custom indicators using a clean builder pattern.

**Stack:** React 18 + Vite 5 (frontend) | Flask 3 + Flask-SocketIO + pandas-ta (backend) | Docker Compose (deployment)

---

## Directory Structure

```
trading-dashboard/
├── backend/
│   ├── app.py                      # Flask app — REST API + SocketIO event handlers
│   ├── requirements.txt            # Python dependencies (version-pinned)
│   ├── .env.example                # Environment variable template
│   ├── Dockerfile                  # Python 3.11-slim container
│   ├── data/
│   │   ├── __init__.py
│   │   └── source.py               # DataSource — yfinance (default) or Alpaca REST
│   ├── indicators/
│   │   ├── __init__.py
│   │   ├── engine.py               # IndicatorEngine — fluent builder, serialize()
│   │   └── custom/
│   │       ├── __init__.py
│   │       ├── momentum.py         # Momentum Oscillator + Squeeze Momentum
│   │       ├── vwap_band.py        # VWAP with upper/lower bands
│   │       └── triple_ma.py        # Triple MA crossover with buy/sell signal markers
│   └── ws/
│       ├── __init__.py
│       └── stream.py               # Alpaca WebSocket client → socketio.emit("tick")
├── frontend/
│   ├── index.html                  # Root HTML shell
│   ├── package.json                # npm dependencies
│   ├── vite.config.js              # Dev server (:3000) + proxy to backend (:5000)
│   ├── tailwind.config.js          # Dark terminal color palette
│   ├── postcss.config.js           # PostCSS + Tailwind build pipeline
│   └── src/
│       ├── main.jsx                # React entry point
│       ├── App.jsx                 # Root component — symbol/timeframe/indicator state
│       ├── components/
│       │   ├── TradingChart.jsx    # Lightweight Charts v4 wrapper, multi-pane layout
│       │   ├── IndicatorPanel.jsx  # Add/remove indicators + parameter config modal
│       │   ├── Toolbar.jsx         # Timeframe selector + preset buttons
│       │   └── SymbolSearch.jsx    # Symbol picker with dropdown search
│       ├── hooks/
│       │   ├── useChartData.js     # Fetches GET /api/chart/:symbol
│       │   └── useWebSocket.js     # Socket.IO client, subscribes to live ticks
│       └── styles/
│           └── globals.css         # Tailwind base + custom animations
├── docker-compose.yml              # Multi-service orchestration
├── README.md                       # Setup guide + API reference
├── HANDOFF.md                      # Detailed technical handoff (architecture, gotchas)
└── PROJECT_STRUCTURE.md            # This file
```

---

## Tech Stack

### Backend

| Package | Version | Role |
|---------|---------|------|
| Flask | 3.0.3 | HTTP server + REST API |
| Flask-SocketIO | 5.3.6 | WebSocket server (threading mode) |
| yfinance | ≥1.3.0 | Default market data provider (no keys needed) |
| alpaca-py | 0.26.0 | Live/paper data + real-time WebSocket ticks |
| pandas-ta | 0.4.71b0 | Technical indicator calculations (**must be this version** — 0.4.67 breaks on Windows) |
| pandas | ≥2.3.2 | DataFrame core |
| numpy | ≥2.0.0 | Required by pandas-ta (**must be 2.x** — 1.x breaks on Python 3.13) |
| eventlet | 0.36.1 | Async I/O for WebSocket streaming |
| python-dotenv | 1.0.1 | `.env` loading |

### Frontend

| Package | Version | Role |
|---------|---------|------|
| React | 18.3.0 | UI framework |
| Vite | 5.4.1 | Dev server + bundler |
| Lightweight Charts | 4.2.0 | High-performance candlestick charting |
| Tailwind CSS | 3.4.10 | Utility-first dark theme styling |
| socket.io-client | 4.7.5 | WebSocket client |

---

## API Surface

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/health` | `{ status, provider }` |
| GET | `/api/chart/:symbol` | OHLCV + indicator data. Query: `tf`, `limit`, `preset`, `indicators[]` |
| GET | `/api/presets` | `["trend", "momentum", "scalp", "full"]` |
| GET | `/api/indicators` | `{ standard: [...], custom: [...] }` with params schema |
| GET | `/api/search?q=` | Symbol search → `[{ symbol, name, exchange }]` |
| WS | `subscribe` event | Subscribe to live ticks; server emits `tick` events |

---

## Data Flow

### REST Request (historical)
```
GET /api/chart/AAPL?tf=1Day&preset=full
  → DataSource.get_bars()           # yfinance or Alpaca REST
  → IndicatorEngine(df)             # loads OHLCV into builder
    .add_ema(20).add_rsi()...       # mutates df, records indicator metadata
  → engine.serialize()              # { candles[], indicators[] }
  → useChartData() hook             # React fetch + state update
  → TradingChart.jsx                # pane 0 = candles, pane 1+ = sub-indicators
```

### Live Tick (Alpaca WebSocket)
```
Alpaca WS → ws/stream.py → socketio.emit("tick") → useWebSocket() → TradingChart state
```

---

## Indicators

### Standard (7)
EMA, SMA, Bollinger Bands, RSI, MACD, ATR, Stochastic

### Custom (5)
VWAP Band, Momentum Oscillator, Squeeze Momentum, Volume Profile, Triple MA Crossover

### Presets (4)
| Preset | Indicators bundled |
|--------|--------------------|
| `trend` | EMA 20/50/200, Bollinger Bands |
| `momentum` | RSI, MACD, Stochastic |
| `scalp` | EMA 9/21, RSI, ATR |
| `full` | All standard + custom indicators |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_PROVIDER` | `yfinance` | `yfinance` or `alpaca` |
| `ALPACA_API_KEY` | — | Required for Alpaca provider |
| `ALPACA_SECRET_KEY` | — | Required for Alpaca provider |
| `ALPACA_BASE_URL` | — | Paper or live Alpaca base URL |
| `FLASK_PORT` | `5000` | Backend port |

---

## Running Locally

```bash
# Backend
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows
pip install -r requirements.txt
cp .env.example .env   # fill in keys if using Alpaca
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

## Extending with a Custom Indicator

1. Add module in `backend/indicators/custom/your_indicator.py` implementing the calculation
2. Register method on `IndicatorEngine` in `backend/indicators/engine.py`
3. Wire into `_build_engine()` presets/dispatch in `backend/app.py`
4. Expose in `IndicatorPanel.jsx` parameter schema (frontend)

See `HANDOFF.md` for the full 4-touch-point walkthrough and constraints.

---

## Known Constraints

- **pandas-ta 0.4.71b0** — do not upgrade; 0.4.67 has Windows numba import errors
- **numpy ≥2.0** — pandas-ta fails with numpy 1.x on Python 3.13
- **Alpaca streaming** — stubbed for paper keys; requires live credentials to activate
- **Async mode** — uses `threading` (not `eventlet`) for macOS/Python 3.14 compatibility
- **Docker** — not validated after latest requirements update; treat as a starting point
