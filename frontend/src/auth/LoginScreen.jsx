const ERRORS = {
  not_allowed: "This GitHub account isn't on the allow-list for this dashboard.",
  denied:      "GitHub sign-in was cancelled.",
  github:      "GitHub sign-in failed. Please try again.",
};

function GitHubMark() {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" fill="currentColor">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38
        0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52
        -.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89
        -3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27
        2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82
        2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013
        8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}

export default function LoginScreen() {
  const errorKey = new URLSearchParams(window.location.search).get("auth_error");
  const error = errorKey ? (ERRORS[errorKey] || "Sign-in failed.") : null;

  return (
    <div
      className="h-screen flex items-center justify-center bg-surface-0 px-4"
      style={{ fontFamily: "'JetBrains Mono', monospace" }}
    >
      <div className="w-full max-w-sm bg-surface-1 border border-surface-3 rounded-lg p-6 shadow-xl">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-accent-cyan text-lg font-bold tracking-tighter">⬡ TRADEVIEW</span>
          <span className="text-[10px] text-surface-4 uppercase tracking-widest">Personal</span>
        </div>
        <p className="text-[11px] text-surface-4 mb-6">Sign in to open the dashboard.</p>

        {error && (
          <p className="text-[11px] text-accent-red bg-accent-red/10 border border-accent-red/30 rounded px-3 py-2 mb-4">
            {error}
          </p>
        )}

        <a
          href="/auth/login"
          className="flex items-center justify-center gap-2 w-full bg-white text-surface-0 text-[12px] font-bold
                     rounded py-2 hover:opacity-90 transition-opacity"
        >
          <GitHubMark />
          Sign in with GitHub
        </a>

        <p className="text-[10px] text-surface-4 mt-4 leading-relaxed">
          Access is limited to allow-listed GitHub accounts. Your session lasts up to 7 days.
        </p>
      </div>
    </div>
  );
}
