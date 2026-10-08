import math
import os
import asyncio
import logging
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

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


def yf_lookback(timeframe: str, limit: int) -> timedelta:
    """How far back to fetch so roughly `limit` bars come back, not years more.

    Trading days → calendar days (5 of 7, plus ~10% and a week of slack for
    holidays and half days), capped at Yahoo's limit for the interval.
    """
    if timeframe == "1Week":
        days = limit * 7 + 14
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


# ── Historical data ────────────────────────────────────────────────────────────

class DataSource:
    def __init__(self, provider: str = None):
        self.provider = provider or os.getenv("DATA_PROVIDER", "yfinance")
        self._alpaca = None

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

    def get_bars(self, symbol: str, timeframe: str = "1Day", limit: int = 500) -> pd.DataFrame:
        symbol = symbol.upper()
        if self.provider == "alpaca":
            return self._get_bars_alpaca(symbol, timeframe, limit)
        return self._get_bars_yfinance(symbol, timeframe, limit)

    def _get_bars_yfinance(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        yf_interval = TIMEFRAME_MAP_YF.get(timeframe, "1d")
        # Only as much history as `limit` needs (a fixed 5y for daily bars made
        # every chart load download ~2.5x the data it kept).
        start = datetime.now(timezone.utc) - yf_lookback(timeframe, limit)

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
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

        tf_map = {
            "1Min":  TimeFrame(1,  TimeFrameUnit.Minute),
            "5Min":  TimeFrame(5,  TimeFrameUnit.Minute),
            "15Min": TimeFrame(15, TimeFrameUnit.Minute),
            "30Min": TimeFrame(30, TimeFrameUnit.Minute),
            "1Hour": TimeFrame(1,  TimeFrameUnit.Hour),
            "1Day":  TimeFrame(1,  TimeFrameUnit.Day),
            "1Week": TimeFrame(1,  TimeFrameUnit.Week),
        }

        client = self._get_alpaca()
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=tf_map.get(timeframe, TimeFrame(1, TimeFrameUnit.Day)),
            start=datetime.now(timezone.utc) - LOOKBACK_ALPACA.get(timeframe, timedelta(days=365 * 6)),
            limit=limit,
            # Newest first: with the default ascending sort, `limit` keeps the
            # *oldest* bars after `start`, and intraday charts showed stale data.
            sort=Sort.DESC,
            feed=DataFeed.SIP if os.getenv("ALPACA_FEED", "iex").lower() == "sip" else DataFeed.IEX,
        )
        bars = client.get_stock_bars(request).df
        # An empty response has a plain RangeIndex with no "timestamp" level.
        if bars.empty:
            raise ValueError(f"No data returned for {symbol}")
        bars.index = bars.index.get_level_values("timestamp")
        bars.index = pd.to_datetime(bars.index, utc=True)
        bars = bars[["open", "high", "low", "close", "volume"]].dropna().sort_index()
        return bars.tail(limit)

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
    Wraps alpaca-py StockDataStream and emits normalised bar dicts to a callback.

    Bar dict shape (matches /api/chart candle contract):
        {
            "symbol": "SPY",
            "time":   1704067200,   # unix seconds (int)
            "open":   476.32,
            "high":   478.91,
            "low":    475.10,
            "close":  477.85,
            "volume": 82341200,
        }

    Usage:
        stream = AlpacaStream(on_bar=my_callback, feed="iex")
        stream.subscribe("SPY", "QQQ")
        stream.run()          # blocking — call from a daemon thread
    """
    
    def __init__(self, on_bar, feed: str = "iex"):
        from alpaca.data.live import StockDataStream
        from alpaca.data.enums import DataFeed

        feed_enum = DataFeed.IEX if feed.lower() == "iex" else DataFeed.SIP

        self._on_bar  = on_bar
        self._feed    = feed
        self._symbols: set[str] = set()
        self._stream  = StockDataStream(
            api_key=os.environ["ALPACA_API_KEY"],
            secret_key=os.environ["ALPACA_SECRET_KEY"],
            feed=feed_enum,
        )

    # ── public ────────────────────────────────────────────────────────────────

    def subscribe(self, *symbols: str):
        """Register one or more symbols for bar updates."""
        clean = [s.upper() for s in symbols]
        self._symbols.update(clean)
        self._stream.subscribe_bars(self._handle_bar, *clean)
        logger.info("AlpacaStream subscribed: %s", clean)

    def unsubscribe(self, *symbols: str):
        clean = [s.upper() for s in symbols]
        self._symbols.difference_update(clean)
        self._stream.unsubscribe_bars(*clean)
        logger.info("AlpacaStream unsubscribed: %s", clean)

    def run(self):
        """Blocking — runs the internal asyncio loop. Call from a daemon thread."""
        self._stream.run()

    def stop(self):
        self._stream.stop()
        logger.info("AlpacaStream stopped.")

    # ── internal ─────────────────────────────────────────────────────────────

    async def _handle_bar(self, bar):
        """
        Fired by alpaca-py for every completed bar.
        Normalises to the shared candle dict and forwards to on_bar.
        """
        payload = {
            "symbol": bar.symbol,
            "time":   int(bar.timestamp.timestamp()),
            "open":   round(float(bar.open),   4),
            "high":   round(float(bar.high),   4),
            "low":    round(float(bar.low),    4),
            "close":  round(float(bar.close),  4),
            "volume": int(bar.volume),
        }

        if asyncio.iscoroutinefunction(self._on_bar):
            await self._on_bar(payload)
        else:
            self._on_bar(payload)