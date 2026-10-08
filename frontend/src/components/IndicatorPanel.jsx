import { useState } from "react";
import { hasInstance as listHas, sameInstance } from "../lib/indicators";

// ── Static config ─────────────────────────────────────────────────────────────

const WATCHLIST = ["SPY", "QQQ", "AAPL", "TSLA", "NVDA", "AMZN", "MSFT", "META"];

const AVAILABLE = [
  { fn: "ema",    label: "EMA",               params: [{ key: "length", label: "Period", default: 20 }] },
  { fn: "sma",    label: "SMA",               params: [{ key: "length", label: "Period", default: 20 }] },
  { fn: "bbands", label: "Bollinger Bands",   params: [] },
  { fn: "rsi",    label: "RSI",               params: [{ key: "length", label: "Period", default: 14 }] },
  { fn: "macd",   label: "MACD",              params: [] },
  { fn: "atr",    label: "ATR",               params: [{ key: "length", label: "Period", default: 14 }] },
  { fn: "stoch",  label: "Stochastic",        params: [] },
  { fn: "vwap",   label: "VWAP Band",         params: [{ key: "std_mult", label: "Std ×", default: 2, int: false }] },
  { fn: "mom",    label: "Mom Oscillator",    params: [{ key: "period",  label: "Period", default: 14 }] },
  { fn: "sqz",    label: "Squeeze Mom",       params: [] },
  { fn: "vol",    label: "Volume Profile",    params: [] },
  { fn: "tma",    label: "Triple MA",         params: [
    { key: "fast",  label: "Fast",  default: 3  },
    { key: "mid",   label: "Mid",   default: 7  },
    { key: "slow",  label: "Slow",  default: 20 },
  ]},
  { fn: "adx",    label: "ADX / DMI",         params: [{ key: "length", label: "Period", default: 14 }] },
  { fn: "kc",     label: "Keltner Channel",   params: [
    { key: "length", label: "Period", default: 20 },
    { key: "scalar", label: "ATR ×",  default: 1.5, int: false },
  ]},
  { fn: "mfi",    label: "Money Flow Index",  params: [{ key: "length", label: "Period", default: 14 }] },
  { fn: "obv",    label: "OBV",               params: [] },
  { fn: "cmf",    label: "Chaikin Money Flow", params: [{ key: "length", label: "Period", default: 20 }] },
  { fn: "mrd",    label: "Market Regime",     params: [] },
];

// Combo BUY/SELL markers are added with their combo, not from a group list.
const SIGNAL_LABEL = "Signals";

// Short pill text for an indicator inside a combo card.
function pillText(ind) {
  if (ind.fn === "sig") return "SIG";
  const vals = Object.values(ind.kwargs ?? {});
  return vals.length ? `${ind.fn.toUpperCase()} ${vals.join("/")}` : ind.fn.toUpperCase();
}

const GROUPS = [
  { key: "ma",         label: "Moving Averages", fns: ["ema", "sma", "tma"]                      },
  { key: "osc",        label: "Oscillators",     fns: ["rsi", "macd", "stoch", "mom", "sqz", "mfi"] },
  { key: "trend",      label: "Trend & Regime",  fns: ["adx", "mrd"]                             },
  { key: "volatility", label: "Volatility",      fns: ["atr", "bbands", "kc"]                    },
  { key: "volume",     label: "Volume",          fns: ["vwap", "vol", "obv", "cmf"]              },
];

// ── Accordion section ─────────────────────────────────────────────────────────

function Section({ label, count, isOpen, onToggle, children }) {
  return (
    <div className="border-b border-surface-2">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-2 py-2 hover:bg-surface-2 transition-colors group"
      >
        <div className="flex items-center gap-1.5">
          <span
            className={`text-[8px] text-surface-4 transition-transform duration-150 inline-block leading-none ${
              isOpen ? "rotate-90" : ""
            }`}
          >
            ▸
          </span>
          <span className="text-[10px] font-mono uppercase tracking-widest text-surface-4 group-hover:text-white transition-colors">
            {label}
          </span>
        </div>
        {count > 0 && (
          <span className="text-[9px] font-mono px-1.5 py-0.5 bg-accent-cyan/10 text-accent-cyan rounded">
            {count}
          </span>
        )}
      </button>
      {isOpen && <div className="pb-1">{children}</div>}
    </div>
  );
}

// ── Panel ─────────────────────────────────────────────────────────────────────

