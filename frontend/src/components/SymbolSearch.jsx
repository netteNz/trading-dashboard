import { useState, useRef, useEffect } from "react";

const POPULAR = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA", "AMD", "META", "AMZN", "GOOGL", "BTC-USD", "ETH-USD"];

export default function SymbolSearch({ value, onChange }) {
  const [query,    setQuery]    = useState(value || "");
  const [open,     setOpen]     = useState(false);
  const [results,  setResults]  = useState(POPULAR);
  const [filtered, setFiltered] = useState(POPULAR);
  const inputRef = useRef(null);

  useEffect(() => {
    if (!query) {
      setFiltered(POPULAR);
      return;
    }
    setFiltered(
      POPULAR.filter(s => s.toLowerCase().includes(query.toLowerCase()))
    );
  }, [query]);

  const select = (sym) => {
    setQuery(sym);
    setOpen(false);
    onChange(sym);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && query.trim()) {
      select(query.trim().toUpperCase());
    }
    if (e.key === "Escape") setOpen(false);
  };

  return (
    <div className="relative">
      <div className="flex items-center gap-2 bg-surface-2 border border-surface-3 rounded px-3 py-1.5 focus-within:border-accent-cyan transition-colors">
        <span className="text-surface-4 text-xs">$</span>
        <input
          ref={inputRef}
          value={query}
          onChange={e => { setQuery(e.target.value.toUpperCase()); setOpen(true); }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={handleKeyDown}
          placeholder="SYMBOL"
          className="bg-transparent text-accent-cyan text-sm font-mono outline-none w-28 placeholder:text-surface-4"
        />
      </div>

      {open && filtered.length > 0 && (
        <div className="absolute top-full mt-1 left-0 z-50 bg-surface-1 border border-surface-3 rounded shadow-xl min-w-[140px]">
          {filtered.slice(0, 10).map(sym => (
            <button
              key={sym}
              onMouseDown={() => select(sym)}
              className="w-full text-left px-3 py-1.5 text-xs font-mono text-surface-4 hover:bg-surface-2 hover:text-accent-cyan transition-colors"
            >
              {sym}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
