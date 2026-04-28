import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

TIMEFRAME_MAP_YF = {
    "1Min":  "1m",
    "5Min":  "5m",
    "15Min": "15m",
    "30Min": "30m",
    "1Hour": "1h",
    "1Day":  "1d",
    "1Week": "1wk",
}

PERIOD_MAP_YF = {
    "1Min":  "7d",
    "5Min":  "60d",
    "15Min": "60d",
    "30Min": "60d",
    "1Hour": "730d",
    "1Day":  "5y",
    "1Week": "10y",
}


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
        else:
            return self._get_bars_yfinance(symbol, timeframe, limit)

    def _get_bars_yfinance(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        yf_interval = TIMEFRAME_MAP_YF.get(timeframe, "1d")
        yf_period   = PERIOD_MAP_YF.get(timeframe, "5y")

        ticker = yf.Ticker(symbol)
        df = ticker.history(period=yf_period, interval=yf_interval)

        if df.empty:
            raise ValueError(f"No data returned for {symbol}")

        df.index = pd.to_datetime(df.index, utc=True)
        df.index.name = "timestamp"
        df.columns = [c.lower() for c in df.columns]
        df = df[["open", "high", "low", "close", "volume"]].dropna()
        return df.tail(limit)

    def _get_bars_alpaca(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

        tf_map = {
            "1Min":  TimeFrame(1,  TimeFrameUnit.Minute),
            "5Min":  TimeFrame(5,  TimeFrameUnit.Minute),
            "15Min": TimeFrame(15, TimeFrameUnit.Minute),
            "30Min": TimeFrame(30, TimeFrameUnit.Minute),
            "1Hour": TimeFrame(1,  TimeFrameUnit.Hour),
            "1Day":  TimeFrame(1,  TimeFrameUnit.Day),
        }

        client = self._get_alpaca()
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=tf_map.get(timeframe, TimeFrame(1, TimeFrameUnit.Day)),
            start=datetime.utcnow() - timedelta(days=365 * 2),
            limit=limit,
        )
        bars = client.get_stock_bars(request).df
        bars.index = bars.index.get_level_values("timestamp")
        bars.index = pd.to_datetime(bars.index, utc=True)
        bars = bars[["open", "high", "low", "close", "volume"]].dropna()
        return bars.tail(limit)

    def search_symbols(self, query: str) -> list:
        """Basic symbol lookup via yfinance"""
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
