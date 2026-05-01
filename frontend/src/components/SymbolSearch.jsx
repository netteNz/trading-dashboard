import { useState, useRef, useEffect } from "react";

const POPULAR = ["SPY", "QQQ", "AAPL", "TSLA", "NVDA", "AMZN", "MSFT", "META"];

export default function SymbolSearch({ value, onChange }) {
  const [query,     setQuery]     = useState(value || "");
  const [open,      setOpen]      = useState(false);
  const [results,   setResults]   = useState(POPULAR.map(s => ({ symbol: s, name: "" })));
  const [searching, setSearching] = useState(false);
  const inputRef   = useRef(null);
  const debounceRef = useRef(null);

  const search = async (q) => {
    if (!q) {
      setResults(POPULAR.map(s => ({ symbol: s, name: "" })));
      setSearching(false);
      return;
    }
    setSearching(true);
    try {
      const res  = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
      const data = res.ok ? await res.json() : [];
      // Merge API results with any POPULAR matches not already returned
      const apiSymbols = new Set(data.map(r => r.symbol));
      const popularHits = POPULAR
        .filter(s => s.includes(q.toUpperCase()) && !apiSymbols.has(s))
        .map(s => ({ symbol: s, name: "" }));
      setResults([...data, ...popularHits]);
    } catch {
      setResults(
        POPULAR
          .filter(s => s.includes(q.toUpperCase()))
          .map(s => ({ symbol: s, name: "" }))
      );
    } finally {
      setSearching(false);
    }
  };

  const handleChange = (e) => {
    const q = e.target.value.toUpperCase();
    setQuery(q);
    setOpen(true);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(q), 350);
  };

  const handleFocus = () => {
    setOpen(true);
    if (!query) search("");
  };

  const select = (sym) => {
    setQuery(sym);
    setOpen(false);
    onChange(sym);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && query.trim()) select(query.trim().toUpperCase());
    if (e.key === "Escape") setOpen(false);
  };

  // Keep input in sync when parent changes symbol externally
  useEffect(() => { setQuery(value || ""); }, [value]);

  return (
    <div className="relative">
      <div className="flex items-center gap-2 bg-surface-2 border border-surface-3 rounded px-3 py-1.5 focus-within:border-accent-cyan transition-colors">
        <span className="text-surface-4 text-xs">$</span>
        <input
          ref={inputRef}
          value={query}
          onChange={handleChange}
          onFocus={handleFocus}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          onKeyDown={handleKeyDown}
          placeholder="SYMBOL"
          className="bg-transparent text-accent-cyan text-sm font-mono outline-none w-28 placeholder:text-surface-4"
        />
        {searching && (
          <span className="w-3 h-3 border border-accent-cyan border-t-transparent rounded-full animate-spin shrink-0" />
        )}
      </div>

      {open && results.length > 0 && (
        <div className="absolute top-full mt-1 left-0 z-50 bg-surface-1 border border-surface-3 rounded shadow-xl min-w-[180px]">
          {results.slice(0, 10).map(r => (
            <button
              key={r.symbol}
              onMouseDown={() => select(r.symbol)}
              className="w-full text-left px-3 py-1.5 flex items-center justify-between gap-3 hover:bg-surface-2 transition-colors"
            >
              <span className="text-xs font-mono text-accent-cyan">{r.symbol}</span>
              {r.name && (
                <span className="text-[10px] font-mono text-surface-4 truncate max-w-[100px]">{r.name}</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
