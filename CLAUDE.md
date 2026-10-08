# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Stack

- **Backend**: Flask + Flask-SocketIO (`async_mode="threading"`, `backend/app.py`) — Python 3.12+ (pandas-ta 0.4.x requires it; CI and the image use 3.13)
- **Frontend**: React 18 + Vite + Lightweight Charts v4 + Tailwind CSS (`frontend/`)
- **Indicators**: pandas-ta (standard) + custom modules (`backend/indicators/custom/`)
- **Data**: yfinance (default, no keys) or Alpaca REST (requires env vars)
- **Live streaming**: Alpaca WebSocket → `ws/stream.py` → SocketIO `tick` event → `useWebSocket` hook

## Commands

```bash
# Backend (activate venv first)
cd backend && source venv/bin/activate
python app.py                        # http://localhost:5000

# Frontend
cd frontend && npm run dev           # http://localhost:3000
npm run build
npm run preview

# Both via Docker
cp backend/.env.example backend/.env
docker compose up --build

# Backend tests (synthetic data, no network)
cd backend && pip install -r requirements-dev.txt && python -m pytest tests -q

# Production-style single container (UI + API on :8000)
docker build -t tradeview:local . && docker run --rm -p 8000:8000 --env-file backend/.env tradeview:local
```

Deployment to Azure Container Apps: `docs/DEPLOY_AZURE.md`. No frontend tests yet.

### Auth

`backend/auth.py`: GitHub OAuth (with PKCE) → app-issued HS256 JWTs in httpOnly cookies
(`tv_access` 15 min, `tv_refresh` 7 days, `tv_csrf` double-submit). `gate()` protects every `/api/*`
except `/api/health`; Socket.IO `connect`/`subscribe` check `socket_user()`. Fails closed (503) when
not configured unless `AUTH_DISABLED=1`. Frontend: `src/lib/api.js` (`apiFetch`, silent refresh) and
`src/auth/` (`AuthProvider`, `LoginScreen`) — use `apiFetch`, never raw `fetch`, for `/api` calls.

## Environment

`backend/.env` (copy from `.env.example`):

| Variable            | Required | Notes                                        |
|---------------------|----------|----------------------------------------------|
| `DATA_PROVIDER`     | yes      | `yfinance` (default) or `alpaca`             |
| `ALPACA_API_KEY`    | no       | Required for real-time stream + Alpaca REST  |
| `ALPACA_SECRET_KEY` | no       | Required for real-time stream + Alpaca REST  |
| `ALPACA_BASE_URL`   | no       | Default: `https://paper-api.alpaca.markets`  |
| `ALPACA_FEED`       | no       | `iex` (default, free plan) or `sip`          |
| `FLASK_PORT`        | no       | Default: `5000`                              |
| `RL_SIGNALS_DIR`    | no       | Override path to RL signals JSON directory   |
| `AUTH_DISABLED`     | dev      | `1` = skip auth (local only)                 |
| `JWT_SECRET`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `ALLOWED_USERS`, `PUBLIC_URL` | prod | Auth gate config — see `.env.example` |

Live WebSocket streams only start if `ALPACA_API_KEY` is set and non-placeholder, and Alpaca accepts the
keys (checked once at startup). Two channels run in `ws/stream.py`: `stocks` (StockDataStream, pinned SPY) and
`crypto` (CryptoDataStream, 24/7, pinned BTC-USD); `subscribe(symbol)` routes by `markets.is_crypto`. Status is
per market: `stream` in `/api/health` is `{stocks, crypto}`, and the `stream_status` event is
`{market, status}` (broadcast on change, and one per market sent to each client on `subscribe`).
`useWebSocket(symbol, market)` returns the current market's as `streamStatus`; `StreamBadge` shows LIVE only for
`live`; MARKET CLOSED for stocks `starting` outside 09:30–16:00 ET on weekdays (the stream is connected but only
turns `live` on the first bar; holidays aren't modelled) — never for crypto; CONNECTING for
`starting`/`reconnecting` otherwise; DELAYED otherwise.

### Markets (stocks / crypto)

`backend/markets.py` holds `MARKETS` (label, default symbol, watchlist), served by `GET /api/markets`; the
frontend's watchlist, search popular list and footer all come from it. Crypto symbols are `BTC-USD` (Yahoo form)
everywhere in the app; Alpaca's `BTC/USD` exists only inside `data/source.py` (`to_/from_alpaca_crypto`).
Crypto bars always come from Alpaca's keyless crypto REST whatever `DATA_PROVIDER` says (Yahoo intraday crypto
has zero volume on ~⅓ of bars), falling back to Yahoo on error. Alpaca crypto volume is single-venue (coins, thin),
so volume-spike combos are stocks-only. The frontend derives `market` from the symbol (`lib/markets.js`
`marketOf`); the header `MarketToggle` jumps to the other market's default symbol, and the last symbol is
persisted (`tv.symbol`). VWAP anchors: `session` (US, NY midnight), `utc` (crypto intraday default), `rolling`
(daily/weekly).

