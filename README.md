# ⬡ TradeView — Personal Trading Dashboard

A self-hosted charting dashboard with unlimited indicators, custom indicator engine, and live WebSocket streaming — built to replace TradingView's 2-indicator cap.

---

## Stack

| Layer     | Tech                                      |
|-----------|-------------------------------------------|
| Frontend  | React 18 + Vite + Lightweight Charts v4  |
| Backend   | Flask + Flask-SocketIO + eventlet         |
| Indicators| pandas-ta + custom Python modules         |
| Data      | yfinance (free) · Alpaca (real-time)      |
| Streaming | Alpaca WebSocket → SocketIO → React       |

---

## Quick Start

### 1. Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — set DATA_PROVIDER=yfinance to start without Alpaca keys

python app.py
# → http://localhost:5000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

### 3. Docker (both at once)

```bash
cp backend/.env.example backend/.env
docker compose up --build
```

---

## API Reference

### `GET /api/chart/:symbol`

| Param        | Default  | Description                          |
|--------------|----------|--------------------------------------|
| `tf`         | `1Day`   | Timeframe: `1Min` `5Min` `1Hour` etc |
| `limit`      | `500`    | Number of bars                        |
| `preset`     | `full`   | `trend` `momentum` `scalp` `full`    |
| `indicators` | —        | JSON array of indicator configs       |

**Response:**
```json
{
  "candles": [
    { "time": 1712534400, "open": 512.1, "high": 515.3, "low": 510.0, "close": 514.2, "volume": 98123456,
      "EMA_20": 511.4, "RSI_14": 58.2, "MACD": 1.23, "VWAP": 512.8, ... }
  ],
  "indicators": [
    { "key": "EMA_20", "type": "line", "pane": 0, "color": "#38bdf8", "label": "EMA 20" },
    ...
  ]
}
```

### `GET /api/presets` → list of preset names  
### `GET /api/indicators` → available standard + custom indicator keys  
### `GET /api/search?q=AAPL` → symbol lookup  

---

## Custom Indicators

Drop a new file in `backend/indicators/custom/` and register it in `engine.py`:

```python
# backend/indicators/custom/my_indicator.py
def my_indicator(df, period=14):
    result = pd.DataFrame(index=df.index)
    result["MY_IND"] = df["close"].rolling(period).mean()  # your logic
    return result

# backend/indicators/engine.py  →  IndicatorEngine class
def add_my_indicator(self, period=14):
    result = my_indicator(self.df, period=period)
    self.df = pd.concat([self.df, result], axis=1)
    self._indicator_meta.append({
        "key": "MY_IND", "type": "line", "pane": 1,
        "color": "#f472b6", "label": "My Indicator"
    })
    return self
```

Then call it in `app.py`:
```python
engine.add_my_indicator(period=21)
```

---

## Timeframes

| Value   | Description     |
|---------|-----------------|
| `1Min`  | 1-minute bars   |
| `5Min`  | 5-minute bars   |
| `15Min` | 15-minute bars  |
| `30Min` | 30-minute bars  |
| `1Hour` | Hourly bars     |
| `1Day`  | Daily bars      |
| `1Week` | Weekly bars     |

---

## Live Streaming (Alpaca)

1. Set `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` in `backend/.env`
2. Set `DATA_PROVIDER=alpaca`
3. Restart backend — the stream starts automatically for default symbols
4. Frontend subscribes via SocketIO on symbol change

---

## Environment Variables

```env
ALPACA_API_KEY=...
ALPACA_SECRET_KEY=...
ALPACA_BASE_URL=https://paper-api.alpaca.markets
DATA_PROVIDER=yfinance          # or alpaca
FLASK_ENV=development
FLASK_PORT=5000
```
