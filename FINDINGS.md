# TradeView — Findings & Opportunities

A prioritized audit of the trading-dashboard codebase (backend + frontend + repo
hygiene), generated 2026-09-13. Every `file:line` citation below was read against
source, not inferred. RL-signal integration (`/api/signals`, `RLAgentMetrics.jsx`,
`ExitControls.jsx`) is catalogued but was explicitly kept out of scope for fixes here.

Roughly ranked by impact ÷ effort within each group; groups themselves are ordered
by how much they affect day-to-day use.

---

## A. Correctness bugs

These are outright wrong behavior, not missing polish.

1. **Removing one indicator can delete several others silently.**
   `frontend/src/components/IndicatorPanel.jsx:148,210` — `handleRemove(fn)` filters
   the active list by `fn` alone, but rows are rendered keyed by `${ind.fn}-${i}`
   (`:202`). Clicking ✕ on one EMA row removes *every* indicator with that `fn`. This
   directly breaks the `mburst` preset (EMA 9 + EMA 21, `backend/app.py:42`) — removing
   either EMA removes both.
   *Fix:* key removal by array index (or a generated id), not by `fn`.
   *Effort: small.*

2. **Changing an indicator or timeframe rebuilds the whole chart, losing zoom/pan.**
   `frontend/src/components/TradingChart.jsx:246` — `buildChart`'s `useEffect` depends
   on `[data, rlSignals]`, so any data refetch tears down and recreates every chart
   instance (`:237-244`) and calls `fitContent()` (`:224`), discarding the user's
   current view. This is the root cause of the "Chart Zoom Default" issue already
   logged in `WIRING_TODO.md`.
   *Fix:* preserve the visible logical range across rebuilds (read it before teardown,
   restore it after), or update existing series in place instead of destroying the
   chart.
   *Effort: medium.*

3. **Indicator colors change on every server restart.**
   `backend/indicators/engine.py:212-213` — `_auto_color` picks from `_COLOR_WHEEL`
   using `hash(key) % len(...)`, but Python randomizes string `hash()` per process
   (`PYTHONHASHSEED`) unless explicitly disabled. An EMA(20) line can be cyan on one
   run and orange on the next.
   *Fix:* use a deterministic hash (e.g. `zlib.crc32(key.encode())`) or a fixed
   name→color lookup table.
   *Effort: trivial.*

4. **A bad `limit` query param crashes the request instead of returning 400.**
   `backend/app.py:80` — `int(request.args.get("limit", 500))` runs *before* the
   `try/except` block (`:92-97`). `GET /api/chart/SPY?limit=abc` raises an uncaught
   `ValueError` → Flask 500, not the clean `{"error": ...}, 400` the rest of the route
   produces. There's also no upper bound — `?limit=999999999` is accepted and will
   attempt to serve however much history is fetched.
   *Fix:* parse and clamp `limit` inside the try block; cap it (e.g. 5000).
   *Effort: trivial.*

5. **Unknown indicator names fail silently.**
   `backend/app.py:53-64` — `_build_engine`'s `if/elif` chain has no final `else`. If
   `fn` doesn't match any branch, nothing happens and no error is recorded — the
   response comes back `200` with the series simply missing from `indicators[]`, and
   the client has no way to know why. Exceptions that *do* fire in a branch are only
   `print()`ed (`:66`), not surfaced in the response at all.
   *Fix:* add an `else: raise ValueError(f"Unknown indicator: {fn}")`, and collect
   per-indicator errors into the response (e.g. `{"warnings": [...]}`) rather than
   only logging server-side.
   *Effort: small.*

6. **Can't add a second EMA/SMA at a different period from the group list.**
   `frontend/src/components/IndicatorPanel.jsx:117` — `isActive(fn)` checks only the
   function name, ignoring `kwargs`. Once one EMA is active, the panel treats *all*
   EMAs as already-added regardless of length, blocking the add flow for a second one
   (you can still get there via a combo preset, just not the group list).
   *Fix:* compare `fn` + `kwargs` (the same comparison `isComboActive` already does at
   `:119-122`).
   *Effort: trivial.*

7. **Every `logger.*` call in the backend is invisible.**
   `backend/data/source.py` and `backend/ws/stream.py` both create module loggers via
   `logging.getLogger(__name__)`, but **no code anywhere calls
   `logging.basicConfig()`**. With no root handler configured, none of the stream
   reconnect diagnostics (`ws/stream.py:53,57-61,69`) or data-source logs ever reach
   stdout. `app.py` uses bare `print()` instead (`:66,170,178,191`) for its own
   messages, so the two logging paths are inconsistent and one is dead.
   *Fix:* one `logging.basicConfig(level=logging.INFO, format=...)` call near the top
   of `app.py`, and switch the `print()` calls to `logging` for consistency.
   *Effort: trivial, high value for debugging the WebSocket stream.*

