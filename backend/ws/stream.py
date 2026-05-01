import os
import asyncio
import threading
import logging
from data.source import AlpacaStream

logger = logging.getLogger(__name__)

_stream: AlpacaStream | None = None
_thread: threading.Thread | None = None


def init_stream(socketio, symbol: str = "SPY", feed: str = "iex"):
    """
    Starts the Alpaca WebSocket stream in a daemon thread.
    Safe to call multiple times — only one stream runs at a time.
    Guards against missing / placeholder keys.
    """
    global _stream, _thread

    api_key = os.getenv("ALPACA_API_KEY", "")
    if not api_key or api_key == "your_alpaca_key_here":
        logger.warning("Alpaca stream skipped — no API key set.")
        return

    if _thread and _thread.is_alive():
        logger.info("Stream already running.")
        return

    def on_bar(bar: dict):
        """Sync callback — emits to all clients subscribed to that symbol room."""
        socketio.emit("tick", bar, room=bar["symbol"])
        logger.debug("tick → %s @ %s", bar["symbol"], bar["time"])

    _stream = AlpacaStream(on_bar=on_bar, feed=feed)
    _stream.subscribe(symbol)

    def _run():
        # StockDataStream.run() spins its own asyncio event loop internally
        try:
            _stream.run()
        except Exception as e:
            logger.error("Alpaca stream crashed: %s", e)

    _thread = threading.Thread(target=_run, name="alpaca-ws", daemon=True)
    _thread.start()
    logger.info("Alpaca stream started → %s (%s feed)", symbol, feed)


def subscribe(symbol: str):
    if _stream:
        _stream.subscribe(symbol)


def unsubscribe(symbol: str):
    if _stream:
        _stream.unsubscribe(symbol)


def stop():
    if _stream:
        _stream.stop()