## Architecture

### Request / Data Flow

```
GET /api/chart/:symbol?tf=&limit=&indicators=[]
  → DataSource.get_bars(limit + WARMUP_BARS)  # yfinance or Alpaca REST → OHLCV DataFrame (cached)
  → _build_engine(df, list)        # dispatches fn string → IndicatorEngine.add_*()
  → engine.signal_stats()          # combo scorecard, before trimming
  → engine.tail(limit).serialize() # { candles[], indicators[] } + stats, warnings
  → useChartData() hook            # React fetch with AbortController
  → TradingChart.jsx               # pane 0 = main overlay, pane 1+ = sub-charts

Live tick:
  Alpaca WS → ws/stream.py → socketio.emit("tick", room=symbol) → useWebSocket() → chart update
```

Vite proxies `/api` and `/socket.io` to `localhost:5000` in dev — no CORS wrangling needed locally.

- **Bar cache**: `DataSource.get_bars` keeps fetched frames in memory per `(symbol, tf, limit)` (60 s intraday,
  5 min 1Day, 15 min 1Week; `CACHE_*` in `data/source.py`), so indicator/preset toggles don't re-download.
  Errors aren't cached; callers get a copy.
- **Warm-up**: `get_chart` fetches `WARMUP_BARS` (250) extra bars, computes everything, then `engine.tail(limit)`
  — long indicators (SMA 200, EMA 55, regime) are valid from the first visible bar.
- **Scorecard**: `payload["stats"]` = `{COMBO: {horizon, base_up, buy, sell}}` from
  `indicators/custom/signal_stats.py` (`HORIZON_BARS` = 10): per side `n`, `open`, `hit`, `median_move_pct`,
  `median_mae_atr`, scored on the displayed window. It is the **only** module that reads future bars, and only
  to score existing markers. `SignalScorecard.jsx` shows it (hidden with SIGNALS off; collapse in `tv.scorecard`).
- `useChartData(…, enabled)` waits for `/api/presets` so the first load fetches once.

### IndicatorEngine Pattern

`IndicatorEngine` (`backend/indicators/engine.py`) is a chainable builder that mutates `self.df` (a copy of the OHLCV DataFrame) and appends to `self._indicator_meta`. `serialize()` converts the df to the candle JSON contract.

Indicator meta shape drives frontend rendering:
```python
{
    "key":       "COL_NAME",          # must match a column in self.df
    "type":      "line"|"histogram"|"scatter",
    "pane":      0,                   # 0 = main chart overlay; 1+ = numbered sub-pane
    "color":     "#hex",
    "label":     "Display Name",
    "lineStyle": "dashed"|"dotted",   # optional
    "levels":    [{"value": 70, "color": "#hex"}],  # optional reference lines
    "colorMap":  {"1": "#hex", "-1": "#hex"},       # optional, histogram: colour per bar value
}
```

