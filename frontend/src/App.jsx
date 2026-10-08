import { useState, useEffect, useMemo } from "react";
import { useChartData }  from "./hooks/useChartData";
import { useWebSocket }  from "./hooks/useWebSocket";
import { useRLSignals }  from "./hooks/useRLSignals";
import TradingChart      from "./components/TradingChart";
import SymbolSearch      from "./components/SymbolSearch";
import IndicatorPanel    from "./components/IndicatorPanel";
import Toolbar           from "./components/Toolbar";
import RLAgentMetrics    from "./components/RLAgentMetrics";
import MarketToggle      from "./components/MarketToggle";
import SignalScorecard   from "./components/SignalScorecard";
import { apiFetch }      from "./lib/api";
import { useAuth }       from "./auth/AuthContext";
import { sameSet }       from "./lib/indicators";
import { marketOf, DEFAULT_MARKETS, formatVolume } from "./lib/markets";

const NO_SIGNALS = [];
const SIGNALS_KEY = "tv.showSignals";
const SYMBOL_KEY  = "tv.symbol";

function readShowSignals() {
  try { return localStorage.getItem(SIGNALS_KEY) !== "0"; } catch { return true; }
}

function readSymbol() {
  try { return localStorage.getItem(SYMBOL_KEY) || "SPY"; } catch { return "SPY"; }
}

