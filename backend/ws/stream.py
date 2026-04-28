import os
import json
import threading
import websocket
from dotenv import load_dotenv

load_dotenv()

_ws_thread = None
_subscribed_symbols: set = set()
_socketio = None


def _build_auth_message() -> str:
    return json.dumps({
        "action": "auth",
        "key":    os.getenv("ALPACA_API_KEY", ""),
        "secret": os.getenv("ALPACA_SECRET_KEY", ""),
    })


def _build_subscribe_message(symbols: list) -> str:
    return json.dumps({"action": "subscribe", "trades": symbols})


def _on_message(ws, raw: str):
    global _socketio
    try:
        events = json.loads(raw)
        for event in events:
            if event.get("T") == "t":          # trade tick
                _socketio.emit("tick", {
                    "symbol": event["S"],
                    "price":  event["p"],
                    "volume": event["s"],
                    "time":   event["t"],
                })
            elif event.get("T") == "b":        # bar event
                _socketio.emit("bar", {
                    "symbol": event["S"],
                    "open":   event["o"],
                    "high":   event["h"],
                    "low":    event["l"],
                    "close":  event["c"],
                    "volume": event["v"],
                    "time":   event["t"],
                })
    except Exception as e:
        print(f"[WS] parse error: {e}")


def _on_open(ws):
    ws.send(_build_auth_message())
    if _subscribed_symbols:
        ws.send(_build_subscribe_message(list(_subscribed_symbols)))
    print("[WS] Alpaca stream connected")


def _on_error(ws, error):
    print(f"[WS] error: {error}")


def _on_close(ws, *args):
    print("[WS] stream closed")


def start_stream(socketio, symbols: list = None):
    """Start the Alpaca WebSocket stream in a background thread."""
    global _ws_thread, _socketio, _subscribed_symbols
    _socketio = socketio
    if symbols:
        _subscribed_symbols.update(s.upper() for s in symbols)

    if _ws_thread and _ws_thread.is_alive():
        return  # already running

    def run():
        ws = websocket.WebSocketApp(
            "wss://stream.data.alpaca.markets/v2/iex",
            on_open=_on_open,
            on_message=_on_message,
            on_error=_on_error,
            on_close=_on_close,
        )
        ws.run_forever(reconnect=5)

    _ws_thread = threading.Thread(target=run, daemon=True)
    _ws_thread.start()


def subscribe(symbol: str):
    """Dynamically subscribe to a new symbol (no-op if stream not started)."""
    _subscribed_symbols.add(symbol.upper())
