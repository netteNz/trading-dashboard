import { MARKET_ORDER } from "../lib/markets";

// STOCKS | CRYPTO segmented switch. The market is derived from the symbol, so
// switching just jumps to that market's default symbol.
export default function MarketToggle({ market, markets, onChange }) {
  return (
    <div className="flex items-center bg-surface-2 border border-surface-3 rounded overflow-hidden">
      {MARKET_ORDER.map(m => (
        <button
          key={m}
          onClick={() => m !== market && onChange(m)}
          className={`text-[10px] font-mono uppercase tracking-wider px-2 py-1 transition-colors ${
            m === market
              ? "bg-surface-3 text-accent-cyan"
              : "text-surface-4 hover:text-white"
          }`}
        >
          {markets[m]?.label ?? m}
        </button>
      ))}
    </div>
  );
}