---

## B. Missing features (ranked)

1. **No crosshair readout.** `TradingChart.jsx` never calls `chart.subscribeCrosshairMove`.
   Hovering the chart shows nothing — no OHLC at the cursor, no indicator values at
   that bar. The header (`App.jsx:72-94`) only ever shows the *last* candle. This is
   the single highest-value addition for a "trading dashboard" — it's table stakes for
   any charting tool and the library already supports it.

2. **No volume pane.** `volume` is present in every candle (`App.jsx:87-92` reads it
   for the header) but no histogram series is ever created in `TradingChart.jsx`.
   Volume is one of the most basic reads a trader wants and the data is already there.

3. **No persistence of view state.** Symbol, timeframe, active indicators, sidebar
   state — none of it survives a refresh, and none of it is in the URL. You can't
   bookmark or share a specific chart setup, and browser back/forward does nothing.
   A `localStorage` sync plus reflecting `symbol`/`timeframe`/`preset` into the query
   string would fix both at once.

4. **No reset-zoom / sane default zoom.** `fitContent()` (`TradingChart.jsx:224`)
   always fits all loaded bars (up to 600), so candles render as unreadably thin
   slivers on first load. Default to the most recent ~150 bars and add a "reset zoom"
   control — already flagged in `WIRING_TODO.md`.

5. **Watchlist and symbol search are static, non-editable duplicates.**
   `IndicatorPanel.jsx:5` (`WATCHLIST`) and `SymbolSearch.jsx:3` (`POPULAR`) hardcode
   the same 8 tickers in two places with no prices, no % change, and no way to
   add/remove/reorder. A real watchlist (even client-side only, backed by
   `localStorage`) with last price and day change would make the sidebar useful
   instead of decorative.

6. **The footer ticker tape does nothing.** `App.jsx:184-206` renders `SPY —` / `QQQ —`
   with a permanent em-dash — no price ever populates it. Either wire it to live quotes
   or remove it; right now it's UI that lies by omission.

7. **No chart-type switch, price-scale mode, or drawing tools.** Candlestick only, no
   line/area/Heikin-Ashi toggle, no log/percent price scale, no trendlines or
   annotations. Reasonable to defer, but worth having on the list since "trading
   dashboard" implies at least a couple of these eventually.

8. **No quote/snapshot endpoint on the backend.** There's no way to get current
   price/day-change for a symbol without pulling the full chart payload. This is what
   would actually power items 5 and 6 above, and would let `Toolbar.jsx` show real %
   change instead of just the raw last price.

9. **Backend endpoints exist but aren't used.** `/api/indicators` (`app.py:121-126`)
   and `/api/presets` (`app.py:100-102`) are both implemented and never called by the
   frontend — `IndicatorPanel.jsx:7-24` hardcodes its own indicator catalog and
   `Toolbar.jsx:13` hardcodes the preset list. Wiring the frontend to these endpoints
   would remove a second source of truth (and `/api/indicators` would need a params
   schema added to be actually useful for building a generic "add indicator" form).

10. **No keyboard shortcuts.** Not blocking, but cheap: a global focus-search shortcut
    (`/` or Ctrl+K) and arrow-key navigation in the `SymbolSearch` dropdown
    (`SymbolSearch.jsx` currently has neither) would meaningfully speed up symbol
    switching.

---

## C. Performance & robustness

