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
// An optional colorMap ({ "<value>": "#hex" }) colours each histogram bar by
// its value (the market regime uses it).
function seriesData(candles, key, colorMap) {
  return candles.map(d => {
    const v = d[key];
    if (v == null) return { time: d.time };
    const color = colorMap?.[String(v)];
    return color ? { time: d.time, value: v, color } : { time: d.time, value: v };
  });
}

// ── Sub-pane layout (resize + hide), persisted per pane number ──────────────
// Heights are weights: visible panes share the space in proportion to them.
// Pane numbers are fixed per indicator type (RSI → 1, MACD → 2, …), so a
// layout carries over between symbols, timeframes and presets.

const LAYOUT_KEY    = "tv.paneLayout";
const MIN_PANE_H    = 48;   // px, for any visible pane
const HIDDEN_PANE_H = 20;   // px, the collapsed strip with label + eye
const MAIN_SHARE    = 0.55; // main chart's default share of the height

function loadLayout() {
  try {
    const raw = JSON.parse(localStorage.getItem(LAYOUT_KEY));
    if (raw && typeof raw === "object") return { weights: raw.weights ?? {}, hidden: raw.hidden ?? {} };
  } catch { /* storage blocked or bad JSON */ }
  return { weights: {}, hidden: {} };
}

function saveLayout(layout) {
  try { localStorage.setItem(LAYOUT_KEY, JSON.stringify(layout)); } catch { /* storage blocked */ }
}

const EYE_SVG = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>`;
const EYE_OFF_SVG = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 19c-6.5 0-10-7-10-7a18.5 18.5 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c6.5 0 10 7 10 7a18.5 18.5 0 0 1-2.16 3.19"/><path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/><line x1="2" y1="2" x2="22" y2="22"/></svg>`;

