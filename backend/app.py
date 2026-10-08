import os
import json as _json
import logging
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_socketio import SocketIO, join_room, leave_room, emit, disconnect
from dotenv import load_dotenv

from auth import init_auth, socket_user
from data.source import DataSource
from markets import MARKETS, is_crypto
from indicators.engine import IndicatorEngine
from indicators.custom.vwap_band import ANCHORS as VWAP_ANCHORS
from indicators.custom.combo_signals import SIGNAL_RULES

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("app")

# Built React app (frontend/dist locally, /app/static in the container). Missing
# in plain local dev, where Vite serves the UI and proxies /api, /auth, /socket.io.
STATIC_DIR = os.path.abspath(os.getenv(
    "STATIC_DIR", os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")))

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")
if os.getenv("TRUST_PROXY") == "1":
    # Behind Azure Container Apps ingress: honour X-Forwarded-Proto/Host so
    # request.scheme/host_url reflect the public https URL.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# The UI is same-origin in production; these extra origins are for the Vite dev
# server, whose proxy forwards the browser's Origin header unchanged.
ALLOWED_ORIGINS = [o.strip() for o in os.getenv(
    "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip()]
if os.getenv("PUBLIC_URL"):
    ALLOWED_ORIGINS.append(os.getenv("PUBLIC_URL").rstrip("/"))

CORS(app, origins=ALLOWED_ORIGINS, supports_credentials=True)
socketio = SocketIO(app, cors_allowed_origins=ALLOWED_ORIGINS, async_mode="threading")
init_auth(app)

ds = DataSource()

MAX_LIMIT = 5000
# Extra bars fetched ahead of the displayed window so long indicators (SMA 200,
# EMA 55, regime) are warmed up from the first visible bar; trimmed before sending.
WARMUP_BARS = 250
# Scorecard: how many bars after a marker are measured.
HORIZON_BARS = 10
INTRADAY_TIMEFRAMES = {"1Min", "5Min", "15Min", "30Min", "1Hour"}

# ── Indicator registry ────────────────────────────────────────────────────────
# fn → (IndicatorEngine method, {kwarg: spec}). A spec is (int|float, min, max)
# or (str, allowed_values). Anything not listed here is rejected with a warning.

_PERIOD = (int, 1, 500)
INDICATORS = {
    "ema":    ("add_ema",    {"length": _PERIOD}),
    "sma":    ("add_sma",    {"length": _PERIOD}),
    "bbands": ("add_bbands", {"length": (int, 2, 500), "std": (float, 0.1, 10.0)}),
    "rsi":    ("add_rsi",    {"length": (int, 2, 500)}),
    "macd":   ("add_macd",   {"fast": _PERIOD, "slow": (int, 2, 500), "signal": _PERIOD}),
    "atr":    ("add_atr",    {"length": _PERIOD}),
    "stoch":  ("add_stoch",  {"k": _PERIOD, "d": _PERIOD, "smooth_k": _PERIOD}),
    "vwap":   ("add_vwap_band",           {"std_mult": (float, 0.1, 10.0), "period": _PERIOD,
                                           "anchor": (str, VWAP_ANCHORS)}),
    "mom":    ("add_momentum_oscillator", {"period": (int, 2, 500), "smooth": _PERIOD}),
    "sqz":    ("add_squeeze_momentum",    {}),
    "vol":    ("add_volume_profile",      {}),
    "tma":    ("add_triple_ma",           {"fast": _PERIOD, "mid": _PERIOD, "slow": _PERIOD}),
    "adx":    ("add_adx",     {"length": (int, 2, 500)}),
    "kc":     ("add_keltner", {"length": (int, 2, 500), "scalar": (float, 0.1, 10.0)}),
    "mfi":    ("add_mfi",     {"length": (int, 2, 500)}),
    "obv":    ("add_obv",     {"signal": _PERIOD}),
    "cmf":    ("add_cmf",     {"length": (int, 2, 500)}),
    "mrd":    ("add_market_regime", {}),
    "sig":    ("add_combo_signals", {"combo": (str, tuple(SIGNAL_RULES)),
                                     "anchor": (str, VWAP_ANCHORS)}),
}
STANDARD_INDICATORS = ["ema", "sma", "bbands", "rsi", "macd", "atr", "stoch"]

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

def _combo(key: str, *indicators: dict) -> list[dict]:
    """A combo preset: its indicators plus its BUY/SELL confluence markers."""
    return [*indicators, {"fn": "sig", "kwargs": {"combo": key}}]


def _i(fn: str, **kwargs) -> dict:
    return {"fn": fn, "kwargs": kwargs}


INDICATOR_PRESETS = {
    "trend":    [_i("ema", length=20), _i("ema", length=50), _i("bbands"), _i("vwap"),
                 _i("tma", fast=3, mid=7, slow=20)],
    "momentum": [_i("rsi"), _i("macd"), _i("mom")],
    "scalp":    [_i("ema", length=9), _i("ema", length=21), _i("rsi"), _i("stoch")],
    "full":     DEFAULT_INDICATORS,
    # ── Combo presets (signal rules: indicators/custom/combo_signals.py) ─────────
    "ttp":    _combo("ttp", _i("ema", length=9), _i("ema", length=21), _i("ema", length=55), _i("rsi")),
    "tsf":    _combo("tsf", _i("ema", length=20), _i("ema", length=50), _i("adx"), _i("macd")),
    "ksqz":   _combo("ksqz", _i("bbands"), _i("kc"), _i("sqz")),
    "bbrsi":  _combo("bbrsi", _i("bbands"), _i("rsi"), _i("vol")),
    "osc":    _combo("osc", _i("rsi"), _i("mfi"), _i("bbands")),
    "tmt":    _combo("tmt", _i("sma", length=50), _i("sma", length=100), _i("sma", length=200),
                     _i("macd"), _i("rsi")),
    "wvs":    _combo("wvs", _i("obv"), _i("cmf"), _i("sqz")),
    "vrb":    _combo("vrb", _i("vwap"), _i("stoch"), _i("atr")),
    "mburst": _combo("mburst", _i("ema", length=9), _i("ema", length=21), _i("sqz"), _i("vol")),
    "vcs":    _combo("vcs", _i("rsi", length=7), _i("vwap"), _i("atr")),
    "regime": [_i("mrd"), _i("adx"), _i("atr")],
    # ── Crypto combos (24/7: UTC-day VWAP, trend-pullback RSI) ──────────────────
    "bmsb":   _combo("bmsb", _i("sma", length=20), _i("ema", length=21), _i("atr")),
    "cpb":    _combo("cpb", _i("ema", length=21), _i("ema", length=55), _i("rsi"), _i("atr")),
    "uvb":    _combo("uvb", _i("vwap"), _i("adx"), _i("atr")),
    # ── Both markets ────────────────────────────────────────────────────────────
    "rdiv":   _combo("rdiv", _i("rsi"), _i("atr")),
}

# Display info for every preset — the one place the UI gets labels from.
# "markets" picks which market toggle(s) list it. Volume-spike combos stay
# stocks-only: single-venue crypto volume (Alpaca) is too thin to trust.
_BOTH, _STOCKS, _CRYPTO = ["stocks", "crypto"], ["stocks"], ["crypto"]
PRESET_INFO = {
    "trend":    {"kind": "core", "markets": _BOTH,  "label": "Trend",    "desc": "EMA 20/50, BB, VWAP, Triple MA", "tf": "any"},
    "momentum": {"kind": "core", "markets": _BOTH,  "label": "Momentum", "desc": "RSI, MACD, Mom Osc",             "tf": "any"},
    "scalp":    {"kind": "core", "markets": _BOTH,  "label": "Scalp",    "desc": "EMA 9/21, RSI, Stoch",           "tf": "1m–15m"},
    "full":     {"kind": "core", "markets": _BOTH,  "label": "Full",     "desc": "Default overview",               "tf": "any"},
    "ttp":    {"kind": "combo", "markets": _BOTH, "label": "Triple Trend Pulse",    "tf": "1H, 1D",
               "desc": "Stacked EMA 9/21/55 + RSI 50 cross"},
    "tsf":    {"kind": "combo", "markets": _BOTH, "label": "Trend Strength Filter", "tf": "1D",
               "desc": "EMA 20/50 trend, ADX > 25, MACD flip"},
    "ksqz":   {"kind": "combo", "markets": _BOTH, "label": "Keltner Squeeze",       "tf": "15m, 1H",
               "desc": "BB inside KC, breakout on release"},
    "bbrsi":  {"kind": "combo", "markets": _STOCKS, "label": "BB-RSI Reversal",       "tf": "1H, 1D",
               "desc": "Band tag + RSI extreme + volume spike"},
    "osc":    {"kind": "combo", "markets": _STOCKS, "label": "Oversold Confluence",   "tf": "1D",
               "desc": "RSI, MFI and BB all at extremes"},
    "tmt":    {"kind": "combo", "markets": _STOCKS, "label": "Triple MA Trend",       "tf": "1D",
               "desc": "SMA 50/100/200 stack + MACD + RSI band"},
    "wvs":    {"kind": "combo", "markets": _STOCKS, "label": "Wyckoff Volume",        "tf": "1D",
               "desc": "CMF zero cross confirmed by OBV"},
    "vrb":    {"kind": "combo", "markets": _BOTH, "label": "VWAP Rubber Band",      "tf": "5m, 15m",
               "desc": "Mean reversion from VWAP bands"},
    "mburst": {"kind": "combo", "markets": _STOCKS, "label": "Momentum Burst",        "tf": "1m, 5m",
               "desc": "EMA ribbon + squeeze flip + volume"},
    "vcs":    {"kind": "combo", "markets": _BOTH, "label": "VWAP Cross Scalp",      "tf": "1m, 5m",
               "desc": "VWAP cross with RSI 7 momentum"},
    "regime": {"kind": "combo", "markets": _BOTH, "label": "Market Regime",         "tf": "1D",
               "desc": "Trend / range / high-vol context"},
    "bmsb":   {"kind": "combo", "markets": _CRYPTO, "label": "Bull Market Support Band", "tf": "1W, 1D",
               "desc": "Close reclaims / loses the SMA 20 + EMA 21 band"},
    "cpb":    {"kind": "combo", "markets": _CRYPTO, "label": "Crypto Trend Pullback",    "tf": "1H, 1D",
               "desc": "EMA 21/55 trend, RSI reclaims 40 (loses 60)"},
    "uvb":    {"kind": "combo", "markets": _CRYPTO, "label": "UTC VWAP Breakout",        "tf": "5m, 15m",
               "desc": "Break of the UTC-day VWAP band, ADX > 20, ATR rising"},
    "rdiv":   {"kind": "combo", "markets": _BOTH, "label": "RSI Divergence",           "tf": "1H, 1D",
               "desc": "Lower low + higher RSI low (and mirror), confirmed 3 bars after the swing"},
}


def _coerce(fn: str, name: str, value, spec):
    """Validate one kwarg against its spec. Returns the coerced value or raises ValueError."""
    kind = spec[0]
    if kind is str:
        if value not in spec[1]:
            raise ValueError(f"{fn}: {name} must be one of {list(spec[1])}")
        return value
    lo, hi = spec[1], spec[2]
    if isinstance(value, bool):
        raise ValueError(f"{fn}: {name} must be a number")
    try:
        num = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{fn}: {name} must be a number")
    if kind is int:
        if not num.is_integer():
            raise ValueError(f"{fn}: {name} must be a whole number")
        num = int(num)
    if not lo <= num <= hi:
        raise ValueError(f"{fn}: {name} must be between {lo} and {hi}")
    return num


def _build_engine(df, indicator_list: list, timeframe: str = "1Day",
                  symbol: str = "") -> tuple[IndicatorEngine, list[str]]:
    engine = IndicatorEngine(df)
    warnings: list[str] = []
    seen: set[tuple[str, str]] = set()

    for item in indicator_list:
        if not isinstance(item, dict):
            warnings.append(f"ignored malformed indicator entry: {item!r}")
            continue
        fn = item.get("fn", "")
        raw_kw = item.get("kwargs") or {}
        if fn not in INDICATORS:
            warnings.append(f"unknown indicator: {fn!r}")
            continue
        if not isinstance(raw_kw, dict):
            warnings.append(f"{fn}: kwargs must be an object")
            continue

        method, schema = INDICATORS[fn]
        kw = {}
        try:
            for name, value in raw_kw.items():
                if name not in schema:
                    warnings.append(f"{fn}: ignored unknown parameter {name!r}")
                    continue
                kw[name] = _coerce(fn, name, value, schema[name])
        except ValueError as e:
            warnings.append(str(e))
            continue

        # Session-anchored VWAP is meaningless on daily/weekly bars (one bar
        # per session), so default to a rolling VWAP there. 24/7 crypto has no
        # US session: its intraday VWAP resets at the UTC daily open.
        if fn in ("vwap", "sig") and "anchor" not in kw:
            if timeframe not in INTRADAY_TIMEFRAMES:
                kw["anchor"] = "rolling"
            else:
                kw["anchor"] = "utc" if symbol and is_crypto(symbol) else "session"

        dedupe_key = (fn, _json.dumps(kw, sort_keys=True))
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        try:
            getattr(engine, method)(**kw)
        except Exception as e:
            log.warning("indicator %s%s failed: %s", fn, kw, e)
            warnings.append(f"{fn}: {e}")

    return engine, warnings


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/api/health")
def health():
    from ws.stream import get_status
    return jsonify({"status": "ok", "provider": ds.provider, "stream": get_status()})


@app.route("/api/chart/<symbol>")
def get_chart(symbol: str):
    timeframe = request.args.get("tf", "1Day")
    preset    = request.args.get("preset", "full")

    try:
        limit = int(request.args.get("limit", 500))
    except ValueError:
        return jsonify({"error": "limit must be an integer"}), 400
    limit = max(1, min(limit, MAX_LIMIT))

    warnings: list[str] = []
    raw_indicators = request.args.get("indicators")
    indicator_list = INDICATOR_PRESETS.get(preset, DEFAULT_INDICATORS)
    if raw_indicators:
        try:
            parsed = _json.loads(raw_indicators)
            if not isinstance(parsed, list):
                raise ValueError("indicators must be a JSON array")
            indicator_list = parsed
        except ValueError as e:
            warnings.append(f"bad indicators param ({e}); using preset {preset!r}")

    try:
        df = ds.get_bars(symbol, timeframe, limit=limit + WARMUP_BARS)
        engine, build_warnings = _build_engine(df, indicator_list, timeframe, symbol)
        # Scored before trimming: it needs the bars after each marker and a warm ATR.
        stats = engine.signal_stats(horizon=HORIZON_BARS, last=limit)
        payload = engine.tail(limit).serialize()
        payload["stats"] = stats
        payload["warnings"] = warnings + build_warnings
        return jsonify(payload)
    except Exception as e:
        log.warning("chart %s %s failed: %s", symbol, timeframe, e)
        return jsonify({"error": str(e)}), 400


@app.route("/api/markets")
def get_markets():
    return jsonify(MARKETS)


@app.route("/api/presets")
def get_presets():
    order = sorted(INDICATOR_PRESETS, key=lambda n: PRESET_INFO[n]["kind"] != "core")
    return jsonify([{"name": n, **PRESET_INFO[n], "indicators": INDICATOR_PRESETS[n]} for n in order])


@app.route("/api/presets/<name>")
def get_preset(name: str):
    indicators = INDICATOR_PRESETS.get(name)
    if indicators is None:
        return jsonify({"error": f"Unknown preset: {name}"}), 404
    return jsonify(indicators)


@app.route("/api/search")
def search():
    q = request.args.get("q", "")
    if not q:
        return jsonify([])
    return jsonify(ds.search_symbols(q))


@app.route("/api/indicators")
def list_indicators():
    def _spec_json(spec):
        if spec[0] is str:
            return {"type": "choice", "values": list(spec[1])}
        return {"type": spec[0].__name__, "min": spec[1], "max": spec[2]}

    return jsonify({
        "standard": STANDARD_INDICATORS,
        "custom":   [fn for fn in INDICATORS if fn not in STANDARD_INDICATORS],
        "params":   {fn: {k: _spec_json(s) for k, s in schema.items()}
                     for fn, (_, schema) in INDICATORS.items()},
    })


@app.route("/api/signals/<symbol>")
def get_rl_signals(symbol: str):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Candidate directories in priority order: env override, then both known
    # relative-sibling paths (macOS agentic-dev and Windows agentic-development)
    env_override = os.getenv("RL_SIGNALS_DIR")
    candidates = []
    if env_override:
        candidates.append(env_override if os.path.isabs(env_override) else os.path.join(root, env_override))
    candidates += [
        os.path.join(root, "../../agentic-dev/reinforcement-learning-stocks/data/dashboard_signals"),
        os.path.join(root, "../../agentic-development/reinforcement-learning-stocks/data/dashboard_signals"),
    ]

    file_path = None
    for d in candidates:
        p = os.path.normpath(os.path.join(d, f"{symbol.lower()}_signals.json"))
        if os.path.exists(p):
            file_path = p
            break

    if file_path is None:
        checked = [os.path.normpath(os.path.join(d, f"{symbol.lower()}_signals.json")) for d in candidates]
        return jsonify({"error": f"Signals not found for {symbol}", "checked_paths": checked}), 404

    try:
        with open(file_path, "r") as f:
            return jsonify(_json.load(f))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── SocketIO events ───────────────────────────────────────────────────────────

# Symbols each connected client has subscribed to, so a closed tab releases
# its Alpaca subscriptions (ws.stream refcounts across clients).
_sid_symbols: dict[str, set[str]] = {}


@socketio.on("connect")
def handle_connect(auth=None):
    # Cookies ride along with the Socket.IO handshake (same origin).
    if socket_user() is None:
        raise ConnectionRefusedError("unauthorized")


@socketio.on("subscribe")
def handle_subscribe(data):
    from ws.stream import subscribe, get_status
    # The access token is short-lived but a socket can stay open for hours:
    # re-check on every subscribe and make the client refresh + reconnect.
    if socket_user() is None:
        emit("auth_expired")
        disconnect()
        return
    # Tell this client the Alpaca stream state now; later changes are broadcast.
    # (The client subscribes right after connecting, so this covers new sockets.)
    for market in MARKETS:
        emit("stream_status", {"market": market, "status": get_status(market)})
    symbol = (data or {}).get("symbol", "SPY").upper()
    symbols = _sid_symbols.setdefault(request.sid, set())
    if symbol in symbols:
        return
    symbols.add(symbol)
    join_room(symbol)
    subscribe(symbol)
    log.info("[ws] %s subscribed to %s", request.sid, symbol)


@socketio.on("unsubscribe")
def handle_unsubscribe(data):
    from ws.stream import unsubscribe
    symbol = (data or {}).get("symbol", "SPY").upper()
    symbols = _sid_symbols.get(request.sid, set())
    if symbol not in symbols:
        return
    symbols.discard(symbol)
    leave_room(symbol)
    unsubscribe(symbol)
    log.info("[ws] %s unsubscribed from %s", request.sid, symbol)


@socketio.on("disconnect")
def handle_disconnect(*_args):
    from ws.stream import unsubscribe
    for symbol in _sid_symbols.pop(request.sid, set()):
        unsubscribe(symbol)


# ── SPA ───────────────────────────────────────────────────────────────────────

@app.route("/")
def spa_index():
    if not os.path.exists(os.path.join(STATIC_DIR, "index.html")):
        return jsonify({"error": "frontend not built — use the Vite dev server on :3000"}), 404
    return send_from_directory(STATIC_DIR, "index.html")


@app.errorhandler(404)
def spa_fallback(err):
    # Client-side routes (and the post-login redirect with ?auth_error=) get the
    # SPA shell; API/auth misses stay JSON 404s.
    path = request.path
    if (request.method == "GET" and not path.startswith(("/api/", "/auth/", "/socket.io"))
            and os.path.exists(os.path.join(STATIC_DIR, "index.html"))):
        return send_from_directory(STATIC_DIR, "index.html")
    return jsonify({"error": "not found"}), 404


# ── Entry point ───────────────────────────────────────────────────────────────

_background_started = False


def start_background():
    """Start the Alpaca live stream once per process (no-op without API keys)."""
    global _background_started
    if _background_started:
        return
    _background_started = True
    from ws.stream import init_stream
    init_stream(socketio, feed=os.getenv("ALPACA_FEED", "iex"))


# Under gunicorn (the container) the module is imported, not run: ENABLE_STREAM=1
# is set in the Dockerfile. Tests and other importers don't start the stream.
if os.getenv("ENABLE_STREAM") == "1":
    start_background()


if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", 5000))
    host = os.getenv("FLASK_HOST", "127.0.0.1")

    if os.getenv("ENABLE_STREAM", "1") != "0":
        start_background()

    log.info("starting on %s:%d — provider=%s", host, port, ds.provider)
    socketio.run(app, host=host, port=port, debug=os.getenv("FLASK_DEBUG") == "1",
                 use_reloader=False, allow_unsafe_werkzeug=True)
