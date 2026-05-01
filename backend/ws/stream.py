import os
import time
import threading
import logging
from data.source import AlpacaStream

logger = logging.getLogger(__name__)

_stream: AlpacaStream | None = None
_thread: threading.Thread | None = None
_stop_event = threading.Event()

MAX_RETRIES    = 5
BACKOFF_BASE   = 2   # seconds — doubles each retry: 2, 4, 8, 16, 32


def init_stream(socketio, symbol: str = "SPY", feed: str = "iex"):
    """
    Starts the Alpaca WebSocket stream in a daemon thread.
    Safe to call multiple times — only one stream runs at a time.
    Guards against missing / placeholder keys.
    """
    global _stream, _thread, _stop_event

    api_key = os.getenv("ALPACA_API_KEY", "")
    if not api_key or api_key == "your_alpaca_key_here":
        logger.warning("Alpaca stream skipped — no API key set.")
        return

    if _thread and _thread.is_alive():
        logger.info("Stream already running.")
        return

    _stop_event.clear()

    def on_bar(bar: dict):
        socketio.emit("tick", bar, room=bar["symbol"])
        logger.debug("tick → %s @ %s", bar["symbol"], bar["time"])

    def _run():
        global _stream
        retries = 0

        while not _stop_event.is_set() and retries < MAX_RETRIES:
            try:
                # Always build a fresh stream object — reusing a crashed one
                # leaves the old TCP socket half-open and causes 429s.
                _stream = AlpacaStream(on_bar=on_bar, feed=feed)
                _stream.subscribe(symbol)
                logger.info("Alpaca stream connected (attempt %d)", retries + 1)
                retries = 0          # reset on clean connect
                _stream.run()        # blocks until disconnect/error

            except Exception as e:
                retries += 1
                wait = BACKOFF_BASE ** retries
                logger.error(
                    "Alpaca stream error (attempt %d/%d): %s — retrying in %ds",
                    retries, MAX_RETRIES, e, wait,
                )
                # Ensure the old socket is torn down before we reconnect
                try:
                    if _stream:
                        _stream.stop()
                except Exception:
                    pass
                _stream = None

                if retries >= MAX_RETRIES:
                    logger.error("Max retries reached — stream stopped.")
                    break

                _stop_event.wait(timeout=wait)   # interruptible sleep

    _thread = threading.Thread(target=_run, name="alpaca-ws", daemon=True)
    _thread.start()
    logger.info("Alpaca stream thread started → %s (%s feed)", symbol, feed)


def subscribe(symbol: str):
    if _stream:
        _stream.subscribe(symbol)


def unsubscribe(symbol: str):
    if _stream:
        _stream.unsubscribe(symbol)


def stop():
    _stop_event.set()
    if _stream:
        _stream.stop()