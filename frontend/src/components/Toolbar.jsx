import ExitControls from "./ExitControls";
import StreamBadge  from "./StreamBadge";

const TIMEFRAMES = [
  { value: "1Min",  label: "1m" },
  { value: "5Min",  label: "5m" },
  { value: "15Min", label: "15m" },
  { value: "30Min", label: "30m" },
  { value: "1Hour", label: "1H" },
  { value: "1Day",  label: "1D" },
  { value: "1Week", label: "1W" },
];

export default function Toolbar({ symbol, timeframe, presets, activePreset, lastTick, streamStatus,
                                  onTimeframeChange, onPresetChange, rl, showSignals, onToggleSignals,
                                  prevClose }) {
  const core   = presets.filter(p => p.kind === "core");
  const combos = presets.filter(p => p.kind === "combo");
  const activeCombo = combos.find(p => p.name === activePreset);

  const price = lastTick?.close ?? null;
  const isUp  = price != null && prevClose != null ? price >= prevClose : null;

  return (
    <div className="flex items-center gap-4 px-4 py-2 bg-surface-1 border-b border-surface-2 select-none">
      {/* Symbol + live badge */}
      <div className="flex items-center gap-2">
        <span className="text-sm font-mono font-bold text-white tracking-wide">{symbol}</span>
        <StreamBadge status={streamStatus} />
        {price != null && (
          <span className={`text-sm font-mono font-bold ml-2 ${
            isUp === true  ? "text-accent-green" :
            isUp === false ? "text-accent-red"   : "text-accent-cyan"
          }`}>
            {price.toFixed(2)}
          </span>
        )}
      </div>

      <div className="h-4 w-px bg-surface-3" />

      {/* Timeframe buttons */}
      <div className="flex items-center gap-0.5">
        {TIMEFRAMES.map(tf => (
          <button
            key={tf.value}
            onClick={() => onTimeframeChange(tf.value)}
            className={`px-2 py-0.5 text-[11px] font-mono rounded transition-colors ${
              timeframe === tf.value
                ? "bg-accent-cyan text-surface-0 font-bold"
                : "text-surface-4 hover:text-accent-cyan hover:bg-surface-2"
            }`}
          >
            {tf.label}
          </button>
        ))}
      </div>

      <div className="h-4 w-px bg-surface-3" />

      {/* Preset selector */}
      <div className="flex items-center gap-1">
        <span className="text-[10px] text-surface-4 uppercase tracking-widest mr-1">Preset</span>
        {core.map(p => (
          <button
            key={p.name}
            onClick={() => onPresetChange(p.name)}
            title={p.desc}
            className={`px-2 py-0.5 text-[11px] font-mono rounded transition-colors ${
              activePreset === p.name
                ? "bg-surface-3 text-white border border-surface-4"
                : "text-surface-4 hover:text-white hover:bg-surface-2"
            }`}
          >
            {p.name}
          </button>
        ))}
        {combos.length > 0 && (
          <select
            value={activeCombo?.name ?? ""}
            onChange={e => e.target.value && onPresetChange(e.target.value)}
            title={activeCombo?.desc ?? "Load a combo preset"}
            className={`ml-1 text-[11px] font-mono rounded px-1 py-0.5 outline-none border transition-colors ${
              activeCombo
                ? "bg-surface-3 text-white border-surface-4"
                : "bg-surface-1 text-surface-4 border-surface-3 hover:text-white"
            }`}
          >
            <option value="">combos…</option>
            {combos.map(p => (
              <option key={p.name} value={p.name}>{p.label} · {p.tf}</option>
            ))}
          </select>
        )}
      </div>

      <div className="h-4 w-px bg-surface-3" />
      
      {/* RL Signals Control */}
      <ExitControls
        enabled={rl.enabled}
        onToggle={rl.onToggle}
        loading={rl.loading}
        unavailable={!rl.loading && !rl.available}
      />

      {/* TA confluence markers (combo BUY/SELL arrows, Triple MA arrows) */}
      <button
        onClick={() => onToggleSignals(!showSignals)}
        title="Show or hide BUY/SELL signal markers"
        className={`px-2 py-1 text-[11px] font-mono font-bold rounded border transition-colors ${
          showSignals
            ? "bg-accent-green/10 border-accent-green text-accent-green"
            : "bg-surface-3 border-surface-4 text-surface-4 hover:text-white"
        }`}
      >
        SIGNALS {showSignals ? "ON" : "OFF"}
      </button>

      <div className="ml-auto flex items-center gap-2">
        <span className="text-[10px] font-mono text-surface-4">
          {new Date().toLocaleTimeString("en-US", { hour12: false })}
        </span>
      </div>
    </div>
  );
}
