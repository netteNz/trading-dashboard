/**
 * RL Ensemble Signal Toggle (controlled).
 * App owns the fetch (useRLSignals) and the enabled flag; this only shows them.
 */
export default function ExitControls({ enabled, onToggle, loading, unavailable }) {
  return (
    <div className="flex items-center gap-2 px-2 py-1 bg-surface-2 rounded-md border border-surface-3">
      <div className="flex flex-col">
        <span className="text-[8px] text-surface-4 font-bold tracking-tighter uppercase leading-tight">Ensemble</span>
        <span className="text-[10px] text-white font-mono font-bold leading-tight">RL AI</span>
      </div>

      <button
        onClick={() => onToggle(!enabled)}
        disabled={loading}
        className={`px-3 py-1 text-[11px] font-mono font-bold rounded border transition-all duration-200 ${
          enabled
            ? "bg-accent-cyan/10 border-accent-cyan text-accent-cyan shadow-[0_0_8px_rgba(0,255,255,0.2)]"
            : "bg-surface-3 border-surface-4 text-surface-4 hover:text-surface-5 hover:border-surface-5"
        }`}
      >
        {loading ? <span className="animate-pulse">LOAD</span> : enabled ? "ON" : "OFF"}
      </button>

      {enabled && unavailable && !loading && (
        <span className="text-[9px] text-accent-red font-bold animate-pulse" title="No RL export for this symbol">
          404
        </span>
      )}
    </div>
  );
}
