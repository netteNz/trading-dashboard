import { useState } from "react";

const COLLAPSE_KEY = "tv.scorecard";
const MIN_SAMPLE = 5;

function readCollapsed() {
  try { return localStorage.getItem(COLLAPSE_KEY) === "1"; } catch { return false; }
}

const pct = (x) => `${Math.round(x * 100)}%`;
const signed = (x) => `${x > 0 ? "+" : ""}${x.toFixed(2)}%`;

// One side (BUY or SELL) of a combo's in-sample scorecard.
function Side({ label, arrow, color, s, base }) {
  if (!s || (s.n === 0 && s.open === 0)) return null;
  const thin = s.n < MIN_SAMPLE;
  return (
    <div className={`flex items-center gap-2 ${thin ? "opacity-50" : ""}`}>
      <span className={color}>{arrow} {label} {s.n}</span>
      {thin ? (
        <span className="text-[#8b949e]">too few to judge{s.open ? ` · ${s.open} open` : ""}</span>
      ) : (
        <>
          <span className="text-white">hit {pct(s.hit)}</span>
          {base != null && <span className="text-[#8b949e]">(base {pct(base)})</span>}
          <span className="text-[#8b949e]">· median <span className="text-white">{signed(s.median_move_pct)}</span></span>
          {s.median_mae_atr != null && (
            <span className="text-[#8b949e]">· drawdown <span className="text-white">{s.median_mae_atr.toFixed(1)} ATR</span></span>
          )}
          {s.open > 0 && <span className="text-[#8b949e]">· {s.open} open</span>}
        </>
      )}
    </div>
  );
}

// What price did N bars after each combo marker, on the loaded bars. Context
// for judging a setup on this symbol/timeframe, not a backtest.
export default function SignalScorecard({ stats }) {
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const entries = Object.entries(stats ?? {});
  if (!entries.length) return null;

  const toggle = () => {
    const next = !collapsed;
    setCollapsed(next);
    try { localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0"); } catch { /* storage blocked */ }
  };

  return (
    <div className="absolute top-2 left-2 z-[5] bg-surface-1/90 border border-surface-3 rounded px-2 py-1.5 text-[10px] font-mono max-w-[min(560px,calc(100%-80px))]">
      <button onClick={toggle} className="flex items-center gap-1.5 text-[#8b949e] hover:text-accent-cyan">
        <span>{collapsed ? "▸" : "▾"}</span>
        <span className="uppercase tracking-wider">Scorecard</span>
        {collapsed && <span className="normal-case">· {entries.map(([k]) => k).join(", ")}</span>}
      </button>
      {!collapsed && (
        <div className="mt-1 flex flex-col gap-1.5">
          {entries.map(([name, s]) => (
            <div key={name} className="flex flex-col gap-0.5">
              <span className="text-accent-cyan">{name} <span className="text-[#8b949e]">· {s.horizon} bars after</span></span>
              {s.buy.n + s.buy.open + s.sell.n + s.sell.open === 0 ? (
                <span className="text-[#8b949e]">no markers on these bars</span>
              ) : (
                <>
                  <Side label="BUY"  arrow="▲" color="text-accent-green" s={s.buy}  base={s.base_up} />
                  <Side label="SELL" arrow="▼" color="text-accent-red"   s={s.sell}
                        base={s.base_up == null ? null : 1 - s.base_up} />
                </>
              )}
            </div>
          ))}
          <span className="text-[#8b949e] opacity-70">In-sample on the loaded bars · no costs · not a backtest</span>
        </div>
      )}
    </div>
  );
}
