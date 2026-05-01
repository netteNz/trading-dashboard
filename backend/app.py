import os
import json as _json
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, join_room, leave_room
from dotenv import load_dotenv

from data.source import DataSource
from indicators.engine import IndicatorEngine

load_dotenv()

app      = Flask(__name__)
CORS(app, origins="*")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

ds = DataSource()

# ── Indicator presets ─────────────────────────────────────────────────────────

DEFAULT_INDICATORS = [
    {"fn": "ema",    "kwargs": {"length": 20}},
    {"fn": "ema",    "kwargs": {"length": 50}},
    {"fn": "bbands", "kwargs": {}},
    {"fn": "rsi",    "kwargs": {}},
    {"fn": "macd",   "kwargs": {}},
    {"fn": "vwap",   "kwargs": {}},
    {"fn": "mom",    "kwargs": {}},
    {"fn": "vol",    "kwargs": {}},
]

INDICATOR_PRESETS = {
    "trend":    [{"fn": "ema", "kwargs": {"length": 20}}, {"fn": "ema", "kwargs": {"length": 50}},
                 {"fn": "bbands", "kwargs": {}}, {"fn": "vwap", "kwargs": {}},
                 {"fn": "tma", "kwargs": {"fast": 3, "mid": 7, "slow": 20}}],
    "momentum": [{"fn": "rsi", "kwargs": {}}, {"fn": "macd", "kwargs": {}}, {"fn": "mom", "kwargs": {}}],
    "scalp":    [{"fn": "ema", "kwargs": {"length": 9}}, {"fn": "ema", "kwargs": {"length": 21}},
                 {"fn": "rsi", "kwargs": {}}, {"fn": "stoch", "kwargs": {}}],
    "full":     DEFAULT_INDICATORS,
    # ── Combo presets ──────────────────────────────────────────────────────────
    "vrb":    [{"fn": "vwap",  "kwargs": {}},              {"fn": "stoch", "kwargs": {}},           {"fn": "atr", "kwargs": {}}],
    "mburst": [{"fn": "ema",   "kwargs": {"length": 9}},   {"fn": "ema",   "kwargs": {"length": 21}}, {"fn": "sqz", "kwargs": {}}],
    "vcs":    [{"fn": "rsi",   "kwargs": {"length": 7}},   {"fn": "vwap",  "kwargs": {}},           {"fn": "atr", "kwargs": {}}],
}


def _build_engine(df, indicator_list: list) -> IndicatorEngine:
    engine = IndicatorEngine(df)
    for item in indicator_list:
        fn = item.get("fn", "")
        kw = item.get("kwargs", {})
        try:
            if   fn == "ema":    engine.add_ema(**kw)
            elif fn == "sma":    engine.add_sma(**kw)
            elif fn == "bbands": engine.add_bbands(**kw)
            elif fn == "rsi":    engine.add_rsi(**kw)
            elif fn == "macd":   engine.add_macd(**kw)
            elif fn == "atr":    engine.add_atr(**kw)
            elif fn == "stoch":  engine.add_stoch(**kw)
            elif fn == "vwap":   engine.add_vwap_band(**kw)
            elif fn == "mom":    engine.add_momentum_oscillator(**kw)
            elif fn == "sqz":    engine.add_squeeze_momentum()
            elif fn == "vol":    engine.add_volume_profile()
            elif fn == "tma":    engine.add_triple_ma(**kw)
        except Exception as e:
            print(f"[engine] skipping {fn}: {e}")
    return engine


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "provider": ds.provider})


@app.route("/api/chart/<symbol>")
def get_chart(symbol: str):
    timeframe = request.args.get("tf", "1Day")
    limit     = int(request.args.get("limit", 500))
    preset    = request.args.get("preset", "full")

    raw_indicators = request.args.get("indicators")
    if raw_indicators:
        try:
            indicator_list = _json.loads(raw_indicators)
        except Exception:
            indicator_list = INDICATOR_PRESETS.get(preset, DEFAULT_INDICATORS)
    else:
        indicator_list = INDICATOR_PRESETS.get(preset, DEFAULT_INDICATORS)

    try:
        df     = ds.get_bars(symbol, timeframe, limit=limit)
        engine = _build_engine(df, indicator_list)
        return jsonify(engine.serialize())
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/presets")
def get_presets():
    return jsonify(list(INDICATOR_PRESETS.keys()))


@app.route("/api/search")
def search():
    q = request.args.get("q", "")
    if not q:
        return jsonify([])
    return jsonify(ds.search_symbols(q))


@app.route("/api/indicators")
def list_indicators():
    return jsonify({
        "standard": ["ema", "sma", "bbands", "rsi", "macd", "atr", "stoch"],
        "custom":   ["vwap", "mom", "sqz", "vol", "tma"],
    })


# ── SocketIO events ───────────────────────────────────────────────────────────

@socketio.on("subscribe")
def handle_subscribe(data):
    from ws.stream import subscribe
    symbol = data.get("symbol", "SPY").upper()
    join_room(symbol)
    subscribe(symbol)
    print(f"[ws] subscribed to {symbol}")


@socketio.on("unsubscribe")
def handle_unsubscribe(data):
    from ws.stream import unsubscribe
    symbol = data.get("symbol", "SPY").upper()
    leave_room(symbol)
    unsubscribe(symbol)
    print(f"[ws] unsubscribed from {symbol}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", 5000))

    if os.getenv("ALPACA_API_KEY") and os.getenv("ALPACA_API_KEY") != "your_alpaca_key_here":
        from ws.stream import init_stream
        init_stream(socketio, symbol="SPY", feed="iex")

    print(f"[app] starting on port {port} — provider={ds.provider}")
    socketio.run(app, host="0.0.0.0", port=port, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)
