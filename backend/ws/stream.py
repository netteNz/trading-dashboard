"""
Alpaca live-bar streams → Socket.IO "tick" events.

Two channels run side by side: "stocks" (StockDataStream) and "crypto"
(CryptoDataStream, 24/7). A symbol is routed to its channel by markets.is_crypto.

alpaca-py's *DataStream.run() swallows connection/auth errors and retries
internally with no backoff, and returns normally on some fatal errors
("insufficient subscription"). So this module:

  * checks the API keys once up front (a bad key would otherwise spin forever),
  * treats *any* return from run() as a disconnect and backs off before retrying,
  * keeps a refcounted symbol registry per channel and re-subscribes all of it
    on reconnect,
  * publishes a status string per channel ("stream_status" event
    {"market", "status"} + get_status(market)).
"""
import os
import time
import threading
import logging

from data.source import AlpacaStream
from markets import market_of

logger = logging.getLogger(__name__)

MAX_SHORT_RUNS   = 8          # give up after this many consecutive short-lived runs
HEALTHY_RUN_SECS = 60         # a run lasting longer than this resets the backoff
MAX_BACKOFF_SECS = 60

_socketio = None


class _Channel:
    def __init__(self, market: str, kind: str, pinned: tuple[str, ...]):
        self.market  = market
        self.kind    = kind
        self.pinned  = pinned           # always streamed, never unsubscribed
        self.lock    = threading.Lock()
        self.refs: dict[str, int] = {}
        self.stream: AlpacaStream | None = None
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.status  = "disabled"

    # ── status ────────────────────────────────────────────────────────────────

    def set_status(self, status: str):
        if status == self.status:
            return
        self.status = status
        logger.info("Alpaca %s stream status → %s", self.market, status)
        if _socketio is not None:
            _socketio.emit("stream_status", {"market": self.market, "status": status})

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def start(self, socketio, feed: str):
        if self.thread and self.thread.is_alive():
            logger.info("%s stream already running.", self.market)
            return

        with self.lock:
            for sym in self.pinned:
                self.refs[sym] = max(self.refs.get(sym, 0), 1)

        self.stop_event.clear()

        def on_bar(bar: dict):
            self.set_status("live")
            socketio.emit("tick", bar, room=bar["symbol"])
            logger.debug("tick → %s @ %s", bar["symbol"], bar["time"])

        def _run():
            short_runs = 0

            while not self.stop_event.is_set():
                self.set_status("starting" if short_runs == 0 else "reconnecting")
                started = time.monotonic()
                try:
                    # Always build a fresh stream object — reusing a crashed one
                    # leaves the old TCP socket half-open and causes 429s.
                    stream = AlpacaStream(on_bar=on_bar, feed=feed, kind=self.kind)
                    with self.lock:
                        symbols = [s for s, n in self.refs.items() if n > 0]
                        stream.subscribe(*symbols)
                        self.stream = stream
                    logger.info("Alpaca %s stream connecting → %s", self.market, symbols)
                    stream.run()        # blocks; returns on fatal errors or stop()
                    logger.warning("Alpaca %s stream run() returned", self.market)
                except Exception as e:
                    logger.error("Alpaca %s stream error: %s", self.market, e)
                finally:
                    with self.lock:
                        old, self.stream = self.stream, None
                    try:
                        if old:
                            old.stop()
                    except Exception:
                        pass

                if self.stop_event.is_set():
                    break

                if time.monotonic() - started > HEALTHY_RUN_SECS:
                    short_runs = 0
                short_runs += 1
                if short_runs > MAX_SHORT_RUNS:
                    logger.error("Alpaca %s stream failed %d times in a row — giving up.",
                                 self.market, MAX_SHORT_RUNS)
                    self.set_status("stopped")
                    break

                wait = min(2 ** short_runs, MAX_BACKOFF_SECS)
                logger.info("Reconnecting Alpaca %s stream in %ds (attempt %d)", self.market, wait, short_runs)
                self.set_status("reconnecting")
                self.stop_event.wait(timeout=wait)   # interruptible sleep

        self.thread = threading.Thread(target=_run, name=f"alpaca-ws-{self.market}", daemon=True)
        self.thread.start()
        logger.info("Alpaca %s stream thread started", self.market)

    def stop(self):
        self.stop_event.set()
        with self.lock:
            stream = self.stream
        if stream:
            stream.stop()
        self.set_status("disabled")

    # ── refcounted subscriptions ──────────────────────────────────────────────

    def subscribe(self, symbol: str):
        with self.lock:
            self.refs[symbol] = self.refs.get(symbol, 0) + 1
            first = self.refs[symbol] == 1
            stream = self.stream
        if first and stream:
            try:
                stream.subscribe(symbol)
            except Exception as e:
                # The registry still has it; the next reconnect picks it up.
                logger.warning("Live subscribe(%s) failed: %s", symbol, e)

    def unsubscribe(self, symbol: str):
        with self.lock:
            if self.refs.get(symbol, 0) <= 0:
                return
            # Pinned symbols start at 1 in start(), so balanced
            # subscribe/unsubscribe pairs never take them to 0.
            self.refs[symbol] -= 1
            last = self.refs[symbol] == 0
            stream = self.stream
        if last and stream:
            try:
                stream.unsubscribe(symbol)
            except Exception as e:
                logger.warning("Live unsubscribe(%s) failed: %s", symbol, e)


CHANNELS = {
    "stocks": _Channel("stocks", "stock",  ("SPY",)),
    "crypto": _Channel("crypto", "crypto", ("BTC-USD",)),
}


# ── status ────────────────────────────────────────────────────────────────────

def get_status(market: str | None = None):
    """Status string for one market, or {market: status} for all of them."""
    if market is None:
        return {m: ch.status for m, ch in CHANNELS.items()}
    return CHANNELS[market].status


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
            logger.error("Alpaca rejected the API keys (HTTP %s) — live streams disabled.", code)
            return True
        logger.warning("Alpaca key check inconclusive (%s) — starting streams anyway.", e)
        return False
    except Exception as e:
        logger.warning("Alpaca key check failed (%s) — starting streams anyway.", e)
        return False


# ── lifecycle ─────────────────────────────────────────────────────────────────

def init_stream(socketio, feed: str = "iex"):
    """
    Starts both Alpaca streams (stocks + crypto) in daemon threads.
    Safe to call multiple times — only one stream per channel runs at a time.
    """
    global _socketio
    _socketio = socketio

    api_key = os.getenv("ALPACA_API_KEY", "")
    if not api_key or api_key == "your_alpaca_key_here":
        logger.warning("Alpaca streams skipped — no API key set.")
        for ch in CHANNELS.values():
            ch.set_status("disabled")
        return

    if all(ch.thread and ch.thread.is_alive() for ch in CHANNELS.values()):
        logger.info("Streams already running.")
        return

    # Same keys for both channels, so one check gates both.
    if _keys_rejected():
        for ch in CHANNELS.values():
            ch.set_status("unauthorized")
        return

    for ch in CHANNELS.values():
        ch.start(socketio, feed)


# ── refcounted subscriptions ──────────────────────────────────────────────────

def subscribe(symbol: str):
    symbol = symbol.upper()
    CHANNELS[market_of(symbol)].subscribe(symbol)


def unsubscribe(symbol: str):
    symbol = symbol.upper()
    CHANNELS[market_of(symbol)].unsubscribe(symbol)


def stop():
    for ch in CHANNELS.values():
        ch.stop()
