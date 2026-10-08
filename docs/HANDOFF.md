# Handoff: Phase D (correct and merge FINDINGS.md)

Phases A (backend correctness), B (chart fixes), C (frontend consistency), the auth gate, the
container/Azure packaging and the TA combo work are done. Azure resources are **not** created yet;
see `docs/DEPLOY_AZURE.md`. Next is Phase D: correct `FINDINGS.md` against the current code (many of
its items were fixed in A–C) and merge it.

## Setting up on a new machine (macOS)

```bash
git pull
# needs Python 3.12+ (pandas-ta 0.4.x); check python3 --version, else e.g. brew install python@3.13
cd backend && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env          # .env is gitignored; set AUTH_DISABLED=1 for local dev
python -m pytest tests -q     # expect 42 passed
python app.py                 # :5000

cd ../frontend && npm ci && npm run dev   # :3000
```

- RL signals resolve from `../../agentic-dev/reinforcement-learning-stocks/data/dashboard_signals`
  on macOS (candidate 1 in `backend/app.py` `get_signals`). Otherwise set `RL_SIGNALS_DIR`.
- The live stream needs real Alpaca keys and market hours. Without them, `/api/health` reports
  `stream: disabled` and the badge shows DELAYED; that is expected. With valid keys outside market
  hours it shows MARKET CLOSED (status stays `starting` until the first bar).

## What Phase C + combos changed

- **Presets** come from `GET /api/presets` (`INDICATOR_PRESETS` + `PRESET_INFO` in `backend/app.py`).
  Toolbar: core buttons + combos select. The highlight is derived from the active list.
- **RL signals**: one fetch per symbol (`useRLSignals`); `ExitControls` and `RLAgentMetrics` are prop-driven.
- **Stream badge**: `stream_status` is sent on `subscribe`; `StreamBadge` shows LIVE only for `live`.
- **New indicators**: `adx`, `kc`, `mfi`, `obv`, `cmf`, `mrd` (market regime, per-bar colours via `colorMap`).
- **Combos**: `ttp tsf ksqz bbrsi osc tmt wvs vrb mburst vcs regime`. All but `regime` include a `sig`
  entry with BUY/SELL markers (`backend/indicators/custom/combo_signals.py`), hidden by the SIGNALS toggle.
- Deliberately skipped: Divergence Scanner (needs future pivots, would repaint), Opening Range Break
  (session state), Adaptive RSI.
- **Sub-panes**: resizable (drag the top edge) and hideable (eye icon); layout persists in localStorage.
- **Badge**: MARKET CLOSED outside regular hours instead of a misleading CONNECTING.

## Session log — 2026-10-07 (branch `phase-c-combos`, merged into `main` and pushed)

| Commit | What |
|---|---|
| `ab451ef` | Backend: ADX/KC/MFI/OBV/CMF/Market Regime, `combo_signals.py` (10 rules), 8 combo presets, `PRESET_INFO`, `/api/presets` objects, `stream_status` on subscribe, 9 new tests |
| `75d151e` | Frontend Phase C: presets from the backend, derived highlight, `useRLSignals`, `StreamBadge`, SIGNALS toggle, regime colours |
| `71bf65f` | Docs: CLAUDE.md, README, ARCHITECTURE, combo-builder skill, this handoff |
| `e71008a` | Resizable/hideable sub-panes; MARKET CLOSED badge |

Verified: 42 backend tests pass, `npm run build` clean, every preset builds without warnings on real
yfinance data (QQQ 1D and 5Min), and the browser checks from the Phase C list (all presets listed,
highlight clears on edit, one `/api/signals` per symbol change, no LIVE without bars, toggle keeps zoom,
pane layout survives a symbol change).

Correction found this session: the old handoff said `stream_status` arrives on connect. It didn't (only on
change); it is now sent on `subscribe`.

Later the same session, on `main`:
- `1fc3e80` CI actions moved to their Node 24 majors (checkout v7, setup-python v7, setup-buildx v4,
  login v4, build-push v7). Run green, Node 20 warning gone.
- Yahoo fetch sized to the bar limit (`yf_lookback()` in `backend/data/source.py`, test added; 43 tests).

## Findings for next session (from running the production container locally)

Local container: Docker Desktop's CLI is at `C:\Program Files\Docker\Docker\resources\bin` (now on the
user PATH). `docker build -t tradeview:local . && docker run -d --name tradeview-local -p 8000:8000
--env-file backend/.env -e AUTH_DISABLED=1 tradeview:local` → http://localhost:8000.

1. **Bug, not fixed: Socket.IO rejects the container's own origin.** The log shows
   `http://localhost:8000 is not an accepted origin`. `cors_allowed_origins` is an explicit list
   (`CORS_ORIGINS` default = the Vite dev origins, plus `PUBLIC_URL`), and with a list python-engineio does
   **not** add the request's own origin (`engineio/base_server.py` `_cors_allowed_origins`). So a local
   container run without `PUBLIC_URL` gets no live ticks / stream badge and the client retries forever.
   Azure is fine (PUBLIC_URL set) and the Vite dev server is fine (`localhost:3000` is listed).
   Fix: pass a callable `(origin, environ)` that allows the allow-list **or** `scheme://host` of the request
   (honouring `X-Forwarded-Proto/Host`, which ProxyFix already trusts behind ACA). Add a test with
   `socketio.test_client` sending a same-origin `Origin` header. Quick workaround: `-e PUBLIC_URL=http://localhost:8000`.
2. **Ticker switch latency.** Measured: server ~0.3–0.6 s for a ticker not fetched recently (almost all
   Yahoo), ~70 ms when Yahoo answers from its side quickly; browser render is negligible (no long tasks).
   - Occasional multi-second spikes (5 s, one 15 s) are Yahoo; nothing in our code.
   - First request after a container start takes ~5 s (worker's first yfinance call warms up).
   - Fixed: daily charts downloaded 5 years to keep 500 bars; now `yf_lookback()` sizes the window
     (1Min fetch 0.55 s → 0.13 s; every timeframe still returns 500 bars; 5000 daily bars still works).
   - Done (2026-10-08): in-memory bar cache in `DataSource.get_bars` (60 s intraday, 5 min daily). Indicator
     and preset toggles on SPY 1D went from ~0.8–2 s to ~15 ms.
   - Rapid switching cancels requests in the browser, but the server still finishes each one, competing
     in the single gunicorn worker (`-w 1`, gthread).
3. **Pitfall: only one Alpaca stream per key.** Importing `app` in a second process with `ENABLE_STREAM=1`
   (e.g. `docker exec … python -c "import app"`) starts another stream and Alpaca answers
   `connection limit exceeded`. For ad-hoc scripts in the container set `ENABLE_STREAM=0`. Same rule for
   staging slots / a local `python app.py` while the container runs.
4. **CI notice:** `ubuntu-latest` moves to Ubuntu 26 from 2026-10-19. Should be harmless (Python pinned by
   setup-python, build in Docker); pin `ubuntu-24.04` if it causes trouble.

## Open ideas (not scheduled)

- Markers are rule onsets, not backtested edges. Partly answered (2026-10-08): the in-sample scorecard
  (`signal_stats.py`, hit rate vs baseline, median move, drawdown in ATR over 10 bars). A proper
  walk-forward backtest with costs is still open.
- A "collapse all sub-panes" control, if per-pane eyes turn out to be too fiddly.
- Exchange holiday calendar for the MARKET CLOSED badge.
