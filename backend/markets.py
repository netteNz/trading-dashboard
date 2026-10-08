"""
Markets the dashboard can switch between, and crypto symbol helpers.

Crypto symbols use Yahoo's "BTC-USD" form everywhere in the app (URL path,
Socket.IO room, frontend). Alpaca wants "BTC/USD": convert only at that boundary.
"""
import re

MARKETS = {
    "stocks": {"label": "Stocks", "default": "SPY",
               "watchlist": ["SPY", "QQQ", "AAPL", "TSLA", "NVDA", "AMZN", "MSFT", "META"]},
    "crypto": {"label": "Crypto", "default": "BTC-USD",
               "watchlist": ["BTC-USD", "ETH-USD", "SOL-USD"]},
}

_CRYPTO_RE = re.compile(r"^[A-Z0-9]{2,10}[-/]USD$")


def is_crypto(symbol: str) -> bool:
    return bool(_CRYPTO_RE.match(symbol.upper()))


def market_of(symbol: str) -> str:
    return "crypto" if is_crypto(symbol) else "stocks"


def to_alpaca_crypto(symbol: str) -> str:
    """"BTC-USD" → "BTC/USD"."""
    return symbol.upper().replace("-", "/")


def from_alpaca_crypto(symbol: str) -> str:
    """"BTC/USD" → "BTC-USD"."""
    return symbol.upper().replace("/", "-")