Sub-panes are rendered as separate `lightweight-charts` chart instances stacked below the main chart in `TradingChart.jsx`.
They are resizable (drag a pane's top edge; it trades height with the visible pane above) and hideable (eye icon →
20px labelled strip). The layout is stored as weights + hidden flags per pane number in localStorage
(`tv.paneLayout`) and applied by `applyLayout()` without rebuilding charts, so zoom survives. Pane numbers are fixed
per indicator type (RSI 1, MACD 2, ATR 3, Stoch 4, Vol 5, Mom 6, SQZ 7, TMA 8, ADX 9, OBV 10, CMF 11, Regime 12;
MFI shares RSI's pane), so a new indicator that needs its own pane takes the next free number.

### Adding a Custom Indicator (3 touch points)

**1. Create** `backend/indicators/custom/<name>.py` — return a DataFrame with named columns.

**2. Register** in `IndicatorEngine` (`backend/indicators/engine.py`):
```python
from indicators.custom.<name> import <name>

def add_<name>(self, ...) -> "IndicatorEngine":
    sfx = self._suffix("<FIRST_COL>")      # "" first time, "_2" if added again
    result = <name>(self.df, ...)
    self._concat(result, sfx)              # renames columns with sfx, then concats
    self._indicator_meta.append({"key": "<FIRST_COL>" + sfx, ...})
    return self
```

**3. Register** in the `INDICATORS` registry in `backend/app.py` (fn → engine method + kwarg schema; unknown fns/kwargs are rejected with a warning):
```python
"<shortname>": ("add_<name>", {"<kwarg>": (int, 1, 500)}),
```

Optionally expose in `frontend/src/components/IndicatorPanel.jsx` by appending to the `AVAILABLE` array.

### RL Signal Integration

`/api/signals/<symbol>` reads pre-exported JSON from a sibling repo directory. Lookup
order (`backend/app.py:135-142`):
1. `RL_SIGNALS_DIR` env var, if set
2. `../../agentic-dev/reinforcement-learning-stocks/data/dashboard_signals/<symbol>_signals.json`
3. `../../agentic-development/reinforcement-learning-stocks/data/dashboard_signals/<symbol>_signals.json`

On Windows checkouts candidate 2 typically doesn't exist and candidate 3 is what
actually resolves.
- JSON is generated by `export_signals_for_dashboard.py` in the RL repo

`useRLSignals(symbol)` (`frontend/src/hooks/useRLSignals.js`) fetches this route once per symbol in `App.jsx`.
`RLAgentMetrics.jsx` (right panel) gets the data as a prop; `ExitControls.jsx` (toolbar) is a controlled toggle,
and `App.jsx` passes `rlSignals` to `TradingChart` for marker overlay only while it is on.

### Presets

Defined as `INDICATOR_PRESETS` dict in `backend/app.py`, with display info (label, desc, `kind` core|combo, tf,
`markets` — which market toggle lists it) in `PRESET_INFO`; `App.jsx` filters presets to the active market. `GET /api/presets` serves both; the frontend fetches it once in `App.jsx` and renders the
toolbar (core buttons + combos select) and the IndicatorPanel combo cards from it — no preset lists in the
frontend. The highlighted preset is derived (exact match of the active list), not stored. Preset name is passed
as `?preset=` query param. Custom `indicators` JSON array param takes precedence over preset.

Current presets: core `trend`, `momentum`, `scalp`, `full`; combos `ttp`, `tsf`, `ksqz`, `bbrsi`, `osc`, `tmt`,
`wvs`, `vrb`, `mburst`, `vcs`, `regime`, `rdiv` (confirmed RSI divergence: marked on the bar that confirms the
pivot, 3 bars after the swing, so it never repaints); crypto-only combos `bmsb`, `cpb`, `uvb`.

Combo presets end with `{"fn": "sig", "kwargs": {"combo": "<key>"}}`: BUY/SELL confluence markers from
`backend/indicators/custom/combo_signals.py` (`SIGNAL_RULES`; markers on the bar a rule turns true, no
look-ahead — enforced by tests on daily `rolling` and hourly `utc` bars for every rule). The toolbar SIGNALS toggle hides all scatter markers client side.

### Frontend State (App.jsx)

Top-level state lives in `App.jsx`: `symbol` (persisted; `market` is derived from it), `markets` (from `/api/markets`), `timeframe`, `presets` (from `/api/presets`), `indicators` (active indicator list), `rlEnabled`, `showSignals` (persisted in localStorage), sidebar/panel collapse flags. `activePreset` and `rlSignals` are derived with `useMemo` (keep `rlSignals` referentially stable — it is a `TradingChart` rebuild dependency). `useChartData` re-fetches whenever symbol, timeframe, or indicators change (stable via `JSON.stringify`).

### Tailwind Theme

Dark blue GitHub-inspired theme. Custom color tokens used throughout: `bg-surface-0/1/2/3/4`, `text-accent-cyan`, `text-accent-green`, `text-accent-red`, `text-accent-yellow`. Defined in `frontend/tailwind.config.js`.
