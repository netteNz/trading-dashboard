import { useEffect, useRef, useCallback } from "react";
import {
  createChart,
  CrosshairMode,
  LineStyle,
  PriceScaleMode,
  LineType,
} from "lightweight-charts";
import { mergeTick, rlTradeMarkers, TF_SECONDS } from "../lib/bars";

const CHART_THEME = {
  layout: {
    background: { color: "#0d1117" },
    textColor:  "#8b949e",
    fontSize:   11,
    fontFamily: "'JetBrains Mono', monospace",
  },
  grid: {
    vertLines: { color: "#161b22" },
    horzLines: { color: "#161b22" },
  },
  crosshair: {
    mode:      CrosshairMode.Normal,
    vertLine:  { color: "#30363d", labelBackgroundColor: "#21262d" },
    horzLine:  { color: "#30363d", labelBackgroundColor: "#21262d" },
  },
  timeScale: {
    borderColor:             "#21262d",
    timeVisible:             true,
    secondsVisible:          false,
    rightOffset:             10,
    fixLeftEdge:             false,
    lockVisibleTimeRangeOnResize: true,
  },
  // Same axis width on every stacked chart, otherwise a pane with wider labels
  // (e.g. volume) gets a narrower plot area and its bars drift out of line.
  rightPriceScale: { borderColor: "#21262d", mode: PriceScaleMode.Normal, minimumWidth: 80 },
};

const isVolumeKey = (key) => key === "volume" || key.startsWith("VOL_MA");

// Bars shown on first load of a symbol/timeframe (fitContent squeezed 600 bars
// into slivers).
const DEFAULT_VISIBLE_BARS = 150;

function lineStyleFromStr(s) {
  if (s === "dashed") return LineStyle.Dashed;
  if (s === "dotted") return LineStyle.Dotted;
  return LineStyle.Solid;
}

// One point per candle, using whitespace ({ time } only) where the indicator is
// still warming up. Every series then has the same bar indices as the candles,
// which keeps the stacked panes aligned when their logical ranges are synced.
function seriesData(candles, key) {
  return candles.map(d => (d[key] != null ? { time: d.time, value: d[key] } : { time: d.time }));
}

