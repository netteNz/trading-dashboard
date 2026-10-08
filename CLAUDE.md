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

Live WebSocket stream only starts if `ALPACA_API_KEY` is set and non-placeholder, and Alpaca accepts the
keys (checked once at startup); status is exposed as `stream` in `/api/health` and the `stream_status` event
(broadcast on change, and sent to each client on `subscribe`). `useWebSocket` returns it as `streamStatus`;
`StreamBadge` shows LIVE only for `live`, CONNECTING for `starting`/`reconnecting` (with valid keys this persists
outside market hours, until the first bar), DELAYED otherwise.

## Architecture

### Request / Data Flow

```
GET /api/chart/:symbol?tf=&limit=&indicators=[]
  → DataSource.get_bars()          # yfinance or Alpaca REST → OHLCV DataFrame
  → _build_engine(df, list)        # dispatches fn string → IndicatorEngine.add_*()
  → IndicatorEngine.serialize()    # { candles[], indicators[] }
  → useChartData() hook            # React fetch with AbortController
  → TradingChart.jsx               # pane 0 = main overlay, pane 1+ = sub-charts

Live tick:
  Alpaca WS → ws/stream.py → socketio.emit("tick", room=symbol) → useWebSocket() → chart update
```

Vite proxies `/api` and `/socket.io` to `localhost:5000` in dev — no CORS wrangling needed locally.

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
}
```

Sub-panes are rendered as separate `lightweight-charts` chart instances stacked below the main chart in `TradingChart.jsx`.

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

Defined as `INDICATOR_PRESETS` dict in `backend/app.py`, with display info (label, desc, `kind` core|combo, tf)
in `PRESET_INFO`. `GET /api/presets` serves both; the frontend fetches it once in `App.jsx` and renders the
toolbar (core buttons + combos select) and the IndicatorPanel combo cards from it — no preset lists in the
frontend. The highlighted preset is derived (exact match of the active list), not stored. Preset name is passed
as `?preset=` query param. Custom `indicators` JSON array param takes precedence over preset.

Current presets: core `trend`, `momentum`, `scalp`, `full`; combos `ttp`, `tsf`, `ksqz`, `bbrsi`, `osc`, `tmt`,
`wvs`, `vrb`, `mburst`, `vcs`, `regime`.

Combo presets end with `{"fn": "sig", "kwargs": {"combo": "<key>"}}`: BUY/SELL confluence markers from
`backend/indicators/custom/combo_signals.py` (`SIGNAL_RULES`; markers on the bar a rule turns true, no
look-ahead — enforced by a test). The toolbar SIGNALS toggle hides all scatter markers client side.

### Frontend State (App.jsx)

Top-level state lives in `App.jsx`: `symbol`, `timeframe`, `presets` (from `/api/presets`), `indicators` (active indicator list), `rlEnabled`, `showSignals` (persisted in localStorage), sidebar/panel collapse flags. `activePreset` and `rlSignals` are derived with `useMemo` (keep `rlSignals` referentially stable — it is a `TradingChart` rebuild dependency). `useChartData` re-fetches whenever symbol, timeframe, or indicators change (stable via `JSON.stringify`).

### Tailwind Theme

Dark blue GitHub-inspired theme. Custom color tokens used throughout: `bg-surface-0/1/2/3/4`, `text-accent-cyan`, `text-accent-green`, `text-accent-red`, `text-accent-yellow`. Defined in `frontend/tailwind.config.js`.
