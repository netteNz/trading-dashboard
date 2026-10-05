# Handoff: Phase C (frontend consistency)

Phases A (backend correctness), B (chart fixes), the auth gate and the container/Azure
packaging are committed. Azure resources are **not** created yet; see `docs/DEPLOY_AZURE.md`.
Phase D (correcting and merging `FINDINGS.md`) comes after Phase C. `FINDINGS.md` is not committed yet.

## Setting up on a new machine (macOS)

```bash
git pull
cd backend && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env          # .env is gitignored; set AUTH_DISABLED=1 for local dev
python -m pytest tests -q     # expect 33 passed
python app.py                 # :5000

cd ../frontend && npm ci && npm run dev   # :3000
```

- RL signals resolve from `../../agentic-dev/reinforcement-learning-stocks/data/dashboard_signals`
  on macOS (candidate 1 in `backend/app.py` `get_signals`). Otherwise set `RL_SIGNALS_DIR`.
- The live stream needs real Alpaca keys and market hours. Without them, `/api/health` reports
  `stream: disabled` and that is expected.

## Phase C tasks

1. **Presets: one source of truth.**
   - Backend: `INDICATOR_PRESETS` in `backend/app.py` (7 presets: trend, momentum, scalp, full, vrb, mburst, vcs).
   - `frontend/src/components/Toolbar.jsx:13` hardcodes `PRESETS` with only 4 of them.
   - `IndicatorPanel.jsx` `COMBOS` duplicates the combo presets with their own labels and descriptions.
   - Fix: serve labels and descriptions from the backend. Make `/api/presets` return
     `[{name, label, desc, indicators}]`. Render both the toolbar and the combos list from that one fetch,
     done once in `App.jsx`.
2. **Stale preset highlight.** Once the user edits indicators by hand, the toolbar still highlights the
   last preset. Derive the active preset by comparing `indicators` to each preset (order-insensitive,
   using the `sameInstance` logic from `IndicatorPanel`) instead of keeping a separate `preset` state.
3. **One RL signals fetch.** `RLAgentMetrics.jsx:19` and `ExitControls.jsx` each fetch
   `/api/signals/<symbol>`. Fetch once in `App.jsx` (or a `useSignals(symbol)` hook) and pass the data down.
   The toggle then only decides whether `rlSignals` goes to `TradingChart`.
4. **LIVE badge shows the real stream state.** `App.jsx` and `Toolbar.jsx` show LIVE whenever the Socket.IO
   connection to our backend is up. The backend already emits `stream_status`
   (`starting|live|reconnecting|unauthorized|stopped|disabled`; see `backend/ws/stream.py`), which arrives
   on connect and on every change. Expose it from `useWebSocket` and show:
   - green LIVE only for `live`
   - yellow for `starting` and `reconnecting`
   - nothing (or a muted "DELAYED") otherwise

Verify in the browser with `AUTH_DISABLED=1`:
- All 7 presets appear in the toolbar.
- Editing an indicator clears the preset highlight.
- The Network tab shows a single `/api/signals` request per symbol change.
- The badge does not show LIVE without Alpaca keys.
- `npm run build` is clean and the backend tests still pass.
