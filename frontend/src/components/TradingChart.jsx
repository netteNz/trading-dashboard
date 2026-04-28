import { useEffect, useRef, useCallback } from "react";
import {
  createChart,
  CrosshairMode,
  LineStyle,
  PriceScaleMode,
} from "lightweight-charts";

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
  rightPriceScale: { borderColor: "#21262d", mode: PriceScaleMode.Normal },
};

function lineStyleFromStr(s) {
  if (s === "dashed") return LineStyle.Dashed;
  if (s === "dotted") return LineStyle.Dotted;
  return LineStyle.Solid;
}

export default function TradingChart({ data, lastTick }) {
  const containerRef = useRef(null);
  const chartRef     = useRef(null);
  const seriesMap    = useRef({});
  const panesRef     = useRef({});   // pane index → pane chart (sub-charts)

  const buildChart = useCallback(() => {
    if (!containerRef.current || !data) return;

    // Destroy previous
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
      seriesMap.current = {};
      panesRef.current  = {};
    }

    const { candles, indicators } = data;

    // ── Main chart ──────────────────────────────────────────────────────────
    const mainH = Math.round(containerRef.current.clientHeight * 0.55);

    const chart = createChart(containerRef.current, {
      ...CHART_THEME,
      width:  containerRef.current.clientWidth,
      height: mainH,
    });
    chartRef.current = chart;

    // Candlestick series
    const candleSeries = chart.addCandlestickSeries({
      upColor:          "#22c55e",
      downColor:        "#ef4444",
      borderUpColor:    "#22c55e",
      borderDownColor:  "#ef4444",
      wickUpColor:      "#22c55e",
      wickDownColor:    "#ef4444",
    });

    const candleData = candles
      .filter(d => d.time && d.open != null)
      .map(d => ({ time: d.time, open: d.open, high: d.high, low: d.low, close: d.close }));
    candleSeries.setData(candleData);
    seriesMap.current["__candles__"] = candleSeries;

    // ── Pane 0 overlays (main chart) ────────────────────────────────────────
    const pane0Indicators = indicators.filter(ind => ind.pane === 0);
    for (const ind of pane0Indicators) {
      const series = chart.addLineSeries({
        color:     ind.color,
        lineWidth: 1,
        lineStyle: lineStyleFromStr(ind.lineStyle),
        title:     ind.label,
        priceLineVisible: false,
        lastValueVisible: true,
      });
      const seriesData = candles
        .filter(d => d[ind.key] != null)
        .map(d => ({ time: d.time, value: d[ind.key] }));
      series.setData(seriesData);
      seriesMap.current[ind.key] = series;
    }

    // ── Sub-pane charts (pane > 0) ──────────────────────────────────────────
    const subPaneIndices = [...new Set(indicators.filter(i => i.pane > 0).map(i => i.pane))].sort();
    const subH = subPaneIndices.length > 0
      ? Math.round((containerRef.current.clientHeight - mainH) / subPaneIndices.length)
      : 0;

    for (const paneIdx of subPaneIndices) {
      const paneIndicators = indicators.filter(i => i.pane === paneIdx);
      if (!paneIndicators.length) continue;

      const paneEl = document.createElement("div");
      paneEl.style.width       = "100%";
      paneEl.style.height      = `${subH}px`;
      paneEl.style.borderTop   = "1px solid #161b22";
      containerRef.current.parentNode.insertBefore(paneEl, containerRef.current.nextSibling);

      const subChart = createChart(paneEl, {
        ...CHART_THEME,
        width:  containerRef.current.clientWidth,
        height: subH,
        timeScale: { ...CHART_THEME.timeScale, visible: false },
      });
      panesRef.current[paneIdx] = { chart: subChart, el: paneEl };

      // Sync time scales
      chart.timeScale().subscribeVisibleLogicalRangeChange(range => {
        if (range) subChart.timeScale().setVisibleLogicalRange(range);
      });
      subChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
        if (range) chart.timeScale().setVisibleLogicalRange(range);
      });

      for (const ind of paneIndicators) {
        let series;
        if (ind.type === "histogram") {
          series = subChart.addHistogramSeries({
            color:            ind.color,
            priceLineVisible: false,
            title:            ind.label,
          });
        } else {
          series = subChart.addLineSeries({
            color:            ind.color,
            lineWidth:        1,
            lineStyle:        lineStyleFromStr(ind.lineStyle),
            priceLineVisible: false,
            title:            ind.label,
          });
        }

        const seriesData = candles
          .filter(d => d[ind.key] != null)
          .map(d => ({ time: d.time, value: d[ind.key] }));
        series.setData(seriesData);
        seriesMap.current[ind.key] = series;

        // Level lines (e.g. RSI 70/30)
        if (ind.levels) {
          for (const level of ind.levels) {
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
    }

    // Fit content
    chart.timeScale().fitContent();

    // Responsive resize
    const ro = new ResizeObserver(() => {
      if (!containerRef.current) return;
      const w = containerRef.current.clientWidth;
      chart.applyOptions({ width: w });
      for (const { chart: sub, el } of Object.values(panesRef.current)) {
        sub.applyOptions({ width: w });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      for (const { chart: sub, el } of Object.values(panesRef.current)) {
        sub.remove();
        el.remove();
      }
      chart.remove();
    };
  }, [data]);

  useEffect(() => {
    const cleanup = buildChart();
    return () => { if (cleanup) cleanup(); };
  }, [buildChart]);

  // Live tick update
  useEffect(() => {
    if (!lastTick || !seriesMap.current["__candles__"]) return;
    // Update the last candle close with the live tick price
    // (Lightweight Charts v4: updateData on a single bar)
  }, [lastTick]);

  return (
    <div
      className="chart-enter"
      style={{ display: "flex", flexDirection: "column", width: "100%", height: "100%" }}
    >
      <div ref={containerRef} style={{ width: "100%" }} />
    </div>
  );
}
