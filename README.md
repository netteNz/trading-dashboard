# TradeView — Agent Handoff

Self-hosted trading dashboard. Unlimited indicators, custom indicator engine, live WebSocket streaming.

---

## STACK

- Frontend: React 18 + Vite + Lightweight Charts v4 — `frontend/`
- Backend: Flask + Flask-SocketIO + eventlet — `backend/`
- Indicators: pandas-ta + custom modules — `backend/indicators/custom/`
- Data: yfinance (default, no keys) · Alpaca (real-time, requires keys)
- Streaming: Alpaca WebSocket → Flask-SocketIO → React useWebSocket hook

---

## SETUP

Run in order. Do not skip steps.

```bash
# 1. Backend
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

# 2. Frontend
cd ../frontend
npm install
```

---

## ENVIRONMENT

File: `backend/.env`

| Variable            | Required | Default                             | Notes                             |
|---------------------|----------|-------------------------------------|-----------------------------------|
| `DATA_PROVIDER`     | yes      | `yfinance`                          | set `alpaca` for real-time        |
| `ALPACA_API_KEY`    | no       | —                                   | required if DATA_PROVIDER=alpaca  |
| `ALPACA_SECRET_KEY` | no       | —                                   | required if DATA_PROVIDER=alpaca  |
| `ALPACA_BASE_URL`   | no       | `https://paper-api.alpaca.markets`  |                                   |
| `FLASK_ENV`         | no       | `development`                       |                                   |
| `FLASK_PORT`        | no       | `5000`                              |                                   |

---

## ENTRYPOINTS

```bash
# Backend — http://localhost:5000
cd backend && source venv/bin/activate && python app.py

# Frontend — http://localhost:3000
cd frontend && npm run dev

# Both via Docker
cp backend/.env.example backend/.env
docker compose up --build
```

---

## API

| Method | Route                | Params                                                                  | Returns                        |
|--------|----------------------|-------------------------------------------------------------------------|--------------------------------|
| GET    | `/api/chart/:symbol` | `tf` (default `1Day`), `limit` (default `500`), `preset`, `indicators` | `{ candles[], indicators[] }`  |
| GET    | `/api/presets`       | —                                                                       | `string[]`                     |
| GET    | `/api/indicators`    | —                                                                       | `{ standard[], custom[] }`     |
| GET    | `/api/search?q=`     | `q`                                                                     | `{ symbol, name, exchange }[]` |

`tf` values: `1Min` `5Min` `15Min` `30Min` `1Hour` `1Day` `1Week`

`preset` values: `trend` `momentum` `scalp` `full`

`indicators` param: JSON array — `[{"fn":"ema","kwargs":{"length":20}}]`

Candle object shape: `{ time: unix_seconds, open, high, low, close, volume, ...indicator_keys }`

Indicator meta shape: `{ key, type: "line"|"histogram", pane: int, color: hex, label, lineStyle?, levels? }`

---

## EXTEND — Adding a Custom Indicator

Follow this exact pattern. Three touch points.

**1. Create** `backend/indicators/custom/<name>.py`

```python
import pandas as pd

def <name>(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    result = pd.DataFrame(index=df.index)
    result["<COL_KEY>"] = # your logic using df["close"], df["high"], df["low"], df["volume"]
    return result
```

**2. Register** in `backend/indicators/engine.py` — add a method to `IndicatorEngine`:

```python
from indicators.custom.<name> import <name>

def add_<name>(self, period: int = 14) -> "IndicatorEngine":
    result = <name>(self.df, period=period)
    self.df = pd.concat([self.df, result], axis=1)
    self._indicator_meta.append({
        "key":   "<COL_KEY>",
        "type":  "line",          # or "histogram"
        "pane":  1,               # 0 = main chart overlay, 1+ = sub-pane
        "color": "#hex",
        "label": "Display Name",
    })
    return self
```

**3. Wire** in `backend/app.py` inside `_build_engine()`:

```python
elif fn == "<shortname>": engine.add_<name>(**kw)
```

Then expose in `frontend/src/components/IndicatorPanel.jsx` by appending to `AVAILABLE`:

```js
{ fn: "<shortname>", label: "Display Name", params: [{ key: "period", label: "Period", default: 14 }] }
```

---

## DATA FLOW

```
GET /api/chart/:symbol
  → DataSource.get_bars()        # yfinance or Alpaca REST
  → IndicatorEngine(df)          # loads OHLCV
      .add_*()                   # mutates self.df + appends to _indicator_meta
  → engine.serialize()           # { candles[], indicators[] }
  → useChartData()               # React fetch hook
  → TradingChart.jsx             # pane 0 = main chart, pane 1+ = sub-charts

Live tick:
  Alpaca WS → ws/stream.py → socketio.emit("tick") → useWebSocket() → TradingChart update
```