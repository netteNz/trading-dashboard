# Trading Dashboard — Active Backlog

**Last Updated**: 2026-05-25

---

## Known Issues

### NVDA Signal Bias (HIGH)
All 202 NVDA ensemble models output positive SAC weights → unanimous buy votes on every bar → only 1 trade counted across 2847 signals. AMD has 893 trades and is healthy.

- [ ] Check leaderboard for NVDA model configs; compare vote distribution per bar
- [ ] Determine if NVDA training data has a persistent trend bias
- [ ] Consider minimum confidence filter: only signal when ≥4/5 models agree
- [ ] Consider hold period: no re-entry within N bars of last signal

### Chart Zoom Default (LOW)
Chart initialises at the far-left of the data range on first load.

- [ ] Set default view to most-recent 100–200 bars
- [ ] Add "Reset Zoom" button
- [ ] Optionally persist zoom state in localStorage

---

## TODO

### HIGH

- [ ] **Signal quality filter** — minimum confidence threshold + signal hold period + stop-loss/take-profit in export script
- [ ] **RLAgentMetrics smoke test** — confirm panel renders for NVDA/AMD, collapse/expand arrows work, metrics update on symbol change, green/red/orange colour coding is correct

### MEDIUM

- [ ] **Signal overlay on chart** — render buy/sell markers from RL signals on the candlestick pane in TradingChart.jsx; colour-code by ensemble confidence
- [ ] **Win rate metric** — add `win_rate_pct` to export script: `(trades_won / total_trades) * 100`
- [ ] **Live signal refresh** — schedule export script hourly (Windows Task Scheduler or cron); add auto-refresh + "Last updated" timestamp in panel
- [ ] **Toolbar price direction** — replace hardcoded `isUp = true` with prev-close comparison

### LOW

- [ ] **Trade history tab** — show individual entry/exit prices, duration, P&L per trade; consider a trade heatmap
- [ ] **Leaderboard deep-link** — show top-3 models with stats; add model details modal
- [ ] **Signal payload caching** — add 5–15 min TTL cache in backend `/api/signals/<symbol>` (currently reads JSON from disk on every request)
- [ ] **Consistent observation shapes** — current padding/trimming fix adds ~5% inference latency; ideally retrain with uniform shapes
- [ ] **Tests** — no test files exist anywhere in the project

---

## Current Metrics Snapshot

| Symbol | Trade Count | P&L | Max DD | Avg Sharpe | Models |
|--------|-------------|-----|--------|-----------|--------|
| NVDA | 1 ⚠️ | +33169.86% | 3.62% | 0.52 | 202 |
| AMD | 893 ✅ | +3661.83% | 45.05% | 0.30 | 60 |

P&L simulation: initial $1 000, execute all signal actions (buy on 1, hold on 0). Does not account for transaction costs, slippage, or partial fills.

---

## Quickstart

```bash
# Terminal 1: re-export signals (RL repo)
cd D:\code\agentic-development\reinforcement-learning-stocks
.venv\Scripts\python.exe scripts\export_signals_for_dashboard.py

# Terminal 2: backend
cd D:\code\web-development\trading-dashboard\backend
venv\Scripts\activate
python app.py

# Terminal 3: frontend
cd D:\code\web-development\trading-dashboard\frontend
npm run dev
# → http://localhost:3000
```
