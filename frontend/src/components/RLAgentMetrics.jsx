import { useState, useEffect } from "react";

/**
 * RL Agent P&L Panel
 * Displays ensemble signal performance (simulated P&L) and leaderboard stats.
 * Collapsible sidebar panel positioned right of existing panels.
 */
export default function RLAgentMetrics({ symbol, isCollapsed, onToggleCollapse }) {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchMetrics = async () => {
    if (!symbol) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/signals/${symbol}`);
      if (!res.ok) throw new Error("Metrics not found");
      const data = await res.json();
      setMetrics(data);
    } catch (err) {
      console.warn(`[RL Metrics] Failed to fetch for ${symbol}:`, err);
      setError(err.message);
      setMetrics(null);
    } finally {
      setLoading(false);
    }
  };

  // Fetch when symbol changes
  useEffect(() => {
    fetchMetrics();
  }, [symbol]);

  if (!metrics || error) {
    return null; // Don't show panel if no data
  }

  const {
    ensemble_metrics = {},
    leaderboard_aggregate = {}
  } = metrics;

  const pnl = ensemble_metrics.simulated_return_pct || 0;
  const maxDD = ensemble_metrics.simulated_max_dd_pct || 0;
  const tradeCount = ensemble_metrics.simulated_trade_count || 0;
  const avgSharpe = leaderboard_aggregate.avg_sharpe || 0;
  const modelCount = leaderboard_aggregate.model_count || 0;

  const pnlColor = pnl >= 0 ? "text-green-400" : "text-red-400";
  const pnlBg = pnl >= 0 ? "bg-green-500/10" : "bg-red-500/10";

  return (
    <div className={`
      transition-all duration-300 ease-in-out
      ${isCollapsed ? "w-12" : "w-72"}
      h-full bg-surface-1 border-l border-surface-3
      flex flex-col overflow-hidden
    `}>
      {/* Header - Always Visible */}
      <div className="px-3 py-2 bg-surface-2 border-b border-surface-3 flex items-center justify-between">
        <span className={`text-[9px] font-bold uppercase tracking-tight text-surface-4 transition-all ${isCollapsed ? "hidden" : ""}`}>
          RL P&L
        </span>
        <button
          onClick={() => onToggleCollapse()}
          className="p-1 hover:bg-surface-3 rounded transition-colors"
          title={isCollapsed ? "Expand" : "Collapse"}
        >
          <span className="text-surface-4 text-sm">
            {isCollapsed ? "→" : "←"}
          </span>
        </button>
      </div>

      {/* Content - Collapsed Hide */}
      {!isCollapsed && (
        <div className="flex-1 overflow-y-auto p-3 space-y-4">
          {/* Simulated P&L Card */}
          <div className={`
            ${pnlBg}
            border border-opacity-30
            ${pnl >= 0 ? "border-green-500" : "border-red-500"}
            rounded-lg p-3
          `}>
            <div className="text-[9px] text-surface-4 uppercase font-bold tracking-tighter mb-1">
              Simulated P&L
            </div>
            <div className={`text-2xl font-bold font-mono ${pnlColor}`}>
              {pnl >= 0 ? "+" : ""}{pnl.toFixed(2)}%
            </div>
            <div className="text-[9px] text-surface-4 mt-1">
              Final: ${(ensemble_metrics.simulated_final_balance || 0).toLocaleString("en-US", {
                maximumFractionDigits: 0
              })}
            </div>
          </div>

          {/* Risk Metrics */}
          <div className="bg-surface-2 rounded-lg p-3 space-y-2">
            <div className="text-[9px] text-surface-4 uppercase font-bold tracking-tighter">
              Risk
            </div>
            <div className="flex justify-between items-center">
              <span className="text-[10px] text-surface-5">Max Drawdown</span>
              <span className={`text-[11px] font-mono font-bold text-orange-400`}>
                {maxDD.toFixed(2)}%
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-[10px] text-surface-5">Trade Count</span>
              <span className="text-[11px] font-mono font-bold text-surface-3">
                {tradeCount}
              </span>
            </div>
          </div>

          {/* Leaderboard Stats */}
          <div className="bg-surface-2 rounded-lg p-3 space-y-2">
            <div className="text-[9px] text-surface-4 uppercase font-bold tracking-tighter">
              Leaderboard
            </div>
            <div className="flex justify-between items-center">
              <span className="text-[10px] text-surface-5">Avg Sharpe</span>
              <span className="text-[11px] font-mono font-bold text-accent-cyan">
                {avgSharpe.toFixed(2)}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-[10px] text-surface-5">Models</span>
              <span className="text-[11px] font-mono font-bold text-accent-cyan">
                {modelCount}
              </span>
            </div>
          </div>

          {/* Last Updated */}
          <div className="text-[8px] text-surface-4 text-center opacity-70">
            {metrics.last_updated_utc && new Date(metrics.last_updated_utc).toLocaleTimeString()}
          </div>
        </div>
      )}
    </div>
  );
}
