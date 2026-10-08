// Alpaca stream state (backend "stream_status"), not our own Socket.IO link.
export default function StreamBadge({ status }) {
  if (status === "live") {
    return (
      <span className="flex items-center gap-1 text-[10px] font-mono text-accent-green" title="Alpaca stream live">
        <span className="live-dot w-1.5 h-1.5 rounded-full bg-accent-green inline-block" />
        LIVE
      </span>
    );
  }
  if (status === "starting" || status === "reconnecting") {
    return (
      <span
        className="flex items-center gap-1 text-[10px] font-mono text-accent-yellow"
        title={`Alpaca stream ${status} (stays here outside market hours until the first bar)`}
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
