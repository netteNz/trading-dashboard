# Trading Dashboard RL Wiring - Status & TODO

**Last Updated**: 2026-05-03 06:07

---

## ✅ COMPLETED

### RL Repo (reinforcement-learning-stocks)
- [x] Fixed `export_signals_for_dashboard.py` to handle mismatched observation shapes
- [x] Enhanced export script with P&L metrics (simulated_return_pct, max_dd_pct, trade_count)
- [x] Added leaderboard aggregate stats (model_count, avg_sharpe, max_sharpe)
- [x] Fixed `src/ensemble.py` to pad/trim observations per-model
- [x] NVDA & AMD signals exported to `data/dashboard_signals/*.json`

### Trading Dashboard (web-development/trading-dashboard)
- [x] Created `frontend/src/components/RLAgentMetrics.jsx` component
- [x] Updated `frontend/src/App.jsx` with imports, state, and dual-panel layout
- [x] Verified backend `/api/signals/<symbol>` route works
- [x] Both frontend (port 3000) and backend (port 5000) running
- [x] Panel displays for NVDA/AMD with metrics visible

### Documentation
- [x] Created `TRADING_DASHBOARD_RL_WIRING.md` (detailed integration guide)
- [x] Created `RL_PANEL_IMPLEMENTATION.md` (quick reference)

---

## 🔴 KNOWN ISSUES

### Signal Action Distribution (NVDA)
**Issue**: NVDA has only **1 trade** despite 2847 signals
- Root cause: Ensemble voting heavily biased toward action=1 (buy)
- Current state: All models output positive SAC weights → all vote 1
- Impact: No sell signals, so only 1 entry trade counted

**AMD (Status)**: 893 trades (healthy) ✅

**Next Steps**:
1. Investigate NVDA model training - why are they always bullish?
2. Check if models trained on different data distributions
3. Consider signal filtering: require minimum ensemble confidence (e.g., 4/5 models agree)
4. Analyze vote distribution per bar to find decision patterns

### Dashboard Chart Zoom
**Issue**: Chart defaults to far-left corner (mentioned in screenshot)
- Likely: Chart zoom/pan state not properly initialized
- Impact: UX friction on initial load
- Status: Low priority (user can scroll to see current data)

---

## 📋 TODO (Priority Order)

### HIGH PRIORITY

#### 1. Investigate NVDA Signal Bias
- [ ] Check leaderboard for NVDA model configs
- [ ] Compare voting distribution: are 4/5 models voting 1 on every bar?
- [ ] Check if training data for NVDA has trend bias
- [ ] Consider model robustness issue - may need retraining with better diversity

#### 2. Signal Quality Filter
- [ ] Add minimum confidence threshold (e.g., only signal if 4+/5 models agree)
- [ ] Add signal hold period (don't retrade within N bars)
- [ ] Add stop-loss / take-profit logic to exit script

#### 3. Test Dashboard Live
- [ ] Confirm RLAgentMetrics panel renders for NVDA/AMD
- [ ] Test panel collapse/expand (← → arrows)
- [ ] Verify metrics update correctly on symbol change
- [ ] Test color coding (green/red P&L, orange drawdown)

### MEDIUM PRIORITY

#### 4. Signal Visualization
- [ ] Overlay buy/sell signals on price chart as markers
- [ ] Color-code signal confidence (darker = more confident)
- [ ] Show entry/exit prices and P&L per trade

#### 5. Live Signal Updates
- [ ] Schedule export script to run hourly (Windows Task Scheduler or cron)
- [ ] Auto-refresh dashboard metrics without page reload
- [ ] Add "Last updated" timestamp display

#### 6. Fix Chart Zoom
- [ ] Set default chart view to show recent 100-200 bars
- [ ] Add "Reset Zoom" button
- [ ] Persist zoom state in localStorage

### LOW PRIORITY

#### 7. Leaderboard Integration
- [ ] Add link to full leaderboard view for symbol
- [ ] Show top 3 models with their stats
- [ ] Add model details modal (config, sharpe, trades, etc.)

#### 8. Trade History Panel
- [ ] Add tab to show individual trades
- [ ] Display entry/exit price, duration, P&L per trade
- [ ] Add trade heatmap (when do models trade most?)

#### 9. Performance Optimization
- [ ] Cache signal JSON in backend (5-15 min TTL)
- [ ] Compress signal payloads before transport
- [ ] Add pagination for large signal lists

---

## 📊 Current Metrics

| Symbol | Trade Count | P&L | Max DD | Avg Sharpe | Models |
|--------|-------------|-----|--------|-----------|--------|
| NVDA   | 1 ⚠️        | +33169.86% | 3.62% | 0.52 | 202 |
| AMD    | 893 ✅      | +3661.83% | 45.05% | 0.30 | 60 |

---

## 🔧 Technical Debt

1. **Observation Shape Mismatch**: Fixed but uses padding/trimming - ideally train models with consistent shapes
2. **Signal Export Latency**: Currently ~15s for full export - consider streaming or chunked export
3. **Backend Route Efficiency**: Reads JSON from disk each request - consider caching layer
4. **P&L Simulation**: Simple greedy model - doesn't account for transaction costs, slippage, partial fills

---

## 📌 Files to Track

| File | Purpose | Status |
|------|---------|--------|
| `scripts/export_signals_for_dashboard.py` | Generate signals + metrics | ✅ Working |
| `src/ensemble.py` | Ensemble voting | ✅ Fixed (obs shape handling) |
| `frontend/src/components/RLAgentMetrics.jsx` | Dashboard panel | ✅ Created |
| `frontend/src/App.jsx` | Main app layout | ✅ Updated |
| `backend/app.py` | Flask routes | ✅ Has /api/signals route |
| `data/dashboard_signals/*.json` | Exported signals | ✅ Generated |

---

## 🚀 Next Session Quickstart

```bash
# Terminal 1: RL Repo (if re-exporting)
cd D:\code\agentic-development\reinforcement-learning-stocks
.venv\Scripts\python.exe scripts\export_signals_for_dashboard.py

# Terminal 2: Backend
cd D:\code\web-development\trading-dashboard\backend
python app.py

# Terminal 3: Frontend
cd D:\code\web-development\trading-dashboard\frontend
npm run dev

# Then visit: http://localhost:3000
```

---

## 💡 Notes for Future Sessions

- **NVDA bias**: May need ensemble recalibration or retraining
- **AMD performance**: Model looks solid (893 trades, 3661% return) - good reference
- **Architecture**: Padding/trimming works but adds ~5% latency to inference
- **Confidence metric**: Currently just vote ratio - could improve with model calibration

