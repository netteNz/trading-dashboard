import { useState, useEffect, useMemo } from "react";
import { useChartData }  from "./hooks/useChartData";
import { useWebSocket }  from "./hooks/useWebSocket";
import TradingChart      from "./components/TradingChart";
import SymbolSearch      from "./components/SymbolSearch";
import IndicatorPanel    from "./components/IndicatorPanel";
import Toolbar           from "./components/Toolbar";
import RLAgentMetrics    from "./components/RLAgentMetrics";

async function fetchPreset(name) {
  const res = await fetch(`/api/presets/${name}`);
  if (!res.ok) throw new Error(`preset ${name} not found`);
  return res.json();
}

export default function App() {
  const [symbol,    setSymbol]    = useState("SPY");
  const [timeframe, setTimeframe] = useState("1Day");
  const [preset,    setPreset]    = useState("full");
  const [indicators, setIndicators] = useState([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [rlMetricsCollapsed, setRlMetricsCollapsed] = useState(false);
  

  // Load the default preset from the backend on mount
  useEffect(() => {
    fetchPreset("full").then(setIndicators).catch(() => {});
  }, []);

  const [rlSignals, setRlSignals] = useState([]);

  const handlePresetChange = (p) => {
    setPreset(p);
    fetchPreset(p).then(setIndicators).catch(() => {});
  };

  const handleToggleRL = (enabled, signals) => {
    setRlSignals(enabled ? signals : []);
  };

  const { data, loading, error, refetch } = useChartData(symbol, timeframe, indicators);
  const { lastTick, connected }           = useWebSocket(symbol);

  // Latest OHLCV from the last candle
  const latestCandle = useMemo(() => {
    if (!data?.candles?.length) return null;
    return data.candles[data.candles.length - 1];
  }, [data]);

  // prevClose = last fetched candle close; live ticks are compared against this
  const prevClose = latestCandle?.close ?? null;

  return (
    <div
      className="flex flex-col h-screen overflow-hidden bg-surface-0"
      style={{ fontFamily: "'JetBrains Mono', monospace" }}
    >
      {/* ── Top bar ── */}
      <header className="flex items-center gap-3 px-3 py-2 bg-surface-1 border-b border-surface-2 shrink-0">
        {/* Logo */}
        <div className="flex items-center gap-2 mr-2">
          <span className="text-accent-cyan text-base font-bold tracking-tighter">⬡ TRADEVIEW</span>
          <span className="text-[10px] text-surface-4 uppercase tracking-widest hidden sm:block">Personal</span>
        </div>

        <div className="h-4 w-px bg-surface-3" />

        {/* Symbol search */}
        <SymbolSearch value={symbol} onChange={setSymbol} />

        {/* OHLCV readout */}
        {latestCandle && (
          <div className="hidden md:flex items-center gap-3 text-[11px] font-mono ml-2">
            {[
              ["O", latestCandle.open],
              ["H", latestCandle.high],
              ["L", latestCandle.low],
              ["C", latestCandle.close],
            ].map(([lbl, val]) => (
              <span key={lbl} className="text-surface-4">
                <span className="text-surface-3 mr-0.5">{lbl}</span>
                <span className={lbl === "H" ? "text-accent-green" : lbl === "L" ? "text-accent-red" : "text-white"}>
                  {val?.toFixed(2) ?? "—"}
                </span>
              </span>
            ))}
            {latestCandle.volume && (
              <span className="text-surface-4">
                <span className="text-surface-3 mr-0.5">V</span>
                <span className="text-accent-yellow">{(latestCandle.volume / 1e6).toFixed(2)}M</span>
              </span>
            )}
          </div>
        )}

        <div className="ml-auto flex items-center gap-2">
          {connected && (
            <span className="flex items-center gap-1 text-[10px] font-mono text-accent-green">
              <span className="live-dot w-1.5 h-1.5 rounded-full bg-accent-green inline-block" />
              LIVE
            </span>
          )}
          <button
            onClick={() => setSidebarOpen(o => !o)}
            className="text-[11px] font-mono text-surface-4 hover:text-accent-cyan px-2 py-1 rounded hover:bg-surface-2 transition-colors"
          >
            {sidebarOpen ? "« Hide" : "Panel »"}
          </button>
        </div>
      </header>

      {/* ── Toolbar (timeframe / preset) ── */}
      <Toolbar
        symbol={symbol}
        timeframe={timeframe}
        preset={preset}
        lastTick={lastTick}
        connected={connected}
        prevClose={prevClose}
        onTimeframeChange={setTimeframe}
        onPresetChange={handlePresetChange}
        onToggleRL={handleToggleRL}
      />

      {/* ── Main body ── */}
      <div className="flex flex-1 overflow-hidden">

        {/* Chart area */}
        <main className="flex-1 overflow-auto relative bg-surface-0">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center z-10 bg-surface-0/80">
              <div className="flex flex-col items-center gap-3">
                <div className="w-5 h-5 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
                <span className="text-[11px] font-mono text-surface-4">Fetching {symbol}…</span>
              </div>
            </div>
          )}

          {error && !loading && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <p className="text-accent-red text-sm font-mono mb-2">⚠ {error}</p>
                <button
                  onClick={refetch}
                  className="text-[11px] font-mono text-accent-cyan hover:underline"
                >
                  Retry
                </button>
              </div>
            </div>
          )}

          {data && !loading && (
            <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
              <TradingChart data={data} lastTick={lastTick} rlSignals={rlSignals} />
            </div>
          )}
        </main>

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
      </div>

      {/* ── Bottom ticker ── */}
      <footer className="h-6 bg-surface-1 border-t border-surface-2 overflow-hidden flex items-center shrink-0">
        <div className="ticker-tape flex items-center gap-8 text-[10px] font-mono text-surface-4 whitespace-nowrap">
          {["SPY", "QQQ"].map(sym => (
            <button
              key={sym}
              onClick={() => setSymbol(sym)}
              className="hover:text-accent-cyan transition-colors"
            >
              {sym} —
            </button>
          ))}
          {/* Duplicate for seamless scroll */}
          {["SPY", "QQQ"].map(sym => (
            <button
              key={`${sym}_2`}
              onClick={() => setSymbol(sym)}
              className="hover:text-accent-cyan transition-colors"
            >
              {sym} —
            </button>
          ))}
        </div>
      </footer>
    </div>
  );
}
