"""
Alpaca live-bar stream → Socket.IO "tick" events.

alpaca-py's StockDataStream.run() swallows connection/auth errors and retries
internally with no backoff, and returns normally on some fatal errors
("insufficient subscription"). So this module:

  * checks the API keys once up front (a bad key would otherwise spin forever),
  * treats *any* return from run() as a disconnect and backs off before retrying,
  * keeps a refcounted symbol registry and re-subscribes all of it on reconnect,
  * publishes a status string ("stream_status" event + get_status()).
"""
import os
import time
import threading
import logging

from data.source import AlpacaStream

logger = logging.getLogger(__name__)

PINNED_SYMBOLS   = ("SPY",)   # always streamed, never unsubscribed
MAX_SHORT_RUNS   = 8          # give up after this many consecutive short-lived runs
HEALTHY_RUN_SECS = 60         # a run lasting longer than this resets the backoff
MAX_BACKOFF_SECS = 60

_lock        = threading.Lock()
_refs: dict[str, int] = {}
_stream: AlpacaStream | None = None
_thread: threading.Thread | None = None
_stop_event  = threading.Event()
_socketio    = None
_status      = "disabled"


# ── status ────────────────────────────────────────────────────────────────────

def get_status() -> str:
    return _status


def _set_status(status: str):
    global _status
    if status == _status:
        return
    _status = status
    logger.info("Alpaca stream status → %s", status)
    if _socketio is not None:
        _socketio.emit("stream_status", {"status": status})


# ── key check ─────────────────────────────────────────────────────────────────

def _keys_rejected() -> bool:
    """True only when Alpaca explicitly rejects the keys (401/403).
    Network errors and unknown failures count as transient, not rejected."""
    try:
        from alpaca.common.exceptions import APIError
        from alpaca.data.enums import DataFeed
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestBarRequest

        client = StockHistoricalDataClient(
            api_key=os.getenv("ALPACA_API_KEY"),
            secret_key=os.getenv("ALPACA_SECRET_KEY"),
        )
        client.get_stock_latest_bar(StockLatestBarRequest(symbol_or_symbols="SPY", feed=DataFeed.IEX))
        return False
    except APIError as e:
        code = getattr(e, "status_code", None)
        if code in (401, 403):
            logger.error("Alpaca rejected the API keys (HTTP %s) — live stream disabled.", code)
            return True
        logger.warning("Alpaca key check inconclusive (%s) — starting stream anyway.", e)
        return False
    except Exception as e:
        logger.warning("Alpaca key check failed (%s) — starting stream anyway.", e)
        return False


# ── lifecycle ─────────────────────────────────────────────────────────────────

def init_stream(socketio, feed: str = "iex"):
    """
    Starts the Alpaca WebSocket stream in a daemon thread.
    Safe to call multiple times — only one stream runs at a time.
    """
    global _thread, _socketio
    _socketio = socketio

    api_key = os.getenv("ALPACA_API_KEY", "")
    if not api_key or api_key == "your_alpaca_key_here":
        logger.warning("Alpaca stream skipped — no API key set.")
        _set_status("disabled")
        return

    if _thread and _thread.is_alive():
        logger.info("Stream already running.")
        return

    with _lock:
        for sym in PINNED_SYMBOLS:
            _refs[sym] = max(_refs.get(sym, 0), 1)

    if _keys_rejected():
        _set_status("unauthorized")
        return

    _stop_event.clear()

    def on_bar(bar: dict):
        _set_status("live")
        socketio.emit("tick", bar, room=bar["symbol"])
        logger.debug("tick → %s @ %s", bar["symbol"], bar["time"])

    def _run():
        global _stream
        short_runs = 0

        while not _stop_event.is_set():
            _set_status("starting" if short_runs == 0 else "reconnecting")
            started = time.monotonic()
            try:
                # Always build a fresh stream object — reusing a crashed one
                # leaves the old TCP socket half-open and causes 429s.
                stream = AlpacaStream(on_bar=on_bar, feed=feed)
                with _lock:
                    symbols = [s for s, n in _refs.items() if n > 0]
                    stream.subscribe(*symbols)
                    _stream = stream
                logger.info("Alpaca stream connecting → %s", symbols)
                stream.run()        # blocks; returns on fatal errors or stop()
                logger.warning("Alpaca stream run() returned")
            except Exception as e:
                logger.error("Alpaca stream error: %s", e)
            finally:
                with _lock:
                    old, _stream = _stream, None
                try:
                    if old:
                        old.stop()
                except Exception:
                    pass

            if _stop_event.is_set():
                break

            if time.monotonic() - started > HEALTHY_RUN_SECS:
                short_runs = 0
            short_runs += 1
            if short_runs > MAX_SHORT_RUNS:
                logger.error("Alpaca stream failed %d times in a row — giving up.", MAX_SHORT_RUNS)
                _set_status("stopped")
                break

            wait = min(2 ** short_runs, MAX_BACKOFF_SECS)
            logger.info("Reconnecting Alpaca stream in %ds (attempt %d)", wait, short_runs)
            _set_status("reconnecting")
            _stop_event.wait(timeout=wait)   # interruptible sleep

    _thread = threading.Thread(target=_run, name="alpaca-ws", daemon=True)
    _thread.start()
    logger.info("Alpaca stream thread started (%s feed)", feed)


# ── refcounted subscriptions ──────────────────────────────────────────────────

def subscribe(symbol: str):
    symbol = symbol.upper()
    with _lock:
        _refs[symbol] = _refs.get(symbol, 0) + 1
        first = _refs[symbol] == 1
        stream = _stream
    if first and stream:
        try:
            stream.subscribe(symbol)
        except Exception as e:
            # The registry still has it; the next reconnect picks it up.
            logger.warning("Live subscribe(%s) failed: %s", symbol, e)


def unsubscribe(symbol: str):
    symbol = symbol.upper()
    with _lock:
        if _refs.get(symbol, 0) <= 0:
            return
        # Pinned symbols start at 1 in init_stream, so balanced
        # subscribe/unsubscribe pairs never take them to 0.
        _refs[symbol] -= 1
        last = _refs[symbol] == 0
        stream = _stream
    if last and stream:
        try:
            stream.unsubscribe(symbol)
        except Exception as e:
            logger.warning("Live unsubscribe(%s) failed: %s", symbol, e)


def stop():
    _stop_event.set()
    with _lock:
        stream = _stream
    if stream:
        stream.stop()
    _set_status("disabled")