export default function IndicatorPanel({ active, onChange, combos = [], symbol, onSymbolChange }) {
  const [adding,   setAdding]   = useState(null);
  const [params,   setParams]   = useState({});
  const [sections, setSections] = useState({
    watchlist:  true,
    active:     true,
    combos:     false,
    ma:         false,
    osc:        false,
    trend:      false,
    volatility: false,
    volume:     false,
  });

  const toggle = (key) => setSections(prev => ({ ...prev, [key]: !prev[key] }));

  // ── Indicator helpers ───────────────────────────────────────────────────────

  const hasInstance  = (ind) => listHas(active, ind);
  const hasAnyOf     = (fn)  => active.some(a => a.fn === fn);

  const isComboActive = (combo) => combo.indicators.every(hasInstance);

  const handleLoadCombo = (combo) => {
    onChange([...active, ...combo.indicators.filter(ci => !hasInstance(ci))]);
  };

  const handleRemoveCombo = (combo) => {
    onChange(active.filter(a => !combo.indicators.some(ci => sameInstance(a, ci))));
  };

  const addInstance = (ind) => {
    if (!hasInstance(ind)) onChange([...active, ind]);
  };

  const handleAdd = (indicator) => {
    if (indicator.params.length === 0) {
      addInstance({ fn: indicator.fn, kwargs: {} });
    } else {
      const defaults = {};
      indicator.params.forEach(p => { defaults[p.key] = p.default; });
      setParams(defaults);
      setAdding(indicator);
    }
  };

  // Remove exactly one row (by position), never every indicator sharing its fn.
  const handleRemoveAt   = (index) => onChange(active.filter((_, i) => i !== index));
  // Parameterless indicators can only be active once, so removing by fn is exact.
  const handleRemoveFn   = (fn)    => onChange(active.filter(a => a.fn !== fn));

  // Empty or invalid inputs fall back to the default; periods are whole numbers ≥ 1.
  const cleanParams = (indicator, raw) => {
    const out = {};
    for (const p of indicator.params) {
      let v = Number(raw[p.key]);
      if (!Number.isFinite(v) || v <= 0) v = p.default;
      out[p.key] = p.int === false ? v : Math.max(1, Math.round(v));
    }
    return out;
  };

  const handleConfirmAdd = () => {
    if (!adding) return;
    addInstance({ fn: adding.fn, kwargs: cleanParams(adding, params) });
    setAdding(null);
    setParams({});
  };

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col w-full">

      {/* ── Watchlist ──────────────────────────────────────────────────────── */}
      <Section
        label="Watchlist"
        count={WATCHLIST.length}
        isOpen={sections.watchlist}
        onToggle={() => toggle("watchlist")}
      >
        {WATCHLIST.map(ticker => (
          <button
            key={ticker}
            onClick={() => onSymbolChange?.(ticker)}
            className={`w-full flex items-center justify-between px-4 py-1.5 text-left transition-colors ${
              symbol === ticker
                ? "text-accent-cyan bg-surface-2"
                : "text-surface-4 hover:bg-surface-2 hover:text-white"
            }`}
          >
            <span className="text-[11px] font-mono">{ticker}</span>
            {symbol === ticker && (
              <span className="w-1.5 h-1.5 rounded-full bg-accent-cyan shrink-0" />
            )}
          </button>
        ))}
      </Section>

      {/* ── Active ─────────────────────────────────────────────────────────── */}
      <Section
        label="Active"
        count={active.length}
        isOpen={sections.active}
        onToggle={() => toggle("active")}
      >
        {active.length === 0 ? (
          <p className="text-[10px] text-surface-4 px-4 py-2">Nothing loaded</p>
        ) : (
          active.map((ind, i) => {
            const meta    = ind.fn === "sig" ? { label: SIGNAL_LABEL } : AVAILABLE.find(a => a.fn === ind.fn);
            const kwVals  = Object.values(ind.kwargs || {});
            const suffix  = kwVals.length ? ` · ${kwVals.join(", ")}` : "";
            return (
              <div
                key={`${ind.fn}-${i}`}
                className="flex items-center justify-between px-4 py-1.5 group/row hover:bg-surface-2 transition-colors"
              >
                <span className="text-[11px] font-mono text-accent-cyan">
                  {meta?.label || ind.fn.toUpperCase()}
                  {suffix && <span className="text-surface-4">{suffix}</span>}
                </span>
                <button
                  onClick={() => handleRemoveAt(i)}
                  title="Remove"
                  className="text-[10px] text-surface-4 hover:text-accent-red opacity-0 group-hover/row:opacity-100 transition-opacity"
                >
                  ✕
                </button>
              </div>
            );
          })
        )}
      </Section>

      {/* ── Combos ─────────────────────────────────────────────────────────── */}
      <Section
        label="Combos"
        count={combos.filter(c => isComboActive(c)).length}
        isOpen={sections.combos}
        onToggle={() => toggle("combos")}
      >
        <div className="flex flex-col gap-1 px-2 py-1">
          {combos.length === 0 && (
            <p className="text-[10px] text-surface-4 px-2 py-1">No combos loaded</p>
          )}
          {combos.map(combo => {
            const comboOn = isComboActive(combo);
            return (
              <div
                key={combo.name}
                className={`rounded border px-2 py-2 transition-colors ${
                  comboOn ? "bg-surface-2 border-accent-cyan/30" : "border-surface-3"
                }`}
              >
                <div className="flex items-start justify-between gap-1">
                  <div className="min-w-0">
                    <p className={`text-[11px] font-mono truncate ${comboOn ? "text-accent-cyan" : "text-white"}`}>
                      {combo.label}
                    </p>
                    <p className="text-[10px] text-surface-4 mt-0.5">{combo.desc}</p>
                    <p className="text-[9px] text-surface-4 mt-0.5 opacity-70">{combo.tf}</p>
                    <div className="flex flex-wrap gap-1 mt-1.5">
                      {combo.indicators.map((ind, i) => (
                        <span
                          key={i}
                          className={`text-[9px] font-mono px-1 py-0.5 bg-surface-3 rounded ${
                            ind.fn === "sig" ? "text-accent-green" : "text-surface-4"
                          }`}
                        >
                          {pillText(ind)}
                        </span>
                      ))}
                    </div>
                  </div>
                  <button
                    onClick={() => comboOn ? handleRemoveCombo(combo) : handleLoadCombo(combo)}
                    className={`shrink-0 text-[11px] font-mono px-2 py-1 rounded transition-colors mt-0.5 ${
                      comboOn
                        ? "text-accent-red hover:bg-surface-3"
                        : "text-accent-cyan hover:bg-surface-2"
                    }`}
                  >
                    {comboOn ? "✕" : "+"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </Section>

      {/* ── Indicator groups ────────────────────────────────────────────────── */}
      {GROUPS.map(group => {
        const groupInds   = AVAILABLE.filter(a => group.fns.includes(a.fn));
        const activeCount = active.filter(a => group.fns.includes(a.fn)).length;
        return (
          <Section
            key={group.key}
            label={group.label}
            count={activeCount}
            isOpen={sections[group.key]}
            onToggle={() => toggle(group.key)}
          >
            {groupInds.map(ind => {
              const on = hasAnyOf(ind.fn);
              // Indicators with parameters can be added several times (EMA 9 + EMA 21),
              // so their row always offers "+"; remove individual ones from Active.
              const canRemove = on && ind.params.length === 0;
              return (
                <div
                  key={ind.fn}
                  className="flex items-center justify-between px-4 py-1.5 group/item hover:bg-surface-2 transition-colors"
                >
                  <span className={`text-[11px] font-mono ${on ? "text-accent-cyan" : "text-surface-4"}`}>
                    {ind.label}
                  </span>
                  <button
                    onClick={() => canRemove ? handleRemoveFn(ind.fn) : handleAdd(ind)}
                    title={canRemove ? "Remove" : on ? "Add another" : "Add"}
                    className={`text-[10px] font-mono transition-colors ${
                      canRemove
                        ? "text-surface-4 hover:text-accent-red opacity-0 group-hover/item:opacity-100"
                        : "text-surface-4 hover:text-accent-cyan"
                    }`}
                  >
                    {canRemove ? "✕" : "+"}
                  </button>
                </div>
              );
            })}
          </Section>
        );
      })}

      {/* ── Param input modal ───────────────────────────────────────────────── */}
      {adding && (
        <div className="mx-2 mt-2 mb-2 bg-surface-2 border border-surface-3 rounded p-3">
          <p className="text-[11px] font-mono text-accent-cyan mb-2">{adding.label}</p>
          {adding.params.map(p => (
            <div key={p.key} className="mb-2">
              <label className="text-[10px] text-surface-4 block mb-1">{p.label}</label>
              <input
                type="number"
                value={params[p.key] ?? p.default}
                min={p.int === false ? 0.1 : 1}
                step={p.int === false ? 0.1 : 1}
                onChange={e => setParams(prev => ({ ...prev, [p.key]: e.target.value }))}
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
