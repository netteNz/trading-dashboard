import math
import os
import time
import asyncio
import logging
import threading
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

from markets import is_crypto, to_alpaca_crypto, from_alpaca_crypto

load_dotenv()

logger = logging.getLogger(__name__)

# ── Timeframe maps ─────────────────────────────────────────────────────────────

TIMEFRAME_MAP_YF = {
    "1Min":  "1m",
    "5Min":  "5m",
    "15Min": "15m",
    "30Min": "30m",
    "1Hour": "1h",
    "1Day":  "1d",
    "1Week": "1wk",
}

# Longest window fetched from Yahoo. Intraday caps are Yahoo's own limits
# (1m: ~7 days, 5m–30m: 60 days, 1h: 730 days).
MAX_LOOKBACK_YF = {
    "1Min":  timedelta(days=7),
    "5Min":  timedelta(days=59),
    "15Min": timedelta(days=59),
    "30Min": timedelta(days=59),
    "1Hour": timedelta(days=729),
    "1Day":  timedelta(days=365 * 25),
    "1Week": timedelta(days=365 * 25),
}

# Bars per US trading day (regular session) on Yahoo; 1Week is handled apart.
BARS_PER_DAY_YF = {"1Min": 390, "5Min": 78, "15Min": 26, "30Min": 13, "1Hour": 7, "1Day": 1}
# Crypto trades 24/7: every calendar day is a full day of bars.
BARS_PER_DAY_247 = {"1Min": 1440, "5Min": 288, "15Min": 96, "30Min": 48, "1Hour": 24, "1Day": 1}


def yf_lookback(timeframe: str, limit: int, crypto: bool = False) -> timedelta:
    """How far back to fetch so roughly `limit` bars come back, not years more.

    Trading days → calendar days (5 of 7, plus ~10% and a week of slack for
    holidays and half days), capped at Yahoo's limit for the interval.
    Crypto (24/7) bars map straight onto calendar days, plus a day of slack.
    """
    if timeframe == "1Week":
        days = limit * 7 + 14
    elif crypto:
        days = math.ceil(limit / BARS_PER_DAY_247.get(timeframe, 1)) + 1
    else:
        trading_days = math.ceil(limit / BARS_PER_DAY_YF.get(timeframe, 1))
        days = math.ceil(trading_days * 7 / 5 * 1.1) + 7
    return min(timedelta(days=days), MAX_LOOKBACK_YF.get(timeframe, timedelta(days=365 * 25)))

# How far back to start an Alpaca bar query. Generous enough that `limit` bars
# (up to a few thousand) fit inside the window, including weekends/holidays.
LOOKBACK_ALPACA = {
    "1Min":  timedelta(days=10),
    "5Min":  timedelta(days=45),
    "15Min": timedelta(days=90),
    "30Min": timedelta(days=180),
    "1Hour": timedelta(days=365 * 2),
    "1Day":  timedelta(days=365 * 6),
    "1Week": timedelta(days=365 * 15),
}



def _alpaca_timeframe(timeframe: str):
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    return {
        "1Min":  TimeFrame(1,  TimeFrameUnit.Minute),
        "5Min":  TimeFrame(5,  TimeFrameUnit.Minute),
        "15Min": TimeFrame(15, TimeFrameUnit.Minute),
        "30Min": TimeFrame(30, TimeFrameUnit.Minute),
        "1Hour": TimeFrame(1,  TimeFrameUnit.Hour),
        "1Day":  TimeFrame(1,  TimeFrameUnit.Day),
        "1Week": TimeFrame(1,  TimeFrameUnit.Week),
    }.get(timeframe, TimeFrame(1, TimeFrameUnit.Day))


def _alpaca_frame(bars: pd.DataFrame, symbol: str, limit: int) -> pd.DataFrame:
    """Alpaca bars response (symbol, timestamp MultiIndex) → plain OHLCV frame."""
    # An empty response has a plain RangeIndex with no "timestamp" level.
    if bars.empty:
        raise ValueError(f"No data returned for {symbol}")
    bars.index = bars.index.get_level_values("timestamp")
    bars.index = pd.to_datetime(bars.index, utc=True)
    bars = bars[["open", "high", "low", "close", "volume"]].dropna().sort_index()
    return bars.tail(limit)

# ── Historical data ────────────────────────────────────────────────────────────

# How long fetched bars are reused. Indicator and preset changes refetch the
# same bars, and the download is ~all of a chart request's time. Live ticks
# keep the last candle current in between.
CACHE_TTL_SECS = {"1Day": 300, "1Week": 900}
CACHE_TTL_DEFAULT = 60          # intraday
CACHE_MAX = 64


