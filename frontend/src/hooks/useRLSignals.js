import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api";

/**
 * RL ensemble export for a symbol (/api/signals/<symbol>), fetched once per
 * symbol and shared by the metrics panel, the toolbar toggle and the chart.
 * data is null when the symbol has no export (404).
 */
export function useRLSignals(symbol) {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  useEffect(() => {
    if (!symbol) return;
    const ctrl = new AbortController();
    setLoading(true);
    setError(null);
    setData(null);

    apiFetch(`/api/signals/${symbol}`, { signal: ctrl.signal })
      .then(async res => {
        if (!res.ok) throw new Error(res.status === 404 ? "not found" : `HTTP ${res.status}`);
        setData(await res.json());
      })
      .catch(e => {
        if (e.name !== "AbortError") setError(e.message);
      })
      .finally(() => {
        // A newer request owns the loading flag once this one is aborted.
        if (!ctrl.signal.aborted) setLoading(false);
      });

    return () => ctrl.abort();
  }, [symbol]);

  return { data, loading, error };
}
