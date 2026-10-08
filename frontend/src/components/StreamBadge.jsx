import { useEffect, useState } from "react";

// US equities regular session, 09:30–16:00 America/New_York, Mon–Fri.
// Exchange holidays aren't modelled: on those days the badge shows CONNECTING.
function isRegularSession(now = new Date()) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-US", {
      timeZone: "America/New_York", weekday: "short", hour: "numeric", minute: "numeric", hourCycle: "h23",
    }).formatToParts(now).map(p => [p.type, p.value]),
  );
  if (parts.weekday === "Sat" || parts.weekday === "Sun") return false;
  const minutes = Number(parts.hour) * 60 + Number(parts.minute);
  return minutes >= 9 * 60 + 30 && minutes < 16 * 60;
}

// Re-evaluated every minute so the badge flips at the open/close on its own.
function useMarketOpen() {
  const [open, setOpen] = useState(isRegularSession);
  useEffect(() => {
    const id = setInterval(() => setOpen(isRegularSession()), 60_000);
    return () => clearInterval(id);
  }, []);
  return open;
}

// Alpaca stream state (backend "stream_status"), not our own Socket.IO link.
// Crypto trades 24/7, so it is never MARKET CLOSED.
export default function StreamBadge({ status, market = "stocks" }) {
  const sessionOpen = useMarketOpen();
  const marketOpen = market === "crypto" || sessionOpen;

  if (status === "live") {
    return (
      <span className="flex items-center gap-1 text-[10px] font-mono text-accent-green" title="Alpaca stream live">
        <span className="live-dot w-1.5 h-1.5 rounded-full bg-accent-green inline-block" />
        LIVE
      </span>
    );
  }
  // "starting" only turns "live" on the first bar, and bars only flow in the
  // regular session — outside it the stream is connected but idle.
  if (status === "starting" && !marketOpen) {
    return (
      <span
        className="flex items-center gap-1 text-[10px] font-mono text-[#8b949e]"
        title="Alpaca stream connected — no bars until the 09:30 ET open"
      >
        <span className="w-1.5 h-1.5 rounded-full border border-[#8b949e] inline-block" />
        MARKET CLOSED
      </span>
    );
  }
  if (status === "starting" || status === "reconnecting") {
    return (
      <span
        className="flex items-center gap-1 text-[10px] font-mono text-accent-yellow"
        title={`Alpaca stream ${status}`}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-accent-yellow inline-block" />
        CONNECTING
      </span>
    );
  }
  return (
    <span className="text-[10px] font-mono text-surface-4" title={`Alpaca stream: ${status ?? "not connected"}`}>
      DELAYED
    </span>
  );
}
