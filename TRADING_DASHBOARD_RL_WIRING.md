# RL Agent P&L Panel Integration Guide

## Overview
This guide shows how to wire the new `RLAgentMetrics.jsx` component into the trading-dashboard to display RL ensemble P&L and leaderboard stats in a collapsible right-side panel.

---

## Step 1: Update `frontend/src/App.jsx`

### Add state for RL metrics panel collapse
Find the `useState` declarations near line 20:

```jsx
const [sidebarOpen, setSidebarOpen] = useState(true);
const [rlMetricsCollapsed, setRlMetricsCollapsed] = useState(false);  // ADD THIS LINE
```

### Import the new component
Add to imports at top:

```jsx
import RLAgentMetrics      from "./components/RLAgentMetrics";
```

### Update the layout structure
Replace the sidebar section (lines 157-170) with:

```jsx
{/* Sidebar: Indicators + RL Metrics */}
{sidebarOpen && (
  <div className="flex" style={{ transition: "width 0.2s ease" }}>
    {/* Indicators Panel */}
    <aside className="w-52 bg-surface-1 border-l border-surface-2 overflow-y-auto shrink-0">
      <IndicatorPanel
        active={indicators}
        onChange={setIndicators}
        symbol={symbol}
        onSymbolChange={setSymbol}
      />
    </aside>

    {/* RL Agent P&L Panel */}
    <RLAgentMetrics
      symbol={symbol}
      isCollapsed={rlMetricsCollapsed}
      onToggleCollapse={() => setRlMetricsCollapsed(!rlMetricsCollapsed)}
    />
  </div>
)}
```

---

## Step 2: Verify Backend Route (Flask)

The backend should already be exporting signals if you've been testing the script. Verify that `backend/app.py` has a route like:

```python
@app.route('/api/signals/<symbol>')
def signals_adapter(symbol):
    """
    Adapter route that loads pre-computed RL signals from the RL repo exports.
    """
    from pathlib import Path
    rl_signals_dir = Path(__file__).resolve().parent.parent.parent / "reinforcement-learning-stocks" / "data" / "dashboard_signals"
    p = rl_signals_dir / f"{symbol.lower()}_signals.json"
    
    if not p.exists():
        return jsonify({"error": f"signals not available for {symbol}"}), 404
    
    with open(p) as f:
        return jsonify(json.load(f))
```

If this route doesn't exist, add it to `backend/app.py` before running the dashboard.

---

## Step 3: Test the Integration

### 1. Ensure signals are exported
From the RL repo, run:
```bash
.venv\Scripts\python.exe scripts\export_signals_for_dashboard.py
```

You should see both `NVDA` and `AMD` export successfully with P&L metrics.

### 2. Start the dashboard backend
```bash
cd backend
python app.py
# or if using venv:
# .venv\Scripts\activate
# python app.py
```

### 3. Start the frontend (in another terminal)
```bash
cd frontend
npm install  # if needed
npm run dev
```

### 4. Open the dashboard
Navigate to `http://localhost:5173` (or whatever port Vite is using).

### 5. Test the panel
1. Select a symbol (NVDA or AMD)
2. The right sidebar should show the RL Metrics panel with:
   - **Simulated P&L %** (green if positive, red if negative)
   - **Max Drawdown %** (orange)
   - **Trade Count** (gray)
   - **Leaderboard Stats** (Avg Sharpe, Model Count in cyan)
3. Click the collapse arrow (←/→) to toggle the panel width

---

## Component Architecture

### RLAgentMetrics.jsx Props
- `symbol` (string): Current ticker symbol
- `isCollapsed` (boolean): Whether panel is collapsed
- `onToggleCollapse` (function): Callback to toggle collapse state

### JSON Payload from `/api/signals/<symbol>`
```json
{
  "symbol": "NVDA",
  "interval": "1d",
  "last_updated_utc": "2026-05-03T09:51:29Z",
  "model_count": 5,
  "ensemble_metrics": {
    "simulated_return_pct": 33169.86,
    "simulated_max_dd_pct": 3.62,
    "simulated_final_balance": 332698.59,
    "simulated_trade_count": 1
  },
  "leaderboard_aggregate": {
    "model_count": 202,
    "avg_sharpe": 0.52,
    "max_sharpe": 1.83
  },
  "signals": [ ... ]
}
```

---

## Styling Notes

The component uses **Tailwind CSS v4** with your existing color palette:
- `surface-0/1/2/3/4/5` - Background/text colors
- `accent-cyan` - Sharpe/model count (bright)
- `accent-green` - Positive P&L
- `accent-red` - Negative P&L
- `accent-orange` - Risk metrics (drawdown)

The panel is fully responsive:
- **Expanded**: 288px (w-72) width
- **Collapsed**: 48px (w-12) width
- Smooth 300ms transitions

---

## Troubleshooting

### Panel doesn't appear
- Check that `/api/signals/<symbol>` returns 200 OK
- Open browser DevTools → Network tab → filter to `signals/` requests
- Verify signal files exist in `../reinforcement-learning-stocks/data/dashboard_signals/`

### Metrics show as NaN or 0
- The signal export script may not have run with the latest fixes
- Re-run: `.venv\Scripts\python.exe scripts\export_signals_for_dashboard.py`
- Check that `ensemble_metrics` and `leaderboard_aggregate` sections are present in the JSON

### Styling looks broken
- Ensure Tailwind CSS classes are properly compiled
- Clear cache: `npm run dev` should rebuild
- Verify `tailwind.config.js` includes `surface-*` and `accent-*` color definitions

---

## What's Next

1. **Live Data Updates**: Modify `export_signals_for_dashboard.py` to run on a schedule (e.g., hourly) to keep metrics fresh
2. **Trade History**: Enhance the panel to show individual trade entry/exit prices alongside P&L
3. **Performance Tabs**: Add tabs to toggle between "Simulated" and "Backtest" metrics
4. **Alerts**: Flash the panel green/red on significant P&L swings

---

## Files Modified/Created

- ✅ `frontend/src/components/RLAgentMetrics.jsx` (NEW)
- ✅ `frontend/src/App.jsx` (MODIFIED - 2 lines + 20 lines structure change)
- ✅ `backend/app.py` (VERIFIED - `/api/signals/<symbol>` route must exist)
- ✅ `scripts/export_signals_for_dashboard.py` (MODIFIED in RL repo - adds P&L metrics)

---

Created: 2026-05-03
