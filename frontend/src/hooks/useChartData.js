import { useState, useEffect, useCallback, useRef } from "react";

import { apiFetch } from "../lib/api";

const BASE = "";  // same origin: Vite proxy in dev, Flask in the container

export function useChartData(symbol, timeframe, indicators) {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);
  const abortRef = useRef(null);

  // Stringify for stable useCallback comparison (strings compare by value)
  const indicatorsJson = JSON.stringify(indicators ?? []);

  const fetch_ = useCallback(async () => {
    if (!symbol) return;

    if (abortRef.current) abortRef.current.abort();
    abortRef.current = new AbortController();

    setLoading(true);
    setError(null);

    try {
      const url = `${BASE}/api/chart/${symbol}?tf=${timeframe}&limit=600&indicators=${encodeURIComponent(indicatorsJson)}`;
      const res = await apiFetch(url, { signal: abortRef.current.signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      // Tag the payload with what it was fetched for, so the chart can tell an
      // indicator change (keep zoom) from a new symbol/timeframe (reset view).
      setData({ ...json, symbol, timeframe });
    } catch (e) {
      if (e.name !== "AbortError") setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [symbol, timeframe, indicatorsJson]);

  useEffect(() => { fetch_(); }, [fetch_]);

  return { data, loading, error, refetch: fetch_ };
}