class DataSource:
    def __init__(self, provider: str = None):
        self.provider = provider or os.getenv("DATA_PROVIDER", "yfinance")
        self._alpaca = None
        self._alpaca_crypto = None
        self._cache: dict[tuple, tuple[float, pd.DataFrame]] = {}
        self._cache_lock = threading.Lock()

    def _get_alpaca(self):
        if self._alpaca is None:
            try:
                from alpaca.data.historical import StockHistoricalDataClient
                self._alpaca = StockHistoricalDataClient(
                    api_key=os.getenv("ALPACA_API_KEY"),
                    secret_key=os.getenv("ALPACA_SECRET_KEY"),
                )
            except Exception as e:
                raise RuntimeError(f"Alpaca init failed: {e}")
        return self._alpaca

    def _get_alpaca_crypto(self):
        # Crypto market data needs no keys; pass them when present (higher rate limit).
        if self._alpaca_crypto is None:
            from alpaca.data.historical import CryptoHistoricalDataClient
            self._alpaca_crypto = CryptoHistoricalDataClient(
                api_key=os.getenv("ALPACA_API_KEY") or None,
                secret_key=os.getenv("ALPACA_SECRET_KEY") or None,
            )
        return self._alpaca_crypto

    def get_bars(self, symbol: str, timeframe: str = "1Day", limit: int = 500) -> pd.DataFrame:
        """OHLCV bars, served from a short-lived in-memory cache when possible."""
        symbol = symbol.upper()
        key = (symbol, timeframe, limit)
        now = time.monotonic()
        with self._cache_lock:
            hit = self._cache.get(key)
            if hit and hit[0] > now:
                return hit[1].copy()

        df = self._fetch_bars(symbol, timeframe, limit)     # errors are not cached

        with self._cache_lock:
            if len(self._cache) >= CACHE_MAX:
                for k in [k for k, (exp, _) in self._cache.items() if exp <= now]:
                    del self._cache[k]
                if len(self._cache) >= CACHE_MAX:
                    del self._cache[min(self._cache, key=lambda k: self._cache[k][0])]
            ttl = CACHE_TTL_SECS.get(timeframe, CACHE_TTL_DEFAULT)
            self._cache[key] = (now + ttl, df)
        return df.copy()

    def _fetch_bars(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        if is_crypto(symbol):
            # Always Alpaca for crypto, whatever DATA_PROVIDER says: Yahoo's
            # intraday crypto bars carry zero volume on a third or more of bars,
            # which breaks VWAP/OBV/CMF/MFI. Yahoo stays as the fallback.
            try:
                return self._get_bars_alpaca_crypto(symbol, timeframe, limit)
            except Exception as e:
                logger.warning("Alpaca crypto bars for %s failed (%s) — falling back to Yahoo", symbol, e)
                return self._get_bars_yfinance(symbol, timeframe, limit)
        if self.provider == "alpaca":
            return self._get_bars_alpaca(symbol, timeframe, limit)
        return self._get_bars_yfinance(symbol, timeframe, limit)

    def _get_bars_yfinance(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        yf_interval = TIMEFRAME_MAP_YF.get(timeframe, "1d")
        # Only as much history as `limit` needs (a fixed 5y for daily bars made
        # every chart load download ~2.5x the data it kept).
        start = datetime.now(timezone.utc) - yf_lookback(timeframe, limit, crypto=is_crypto(symbol))

        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start, interval=yf_interval)

        if df.empty:
            raise ValueError(f"No data returned for {symbol}")

        df.index = pd.to_datetime(df.index, utc=True)
        df.index.name = "timestamp"
        df.columns = [c.lower() for c in df.columns]
        df = df[["open", "high", "low", "close", "volume"]].dropna()
        return df.tail(limit)

    def _get_bars_alpaca(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        from alpaca.common.enums import Sort
        from alpaca.data.enums import DataFeed
        from alpaca.data.requests import StockBarsRequest

        client = self._get_alpaca()
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=_alpaca_timeframe(timeframe),
            start=datetime.now(timezone.utc) - LOOKBACK_ALPACA.get(timeframe, timedelta(days=365 * 6)),
            limit=limit,
            # Newest first: with the default ascending sort, `limit` keeps the
            # *oldest* bars after `start`, and intraday charts showed stale data.
            sort=Sort.DESC,
            feed=DataFeed.SIP if os.getenv("ALPACA_FEED", "iex").lower() == "sip" else DataFeed.IEX,
        )
        return _alpaca_frame(client.get_stock_bars(request).df, symbol, limit)

    def _get_bars_alpaca_crypto(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        from alpaca.common.enums import Sort
        from alpaca.data.requests import CryptoBarsRequest

        request = CryptoBarsRequest(
            symbol_or_symbols=to_alpaca_crypto(symbol),
            timeframe=_alpaca_timeframe(timeframe),
            start=datetime.now(timezone.utc) - yf_lookback(timeframe, limit, crypto=True),
            limit=limit,
            sort=Sort.DESC,
        )
        return _alpaca_frame(self._get_alpaca_crypto().get_crypto_bars(request).df, symbol, limit)

    def search_symbols(self, query: str) -> list:
        try:
            ticker = yf.Ticker(query.upper())
            info = ticker.fast_info
            return [{
                "symbol": query.upper(),
                "name": getattr(info, "name", query.upper()),
                "exchange": getattr(info, "exchange", "—"),
            }]
        except Exception:
            return []


# ── Live WebSocket stream ──────────────────────────────────────────────────────

class AlpacaStream:
    """
    Wraps alpaca-py StockDataStream (kind="stock") or CryptoDataStream
    (kind="crypto") and emits normalised bar dicts to a callback.

    Crypto symbols go in and come out in the app's "BTC-USD" form; the
    "BTC/USD" form Alpaca uses never leaves this class.

    Bar dict shape (matches /api/chart candle contract):
        {
            "symbol": "SPY",
            "time":   1704067200,   # unix seconds (int)
            "open":   476.32,
            "high":   478.91,
            "low":    475.10,
            "close":  477.85,
            "volume": 82341200,     # int for stocks; float (coins) for crypto
        }

    Usage:
        stream = AlpacaStream(on_bar=my_callback, feed="iex")
        stream.subscribe("SPY", "QQQ")
        stream.run()          # blocking — call from a daemon thread
    """
    
    def __init__(self, on_bar, feed: str = "iex", kind: str = "stock"):
        self._on_bar  = on_bar
        self._feed    = feed
        self._crypto  = kind == "crypto"
        self._symbols: set[str] = set()
        keys = dict(api_key=os.environ["ALPACA_API_KEY"], secret_key=os.environ["ALPACA_SECRET_KEY"])
        if self._crypto:
            from alpaca.data.live import CryptoDataStream
            from alpaca.data.enums import CryptoFeed
            self._stream = CryptoDataStream(**keys, feed=CryptoFeed.US)
        else:
            from alpaca.data.live import StockDataStream
            from alpaca.data.enums import DataFeed
            self._stream = StockDataStream(
                **keys, feed=DataFeed.IEX if feed.lower() == "iex" else DataFeed.SIP)

    # ── public ────────────────────────────────────────────────────────────────

    def subscribe(self, *symbols: str):
        """Register one or more symbols for bar updates."""
        clean = [s.upper() for s in symbols]
        self._symbols.update(clean)
        self._stream.subscribe_bars(self._handle_bar, *self._wire(clean))
        logger.info("AlpacaStream subscribed: %s", clean)

    def unsubscribe(self, *symbols: str):
        clean = [s.upper() for s in symbols]
        self._symbols.difference_update(clean)
        self._stream.unsubscribe_bars(*self._wire(clean))
        logger.info("AlpacaStream unsubscribed: %s", clean)

    def run(self):
        """Blocking — runs the internal asyncio loop. Call from a daemon thread."""
        self._stream.run()

    def stop(self):
        self._stream.stop()
        logger.info("AlpacaStream stopped.")

    # ── internal ─────────────────────────────────────────────────────────────

    def _wire(self, symbols: list[str]) -> list[str]:
        return [to_alpaca_crypto(s) for s in symbols] if self._crypto else symbols

    async def _handle_bar(self, bar):
        """
        Fired by alpaca-py for every completed bar.
        Normalises to the shared candle dict and forwards to on_bar.
        """
        payload = {
            "symbol": from_alpaca_crypto(bar.symbol) if self._crypto else bar.symbol,
            "time":   int(bar.timestamp.timestamp()),
            "open":   round(float(bar.open),   4),
            "high":   round(float(bar.high),   4),
            "low":    round(float(bar.low),    4),
            "close":  round(float(bar.close),  4),
            # Crypto volume is fractional coins; int() would zero most 1m bars.
            "volume": round(float(bar.volume), 8) if self._crypto else int(bar.volume),
        }

        if asyncio.iscoroutinefunction(self._on_bar):
            await self._on_bar(payload)
        else:
            self._on_bar(payload)