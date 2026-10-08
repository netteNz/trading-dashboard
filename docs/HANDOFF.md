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
  hours it shows CONNECTING (status stays `starting` until the first bar).

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

## Open ideas (not scheduled)

- Many sub-panes get thin: `TradingChart` splits 45% of the height evenly with no minimum.
- Markers are rule onsets, not backtested edges. A backtest of each rule (hit rate, avg R) would say
  which combos deserve trust on which timeframe.
