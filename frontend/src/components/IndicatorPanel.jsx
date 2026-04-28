import { useState } from "react";

const AVAILABLE = [
  { fn: "ema",    label: "EMA",              params: [{ key: "length", label: "Period", default: 20 }] },
  { fn: "sma",    label: "SMA",              params: [{ key: "length", label: "Period", default: 20 }] },
  { fn: "bbands", label: "Bollinger Bands",  params: [] },
  { fn: "rsi",    label: "RSI",              params: [{ key: "length", label: "Period", default: 14 }] },
  { fn: "macd",   label: "MACD",             params: [] },
  { fn: "atr",    label: "ATR",              params: [{ key: "length", label: "Period", default: 14 }] },
  { fn: "stoch",  label: "Stochastic",       params: [] },
  { fn: "vwap",   label: "VWAP Band",        params: [{ key: "std_mult", label: "Std ×", default: 2 }] },
  { fn: "mom",    label: "Mom Oscillator",   params: [{ key: "period", label: "Period", default: 14 }] },
  { fn: "sqz",    label: "Squeeze Mom",      params: [] },
  { fn: "vol",    label: "Volume Profile",   params: [] },
  { fn: "tma",    label: "Triple MA Crossover", params: [{ key: "fast", label: "Fast Period", default: 3 }, { key: "mid", label: "Mid Period", default: 7 }, { key: "slow", label: "Slow Period", default: 20 }] },
];

export default function IndicatorPanel({ active, onChange }) {
  const [adding, setAdding] = useState(null);
  const [params, setParams] = useState({});

  const isActive = (fn) => active.some(a => a.fn === fn);

  const handleAdd = (indicator) => {
    if (indicator.params.length === 0) {
      onChange([...active, { fn: indicator.fn, kwargs: {} }]);
    } else {
      const defaults = {};
      indicator.params.forEach(p => { defaults[p.key] = p.default; });
      setParams(defaults);
      setAdding(indicator);
    }
  };

  const handleRemove = (fn) => {
    onChange(active.filter(a => a.fn !== fn));
  };

  const handleConfirmAdd = () => {
    if (!adding) return;
    onChange([...active, { fn: adding.fn, kwargs: { ...params } }]);
    setAdding(null);
    setParams({});
  };

  return (
    <div className="flex flex-col gap-1 w-full">
      <p className="text-[10px] text-surface-4 uppercase tracking-widest mb-2 px-1">Indicators</p>

      {/* Active indicators */}
      {active.map((ind, i) => {
        const meta = AVAILABLE.find(a => a.fn === ind.fn);
        return (
          <div
            key={`${ind.fn}-${i}`}
            className="flex items-center justify-between px-2 py-1 bg-surface-2 rounded border border-surface-3 group"
          >
            <span className="text-[11px] font-mono text-accent-cyan">
              {meta?.label || ind.fn.toUpperCase()}
              {ind.kwargs?.length ? <span className="text-surface-4 ml-1">({ind.kwargs.length})</span> : null}
            </span>
            <button
              onClick={() => handleRemove(ind.fn)}
              className="text-surface-4 hover:text-accent-red text-xs opacity-0 group-hover:opacity-100 transition-opacity"
            >
              ✕
            </button>
          </div>
        );
      })}

      {/* Add indicator picker */}
      <div className="mt-2">
        <p className="text-[10px] text-surface-4 uppercase tracking-widest mb-1 px-1">Add</p>
        <div className="flex flex-col gap-0.5">
          {AVAILABLE.filter(a => !isActive(a.fn)).map(ind => (
            <button
              key={ind.fn}
              onClick={() => handleAdd(ind)}
              className="text-left text-[11px] font-mono px-2 py-1 text-surface-4 hover:text-accent-cyan hover:bg-surface-2 rounded transition-colors"
            >
              + {ind.label}
            </button>
          ))}
        </div>
      </div>

      {/* Param modal */}
      {adding && (
        <div className="mt-3 bg-surface-2 border border-surface-3 rounded p-3">
          <p className="text-[11px] font-mono text-accent-cyan mb-2">{adding.label}</p>
          {adding.params.map(p => (
            <div key={p.key} className="mb-2">
              <label className="text-[10px] text-surface-4 block mb-1">{p.label}</label>
              <input
                type="number"
                value={params[p.key] ?? p.default}
                onChange={e => setParams(prev => ({ ...prev, [p.key]: Number(e.target.value) }))}
                className="w-full bg-surface-1 border border-surface-3 rounded px-2 py-1 text-xs font-mono text-white outline-none focus:border-accent-cyan"
              />
            </div>
          ))}
          <div className="flex gap-2 mt-2">
            <button
              onClick={handleConfirmAdd}
              className="flex-1 bg-accent-cyan text-surface-0 text-[11px] font-mono py-1 rounded hover:opacity-90"
            >
              Add
            </button>
            <button
              onClick={() => { setAdding(null); setParams({}); }}
              className="flex-1 bg-surface-3 text-surface-4 text-[11px] font-mono py-1 rounded hover:opacity-90"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
