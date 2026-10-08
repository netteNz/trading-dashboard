// Mirrors backend/markets.py: crypto symbols use Yahoo's "BTC-USD" form app-wide.
const CRYPTO_RE = /^[A-Z0-9]{2,10}[-/]USD$/;

export const MARKET_ORDER = ["stocks", "crypto"];

export function marketOf(symbol) {
  return CRYPTO_RE.test((symbol || "").toUpperCase()) ? "crypto" : "stocks";
}

// Fallback until /api/markets answers (and if it fails).
export const DEFAULT_MARKETS = {
  stocks: { label: "Stocks", default: "SPY",     watchlist: ["SPY", "QQQ", "AAPL", "TSLA", "NVDA", "AMZN", "MSFT", "META"] },
  crypto: { label: "Crypto", default: "BTC-USD", watchlist: ["BTC-USD", "ETH-USD", "SOL-USD"] },
};

// Compact volume: 12.37 (coins) · 845.2K · 82.34M · 31.20B.
export function formatVolume(v) {
  if (v == null || !Number.isFinite(v)) return "—";
  const abs = Math.abs(v);
  if (abs >= 1e9) return `${(v / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${(v / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return v.toFixed(abs < 10 ? 4 : 2);
}