export default function TradingChart({ data, lastTick, rlSignals = [], timeframe, viewKey }) {
  const containerRef = useRef(null);
  const chartRef     = useRef(null);
  const seriesMap    = useRef({});
  const panesRef     = useRef({});   // pane index → { chart, el } (sub-charts)
  const liveBarRef   = useRef(null); // the bar live ticks are merged into
  const viewRef      = useRef({ key: null, range: null });

  const buildChart = useCallback(() => {
    if (!containerRef.current || !data) return;

    const { indicators } = data;
    const candles = data.candles.filter(d => d.time && d.open != null);

    // ── Main chart ──────────────────────────────────────────────────────────
    const totalH = containerRef.current.parentNode ? containerRef.current.parentNode.clientHeight : 500;
    const mainH = Math.round(totalH * 0.55);

    const chart = createChart(containerRef.current, {
      ...CHART_THEME,
      width:  containerRef.current.clientWidth,
      height: mainH,
    });
    chartRef.current = chart;

    const candleSeries = chart.addCandlestickSeries({
      upColor:          "#22c55e",
      downColor:        "#ef4444",
      borderUpColor:    "#22c55e",
      borderDownColor:  "#ef4444",
      wickUpColor:      "#22c55e",
      wickDownColor:    "#ef4444",
    });
    candleSeries.setData(candles.map(d => ({ time: d.time, open: d.open, high: d.high, low: d.low, close: d.close })));
    seriesMap.current["__candles__"] = candleSeries;

    const last = candles[candles.length - 1];
    liveBarRef.current = last
      ? { time: last.time, open: last.open, high: last.high, low: last.low, close: last.close, volume: last.volume }
      : null;

    // ── Pane 0 overlays (main chart) + markers ──────────────────────────────
    const markers = [];
    for (const ind of indicators.filter(i => i.pane === 0)) {
      if (ind.type === "scatter") {
        const buy = ind.key.includes("BUY");
        for (const d of candles) {
          if (d[ind.key] == null) continue;
          markers.push({
            time: d.time,
            position: buy ? "belowBar" : "aboveBar",
            color: ind.color,
            shape: buy ? "arrowUp" : "arrowDown",
            text: ind.label,
          });
        }
      } else {
        const series = chart.addLineSeries({
          color:     ind.color,
          lineWidth: 1.5,
          lineStyle: lineStyleFromStr(ind.lineStyle),
          lineType:  LineType.Curved,
          title:     ind.label,
          priceLineVisible: false,
          lastValueVisible: true,
        });
        series.setData(seriesData(candles, ind.key));
        seriesMap.current[ind.key] = series;
      }
    }

    // RL signals are daily decisions; on intraday/weekly charts they'd be
    // snapped onto the wrong bars, so they're only drawn on 1D.
    if (timeframe === "1Day" && candles.length) {
      markers.push(...rlTradeMarkers(rlSignals, candles[0].time, last.time));
    }
    if (markers.length) {
      markers.sort((a, b) => a.time - b.time);
      candleSeries.setMarkers(markers);
    }

    // ── Sub-pane charts (pane > 0), stacked in ascending pane order ─────────
    const subPaneIndices = [...new Set(indicators.filter(i => i.pane > 0).map(i => i.pane))]
      .sort((a, b) => a - b);
    const subH = subPaneIndices.length > 0
      ? Math.round((totalH - mainH) / subPaneIndices.length)
      : 0;

    const allCharts = [chart];
    let anchor = containerRef.current;
    for (const paneIdx of subPaneIndices) {
      const paneIndicators = indicators.filter(i => i.pane === paneIdx);

      const paneEl = document.createElement("div");
      paneEl.style.width     = "100%";
      paneEl.style.height    = `${subH}px`;
      paneEl.style.borderTop = "1px solid #161b22";
      anchor.parentNode.insertBefore(paneEl, anchor.nextSibling);
      anchor = paneEl;

      const subChart = createChart(paneEl, {
        ...CHART_THEME,
        width:  containerRef.current.clientWidth,
        height: subH,
        timeScale: { ...CHART_THEME.timeScale, visible: false },
      });
      panesRef.current[paneIdx] = { chart: subChart, el: paneEl };
      allCharts.push(subChart);

      for (const ind of paneIndicators) {
        // Volume reads as 46.3M instead of 46306400.00.
        const fmt = isVolumeKey(ind.key) ? { priceFormat: { type: "volume" } } : {};
        const series = ind.type === "histogram"
          ? subChart.addHistogramSeries({ color: ind.color, priceLineVisible: false, title: ind.label, ...fmt })
          : subChart.addLineSeries({
              color:            ind.color,
              lineWidth:        1.5,
              lineStyle:        lineStyleFromStr(ind.lineStyle),
              lineType:         LineType.Curved,
              priceLineVisible: false,
              title:            ind.label,
              ...fmt,
            });
        series.setData(seriesData(candles, ind.key));
        seriesMap.current[ind.key] = series;

        for (const level of ind.levels ?? []) {
          series.createPriceLine({
            price:      level.value,
            color:      level.color,
            lineWidth:  1,
            lineStyle:  LineStyle.Dotted,
            axisLabelVisible: true,
          });
        }
      }
    }

    // ── Keep every chart's visible range in sync ────────────────────────────
    let syncing = false;
    for (const source of allCharts) {
      source.timeScale().subscribeVisibleLogicalRangeChange(range => {
        if (!range || syncing) return;
        syncing = true;
        for (const target of allCharts) {
          if (target !== source) target.timeScale().setVisibleLogicalRange(range);
        }
        syncing = false;
        if (source === chart) viewRef.current.range = range;
      });
    }

    // Same symbol + timeframe (indicator or RL change): keep the user's zoom.
    // New symbol/timeframe: show the most recent bars.
    const saved = viewRef.current;
    if (saved.key === viewKey && saved.range) {
      chart.timeScale().setVisibleLogicalRange(saved.range);
    } else if (candles.length > DEFAULT_VISIBLE_BARS) {
      chart.timeScale().setVisibleLogicalRange({
        from: candles.length - DEFAULT_VISIBLE_BARS,
        to:   candles.length + CHART_THEME.timeScale.rightOffset,
      });
    } else {
      chart.timeScale().fitContent();
    }
    viewRef.current.key = viewKey;

    // Responsive resize
    const ro = new ResizeObserver(() => {
      if (!containerRef.current) return;
      const w = containerRef.current.clientWidth;
      for (const c of allCharts) c.applyOptions({ width: w });
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      for (const { chart: sub, el } of Object.values(panesRef.current)) {
        sub.remove();
        el.remove();
      }
      chart.remove();
      chartRef.current  = null;
      seriesMap.current = {};
      panesRef.current  = {};
    };
  }, [data, rlSignals, timeframe, viewKey]);

  useEffect(() => buildChart(), [buildChart]);

  // Live ticks are completed 1-minute bars. Fold them into the current bar of
  // whatever timeframe is shown (or start the next bar) instead of appending
  // each one as its own candle. Indicator lines update on the next refetch.
  useEffect(() => {
    const series = seriesMap.current["__candles__"];
    if (!lastTick || !series) return;
    const merged = mergeTick(liveBarRef.current, lastTick, TF_SECONDS[timeframe]);
    if (!merged) return;
    liveBarRef.current = merged;
    series.update({ time: merged.time, open: merged.open, high: merged.high, low: merged.low, close: merged.close });
  }, [lastTick, timeframe]);

  return (
    <div
      className="chart-enter"
      style={{ display: "flex", flexDirection: "column", width: "100%", height: "100%" }}
    >
      <div ref={containerRef} style={{ width: "100%" }} />
    </div>
  );
}
