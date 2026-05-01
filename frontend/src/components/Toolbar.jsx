const TIMEFRAMES = [
  { value: "1Min",  label: "1m" },
  { value: "5Min",  label: "5m" },
  { value: "15Min", label: "15m" },
  { value: "30Min", label: "30m" },
  { value: "1Hour", label: "1H" },
  { value: "1Day",  label: "1D" },
  { value: "1Week", label: "1W" },
];

const PRESETS = ["trend", "momentum", "scalp", "full"];

export default function Toolbar({ symbol, timeframe, preset, lastTick, connected,
                                  onTimeframeChange, onPresetChange, prevClose }) {
  const price = lastTick?.close ?? null;
  const isUp  = price != null && prevClose != null ? price >= prevClose : null;

  return (
    <div className="flex items-center gap-4 px-4 py-2 bg-surface-1 border-b border-surface-2 select-none">
      {/* Symbol + live badge */}
      <div className="flex items-center gap-2">
        <span className="text-sm font-mono font-bold text-white tracking-wide">{symbol}</span>
        {connected && (
          <span className="flex items-center gap-1 text-[10px] font-mono text-accent-green">
            <span className="live-dot w-1.5 h-1.5 rounded-full bg-accent-green inline-block" />
            LIVE
          </span>
        )}
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
        {PRESETS.map(p => (
          <button
            key={p}
            onClick={() => onPresetChange(p)}
            className={`px-2 py-0.5 text-[11px] font-mono rounded transition-colors ${
              preset === p
                ? "bg-surface-3 text-white border border-surface-4"
                : "text-surface-4 hover:text-white hover:bg-surface-2"
            }`}
          >
            {p}
          </button>
        ))}
      </div>

      <div className="ml-auto flex items-center gap-2">
        <span className="text-[10px] font-mono text-surface-4">
          {new Date().toLocaleTimeString("en-US", { hour12: false })}
        </span>
      </div>
    </div>
  );
}