export default function App() {
  const [symbol,    setSymbol]    = useState(readSymbol);
  const [timeframe, setTimeframe] = useState("1Day");
  const [markets,   setMarkets]   = useState(DEFAULT_MARKETS);
  const [allPresets, setPresets]  = useState([]);
  const [presetsReady, setPresetsReady] = useState(false);
  const [indicators, setIndicators] = useState([]);
  const [rlEnabled, setRlEnabled] = useState(false);
  const [showSignals, setShowSignals] = useState(readShowSignals);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [rlMetricsCollapsed, setRlMetricsCollapsed] = useState(false);
  const { user, logout } = useAuth();


  // Presets (labels, descriptions, indicator lists) come from the backend once.
  useEffect(() => {
    apiFetch("/api/presets")
      .then(res => (res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`))))
      .then(list => {
        setPresets(list);
        const full = list.find(p => p.name === "full");
        if (full) setIndicators(full.indicators);
      })
      .catch(e => console.warn("[presets] failed to load:", e))
      .finally(() => setPresetsReady(true));    // on failure the chart still loads (candles only)
    apiFetch("/api/markets")
      .then(res => (res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`))))
      .then(setMarkets)
      .catch(e => console.warn("[markets] failed to load:", e));
  }, []);

  // The market follows the symbol (typing BTC-USD switches to crypto); the
  // last symbol is remembered, so the market survives a reload too.
  const market = marketOf(symbol);
  useEffect(() => {
    try { localStorage.setItem(SYMBOL_KEY, symbol); } catch { /* storage blocked */ }
  }, [symbol]);
  const watchlist = markets[market]?.watchlist ?? [];

  // Only the presets that make sense for this market (backend "markets" tag).
  const presets = useMemo(
    () => allPresets.filter(p => !p.markets || p.markets.includes(market)),
    [allPresets, market],
  );

  const handleMarketChange = (m) => {
    setSymbol(markets[m]?.default ?? DEFAULT_MARKETS[m].default);
    // A combo from the other market would linger un-highlighted: reset to Full.
    const current = allPresets.find(p => sameSet(p.indicators, indicators));
    const full = allPresets.find(p => p.name === "full");
    if (current?.markets && !current.markets.includes(m) && full) setIndicators(full.indicators);
  };

  // The highlighted preset is whichever one matches the active list exactly,
  // so a manual edit clears it.
  const activePreset = useMemo(
    () => presets.find(p => sameSet(p.indicators, indicators))?.name ?? null,
    [presets, indicators],
  );
  const combos = useMemo(() => presets.filter(p => p.kind === "combo"), [presets]);

  const handlePresetChange = (name) => {
    const p = presets.find(x => x.name === name);
    if (p) setIndicators(p.indicators);
  };

  const handleToggleSignals = (on) => {
    setShowSignals(on);
    try { localStorage.setItem(SIGNALS_KEY, on ? "1" : "0"); } catch { /* storage blocked */ }
  };

  const rl = useRLSignals(symbol);
  // Stable reference: a fresh [] each render would rebuild the chart every render.
  const rlSignals = useMemo(
    () => (rlEnabled && rl.data?.signals) || NO_SIGNALS,
    [rlEnabled, rl.data],
  );

  const { data, loading, error, refetch } = useChartData(symbol, timeframe, indicators, presetsReady);
  const { lastTick, streamStatus }        = useWebSocket(symbol, market);

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

        {/* Market + symbol search */}
        <MarketToggle market={market} markets={markets} onChange={handleMarketChange} />
        <SymbolSearch value={symbol} onChange={setSymbol} popular={watchlist} />

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
            {latestCandle.volume != null && (
              <span className="text-surface-4">
                <span className="text-surface-3 mr-0.5">V</span>
                <span className="text-accent-yellow">{formatVolume(latestCandle.volume)}</span>
              </span>
            )}
          </div>
        )}

        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={() => setSidebarOpen(o => !o)}
            className="text-[11px] font-mono text-surface-4 hover:text-accent-cyan px-2 py-1 rounded hover:bg-surface-2 transition-colors"
          >
            {sidebarOpen ? "« Hide" : "Panel »"}
          </button>

          <div className="h-4 w-px bg-surface-3" />

          <div className="flex items-center gap-2">
            {user?.avatar_url && (
              <img src={user.avatar_url} alt="" className="w-5 h-5 rounded-full border border-surface-3" />
            )}
            <span className="text-[11px] font-mono text-surface-4 hidden sm:block">{user?.login}</span>
            {!user?.auth_disabled && (
              <button
                onClick={logout}
                className="text-[11px] font-mono text-surface-4 hover:text-accent-red px-2 py-1 rounded hover:bg-surface-2 transition-colors"
              >
                Sign out
              </button>
            )}
          </div>
        </div>
      </header>

      {/* ── Toolbar (timeframe / preset) ── */}
      <Toolbar
        symbol={symbol}
        timeframe={timeframe}
        presets={presets}
        activePreset={activePreset}
        lastTick={lastTick}
        streamStatus={streamStatus}
        market={market}
        prevClose={prevClose}
        onTimeframeChange={setTimeframe}
        onPresetChange={handlePresetChange}
        rl={{ enabled: rlEnabled, onToggle: setRlEnabled, loading: rl.loading, available: !!rl.data }}
        showSignals={showSignals}
        onToggleSignals={handleToggleSignals}
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

          {/* Stays mounted while refetching (the spinner overlays it) so zoom survives */}
          {data && (
            <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
              <TradingChart
                data={data}
                lastTick={data.symbol === symbol ? lastTick : null}
                rlSignals={rlSignals}
                showSignals={showSignals}
                timeframe={data.timeframe}
                viewKey={`${data.symbol}|${data.timeframe}`}
              />
            </div>
          )}
          {data && showSignals && <SignalScorecard stats={data.stats} />}
        </main>

      {/* Sidebar: Indicators + RL Metrics */}
      {sidebarOpen && (
        <div className="flex" style={{ transition: "width 0.2s ease" }}>
          {/* Indicators Panel */}
          <aside className="w-52 bg-surface-1 border-l border-surface-2 overflow-y-auto shrink-0">
            <IndicatorPanel
              active={indicators}
              onChange={setIndicators}
              combos={combos}
              symbol={symbol}
              watchlist={watchlist}
              onSymbolChange={setSymbol}
            />
          </aside>
      
          {/* RL Agent P&L Panel */}
          <RLAgentMetrics
            metrics={rl.data}
            isCollapsed={rlMetricsCollapsed}
            onToggleCollapse={() => setRlMetricsCollapsed(!rlMetricsCollapsed)}
          />
        </div>
      )}
      </div>

      {/* ── Bottom ticker ── */}
      <footer className="h-6 bg-surface-1 border-t border-surface-2 overflow-hidden flex items-center shrink-0">
        <div className="ticker-tape flex items-center gap-8 text-[10px] font-mono text-surface-4 whitespace-nowrap">
          {watchlist.map(sym => (
            <button
              key={sym}
              onClick={() => setSymbol(sym)}
              className="hover:text-accent-cyan transition-colors"
            >
              {sym} —
            </button>
          ))}
          {/* Duplicate for seamless scroll */}
          {watchlist.map(sym => (
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