export default function TradingChart({ data, lastTick, rlSignals = [], showSignals = true, timeframe, viewKey }) {
  const containerRef = useRef(null);
  const chartRef     = useRef(null);
  const seriesMap    = useRef({});
  const panesRef     = useRef({});   // pane index → { chart, el } (sub-charts)
  const liveBarRef   = useRef(null); // the bar live ticks are merged into
  const viewRef      = useRef({ key: null, range: null });
  const layoutRef    = useRef(null);
  if (layoutRef.current === null) layoutRef.current = loadLayout();

  const buildChart = useCallback(() => {
    if (!containerRef.current || !data) return;

    const { indicators } = data;
    const candles = data.candles.filter(d => d.time && d.open != null);

    // ── Main chart ──────────────────────────────────────────────────────────
    const frame  = containerRef.current.parentNode;
    const totalH = () => (frame?.clientHeight || 500);
    const mainH  = Math.round(totalH() * MAIN_SHARE);   // provisional; applyLayout() sets the real one

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
        if (!showSignals) continue;
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
    const layout = layoutRef.current;
    // Main first, then sub-panes top to bottom.
    const panes = [{ id: "main", chart }];
    const weightOf = (p) => layout.weights[p.id]
      ?? (p.id === "main" ? Math.max(1, subPaneIndices.length) * MAIN_SHARE / (1 - MAIN_SHARE) : 1);
    const isHidden = (p) => p.id !== "main" && !!layout.hidden[p.id];
    const availH = () => {
      const subs = panes.slice(1);
      return totalH() - subs.length /* borders */ - subs.filter(isHidden).length * HIDDEN_PANE_H;
    };

    // Size every pane from the weights; no chart rebuild, so zoom is untouched.
    const applyLayout = () => {
      const visible = panes.filter(p => !isHidden(p));
      const avail   = Math.max(availH(), visible.length * MIN_PANE_H);
      const wSum    = visible.reduce((a, p) => a + weightOf(p), 0);
      const width   = containerRef.current?.clientWidth ?? 0;
      for (const p of panes) {
        if (isHidden(p)) {
          p.wrap.style.height = `${HIDDEN_PANE_H}px`;
          p.chartEl.style.display = "none";
          continue;
        }
        const h = Math.max(MIN_PANE_H, Math.floor(avail * weightOf(p) / wSum));
        if (p.wrap) {
          p.wrap.style.height = `${h}px`;
          p.chartEl.style.display = "block";
        }
        p.chart.applyOptions({ width, height: h });
      }
      for (const p of panes.slice(1)) {
        const hidden = isHidden(p);
        p.eye.innerHTML        = hidden ? EYE_OFF_SVG : EYE_SVG;
        p.eye.title            = hidden ? "Show pane" : "Hide pane";
        p.label.style.color    = hidden ? "#6e7681" : "#8b949e";
        p.handle.style.display = hidden ? "none" : "block";
      }
    };

    // Drag a pane's top edge: trade height with the nearest visible pane above.
    const startResize = (pane, e) => {
      e.preventDefault();
      const idx   = panes.indexOf(pane);
      const above = panes.slice(0, idx).reverse().find(p => !isHidden(p));
      if (!above) return;
      const visible = panes.filter(p => !isHidden(p));
      const pxPerW  = availH() / visible.reduce((a, p) => a + weightOf(p), 0);
      const minW    = MIN_PANE_H / pxPerW;
      const y0 = e.clientY, wa = weightOf(above), wb = weightOf(pane);
      const handle = e.currentTarget;
      handle.setPointerCapture(e.pointerId);

      const onMove = (ev) => {
        let dw = (ev.clientY - y0) / pxPerW;            // drag down: the pane above grows
        dw = Math.min(dw, wb - minW);
        dw = Math.max(dw, minW - wa);
        layout.weights[above.id] = wa + dw;
        layout.weights[pane.id]  = wb - dw;
        applyLayout();
      };
      const onUp = () => {
        handle.removeEventListener("pointermove", onMove);
        handle.removeEventListener("pointerup", onUp);
        handle.removeEventListener("pointercancel", onUp);
        saveLayout(layout);
      };
      handle.addEventListener("pointermove", onMove);
      handle.addEventListener("pointerup", onUp);
      handle.addEventListener("pointercancel", onUp);
    };

    const allCharts = [chart];
    let anchor = containerRef.current;
    for (const paneIdx of subPaneIndices) {
      const paneIndicators = indicators.filter(i => i.pane === paneIdx);

      const wrap = document.createElement("div");
      wrap.style.cssText = "position:relative;width:100%;border-top:1px solid #161b22;background:#0d1117";
      anchor.parentNode.insertBefore(wrap, anchor.nextSibling);
      anchor = wrap;

      const paneEl = document.createElement("div");
      paneEl.style.width = "100%";
      wrap.appendChild(paneEl);

      // Drag handle straddling the top border.
      const handle = document.createElement("div");
      handle.title = "Drag to resize";
      handle.style.cssText = "position:absolute;left:0;right:0;top:-4px;height:8px;cursor:row-resize;z-index:4";
      handle.addEventListener("pointerenter", () => { wrap.style.borderTopColor = "#38bdf8"; });
      handle.addEventListener("pointerleave", () => { wrap.style.borderTopColor = "#161b22"; });

      // Eye toggle + pane label, top-left.
      const header = document.createElement("div");
      header.style.cssText = "position:absolute;left:6px;top:3px;z-index:3;display:flex;align-items:center;gap:6px;"
        + "font:10px 'JetBrains Mono',monospace;pointer-events:none";
      const eye = document.createElement("button");
      eye.type = "button";
      eye.style.cssText = "pointer-events:auto;display:flex;align-items:center;padding:1px 3px;border-radius:3px;"
        + "color:#8b949e;background:rgba(13,17,23,0.8);border:1px solid #21262d;cursor:pointer";
      const label = document.createElement("span");
      label.textContent = [...new Set(paneIndicators.map(i => i.label))].join(" · ");
      header.append(eye, label);
      wrap.append(handle, header);

      const subChart = createChart(paneEl, {
        ...CHART_THEME,
        width:  containerRef.current.clientWidth,
        height: MIN_PANE_H,
        timeScale: { ...CHART_THEME.timeScale, visible: false },
      });
      const pane = { id: String(paneIdx), chart: subChart, wrap, chartEl: paneEl, eye, label, handle };
      panes.push(pane);
      handle.addEventListener("pointerdown", (e) => startResize(pane, e));
      eye.addEventListener("click", () => {
        if (layout.hidden[pane.id]) delete layout.hidden[pane.id];
        else layout.hidden[pane.id] = true;
        applyLayout();
        saveLayout(layout);
      });

      panesRef.current[paneIdx] = { chart: subChart, el: wrap };
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
        series.setData(seriesData(candles, ind.key, ind.type === "histogram" ? ind.colorMap : undefined));
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

    applyLayout();

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
    // Width and height: the frame fills the chart area.
    const ro = new ResizeObserver(() => {
      if (containerRef.current) applyLayout();
    });
    ro.observe(frame ?? containerRef.current);

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
  }, [data, rlSignals, showSignals, timeframe, viewKey]);

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
