import { useState, useEffect } from "react";

/**
 * RL Ensemble Signal Toggle
 * Fetches AI-generated exit/entry signals from the backend adapter.
 */
export default function ExitControls({ symbol, onToggleSignals }) {
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchSignals = async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch from the backend adapter we just implemented
      const res = await fetch(`/api/signals/${symbol}`);
      if (!res.ok) throw new Error("Not Found");
      const data = await res.json();
      
      // Bubble signals up to the parent to be passed to TradingChart
      onToggleSignals(true, data.signals);
    } catch (err) {
      console.warn(`[RL] signals not available for ${symbol}`);
      setError(true);
      onToggleSignals(false, []);
      setEnabled(false);
    } finally {
      setLoading(false);
    }
  };

  // Re-fetch when symbol changes if enabled
  useEffect(() => {
    if (enabled) {
      fetchSignals();
    } else {
      onToggleSignals(false, []);
    }
  }, [enabled, symbol]);

  return (
    <div className="flex items-center gap-2 px-2 py-1 bg-surface-2 rounded-md border border-surface-3">
      <div className="flex flex-col">
        <span className="text-[8px] text-surface-4 font-bold tracking-tighter uppercase leading-tight">Ensemble</span>
        <span className="text-[10px] text-white font-mono font-bold leading-tight">RL AI</span>
      </div>
      
      <button
        onClick={() => setEnabled(!enabled)}
        disabled={loading}
        className={`px-3 py-1 text-[11px] font-mono font-bold rounded border transition-all duration-200 ${
          enabled
            ? "bg-accent-cyan/10 border-accent-cyan text-accent-cyan shadow-[0_0_8px_rgba(0,255,255,0.2)]"
            : "bg-surface-3 border-surface-4 text-surface-4 hover:text-surface-5 hover:border-surface-5"
        }`}
      >
        {loading ? (
          <span className="flex items-center gap-1">
            <span className="animate-pulse">LOAD</span>
          </span>
        ) : enabled ? (
          "ON"
        ) : (
          "OFF"
        )}
      </button>
      
      {error && !loading && (
        <span className="text-[9px] text-accent-red font-bold animate-pulse">404</span>
      )}
    </div>
  );
}
