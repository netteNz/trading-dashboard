import { useState, useEffect, useCallback, useRef } from "react";

const BASE = "";  // Vite proxy handles /api → localhost:5000

export function useChartData(symbol, timeframe, preset = "full") {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);
  const abortRef = useRef(null);

  const fetch_ = useCallback(async () => {
    if (!symbol) return;

    // Abort any in-flight request
    if (abortRef.current) abortRef.current.abort();
    abortRef.current = new AbortController();

    setLoading(true);
    setError(null);

    try {
      const url = `${BASE}/api/chart/${symbol}?tf=${timeframe}&preset=${preset}&limit=600`;
      const res = await fetch(url, { signal: abortRef.current.signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
    } catch (e) {
      if (e.name !== "AbortError") setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [symbol, timeframe, preset]);

  useEffect(() => { fetch_(); }, [fetch_]);

  return { data, loading, error, refetch: fetch_ };
}
