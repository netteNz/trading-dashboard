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

## Session log — 2026-10-07 (branch `phase-c-combos`, merged into `main`, not pushed)

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

## Open ideas (not scheduled)

- Markers are rule onsets, not backtested edges. A backtest of each rule (hit rate, avg R) would say
  which combos deserve trust on which timeframe.
- A "collapse all sub-panes" control, if per-pane eyes turn out to be too fiddly.
- Exchange holiday calendar for the MARKET CLOSED badge.
