// Pure helpers for the candlestick chart (no React / chart-library imports,
// so they can be exercised directly with node).

// Bar length in seconds per toolbar timeframe.
export const TF_SECONDS = {
  "1Min":  60,
  "5Min":  5 * 60,
  "15Min": 15 * 60,
  "30Min": 30 * 60,
  "1Hour": 60 * 60,
  "1Day":  24 * 60 * 60,
  "1Week": 7 * 24 * 60 * 60,
};

/**
 * Fold a live 1-minute bar from the stream into the chart's current bar.
 *
 * Buckets are measured from the last bar's own timestamp rather than the
 * epoch, so they line up with however the data source anchors its bars
 * (yfinance hourly bars start at :30, daily bars at New York midnight).
 *
 * Returns the bar to pass to series.update(), or null to ignore the tick
 * (older than the current bar).
 */
export function mergeTick(current, tick, tfSeconds) {
  if (!current || !tick || tick.close == null || !tfSeconds) return null;
  if (tick.time < current.time) return null;

  if (tick.time < current.time + tfSeconds) {
    // 1-minute chart and the tick *is* the current (partial) bar: replace it
    // rather than adding its volume twice.
    if (tfSeconds === 60 && tick.time === current.time) {
      return { time: current.time, open: current.open, high: Math.max(current.high, tick.high),
               low: Math.min(current.low, tick.low), close: tick.close, volume: tick.volume };
    }
    return {
      time:   current.time,
      open:   current.open,
      high:   Math.max(current.high, tick.high),
      low:    Math.min(current.low, tick.low),
      close:  tick.close,
      volume: (current.volume ?? 0) + (tick.volume ?? 0),
    };
  }

  // A new bucket has started.
  const periods = Math.floor((tick.time - current.time) / tfSeconds);
  return {
    time:   current.time + periods * tfSeconds,
    open:   tick.open,
    high:   tick.high,
    low:    tick.low,
    close:  tick.close,
    volume: tick.volume ?? 0,
  };
}

/**
 * RL ensemble signals are one row per bar (action 1 = in position, 0 = flat).
 * Plotting every row buried the chart under thousands of arrows and showed
 * "hold" as a sell; only the *changes* are trades. Signals outside the loaded
 * candle range are dropped (the chart library would snap them onto the first
 * or last bar).
 */
export function rlTradeMarkers(signals, firstTime, lastTime) {
  if (!signals?.length || firstTime == null || lastTime == null) return [];
  const slack = 24 * 60 * 60;   // signal dates are UTC midnight; daily bars sit a few hours later
  const sorted = [...signals].sort((a, b) => a.date - b.date);
  const markers = [];
  let prev = 0;
  for (const s of sorted) {
    if (s.action !== prev && s.date >= firstTime - slack && s.date <= lastTime + slack) {
      const entry = s.action === 1;
      markers.push({
        time:     s.date,
        position: entry ? "belowBar" : "aboveBar",
        color:    entry ? "#3fb950" : "#f85149",
        shape:    entry ? "arrowUp" : "arrowDown",
        text:     entry ? `RL buy ${Math.round((s.confidence ?? 0) * 100)}%` : "RL exit",
      });
    }
    prev = s.action;
  }
  return markers;
}