1. **The yfinance path over-fetches by orders of magnitude.**
   `backend/data/source.py:61-75` always requests the *full period* for a timeframe
   (e.g. 5 years for daily bars, per `PERIOD_MAP_YF`) and then `.tail(limit)`s the
   result locally. A request for the last 100 daily bars downloads 5 years of history
   from Yahoo every single time, with no caching, so two users on the same symbol
   double the load. This is the highest-leverage backend fix: a simple TTL cache
   (in-memory dict keyed by `symbol/timeframe`, a few minutes' TTL) would cut Yahoo
   traffic dramatically and reduce rate-limit risk.

2. **`serialize()` does a manual Python double-loop over every cell.**
   `backend/indicators/engine.py:192-198` iterates every row × every column in pure
   Python to convert NaN → None. On the `full` preset (~25 columns × 600 rows) that's
   ~15,000 iterations per request. `df.where(pd.notnull(df), None)` or a vectorized
   approach would be materially faster and simpler.

3. **`squeeze_momentum` calls `np.polyfit` once per bar in a loop.**
   `backend/indicators/custom/momentum.py:72-82` — `linreg_series` is O(n) individual
   polyfits, the slowest computation in the codebase, for what is likely a rolling
   linear regression that could be vectorized.

4. **Live ticks never touch indicator overlays.**
   `TradingChart.jsx:254-260` updates only the candlestick series on each tick.
   EMA/RSI/MACD/etc. lines stay frozen at whatever they were on the last REST fetch
   until the next full refetch — so during live trading the overlays visibly lag
   the price action.

5. **WebSocket subscription has no refcounting and no disconnect cleanup.**
   `backend/app.py:164-179` joins/leaves rooms per socket event with no counting — if
   two clients are watching SPY and one unsubscribes, `unsubscribe("SPY")`
   (`ws/stream.py`) tears down the Alpaca feed for both. There's also no
   `@socketio.on("disconnect")` handler, so a client that just closes the tab leaves
   its subscription (and room membership) alive indefinitely.

6. **The stream gives up permanently after 5 reconnect failures with no signal.**
   `backend/ws/stream.py` backs off exponentially (2s→32s) across `MAX_RETRIES = 5`,
   then the thread exits silently. Nothing tells the frontend the live feed is dead —
   `useWebSocket.js` just shows `connected: false` forever, indistinguishable from
   "market closed." A `stream_status` socket event (or exposing status on
   `/api/health`) would let the UI say "live feed disconnected" instead of nothing.

7. **`/api/health` doesn't check anything.**
   `backend/app.py:72-74` returns `{"status": "ok"}` unconditionally — it never checks
   whether the data provider is reachable or whether the stream thread is alive. A
   fully broken backend still reports healthy.

---

## D. Security posture (local-dev context noted — still worth fixing before any
## non-local deployment)

1. `backend/app.py:192` — `debug=True` hardcoded, bound to `0.0.0.0`. In debug mode
   Flask's interactive Werkzeug debugger is reachable by anyone who can reach the port,
   which allows arbitrary code execution. `FLASK_ENV` exists in `.env.example` but is
   never read anywhere, so there's no way to flip this via environment today.
2. `backend/app.py:14-15` — `CORS(origins="*")` and `cors_allowed_origins="*"` accept
   requests from any origin. Fine for local dev; not fine if this is ever exposed.
3. `backend/app.py:146` — the `symbol` path parameter is interpolated directly into a
   filesystem path (`f"{symbol.lower()}_signals.json"`) with no sanitization before
   the `os.path.exists`/`open` calls. Constrained somewhat by the fixed suffix, but a
   crafted symbol (e.g. containing `../`) is worth explicitly rejecting rather than
   relying on the suffix alone.
4. `backend/Dockerfile` runs the Flask dev server as PID 1 in the container, with no
   `.dockerignore` — `COPY . .` will include the local `venv/` (hundreds of MB) if it
   exists in the build context.

---

## E. Dead code and accepted gaps (brief — not fixed in this pass)

- `/api/indicators` and `/api/presets` (list form) are implemented but have zero
  frontend callers (see B.9).
- `tailwind.config.js` defines `surface.0`–`surface.4` but `RLAgentMetrics.jsx`
  references `text-surface-5` in five places — renders as inherited/default color.
- Vestigial bindings with no effect: `useChartData.js:3` (`const BASE = ""`),
  `SymbolSearch.jsx:10,72` (`inputRef` never read), `TradingChart.jsx:231` (`el`
  destructured, unused), `TradingChart.jsx:126,206` (`seriesMap` populated for every
  indicator, only `__candles__` ever read back).
- `backend/requirements.txt` has `alpaca-py` and `python-dotenv` listed twice, once
  pinned once not.
- `.agents/skills/indicator-combo-builder/` and `.claude/skills/indicator-combo-builder/`
  are both tracked in git and currently byte-identical (3 files each) — guaranteed to
  drift apart the next time one is edited without the other.
- No automated tests, no linter (ESLint/ruff), no CI — confirmed absent repo-wide.
  Highest-value first tests if this gap is ever addressed: `engine.serialize()`'s
  timestamp conversion, `vwap_band`'s session-boundary reset, and `triple_ma`'s
  no-lookahead guarantee.

---

## RL-signal integration (catalogued, not addressed here — out of scope for this pass)

- `RLAgentMetrics.jsx:36-38` — the component returns `null` on any error, which also
  removes its own collapse/expand control; `loading` and `error` state are computed
  (`:10-11,21-27`) but never rendered.
- `ExitControls.jsx:70` — a failed fetch renders the raw string `404` to the user with
  no explanation.
- `backend/app.py:129-159` — `/api/signals/<symbol>` re-reads and re-parses the JSON
  file from disk on every request with no cache; `WIRING_TODO.md` already flags a
  5–15 min TTL as a known TODO.
