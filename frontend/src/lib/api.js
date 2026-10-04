// Same-origin fetch wrapper for the auth-gated backend.
//
// - Cookies (tv_access / tv_refresh) are httpOnly, so JS never sees the JWTs.
// - Non-GET requests echo the tv_csrf cookie in X-CSRF-Token (double-submit).
// - A 401 triggers one shared POST /auth/refresh, then the request is retried
//   once. If the refresh fails, the registered onUnauthorized handler runs
//   (AuthProvider switches to the login screen).

let refreshInFlight = null;
let onUnauthorized = () => {};

export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

export function csrfToken() {
  const m = document.cookie.match(/(?:^|;\s*)tv_csrf=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

function withAuth(opts = {}) {
  const method = (opts.method || "GET").toUpperCase();
  const headers = new Headers(opts.headers || {});
  if (method !== "GET" && method !== "HEAD") headers.set("X-CSRF-Token", csrfToken());
  return { ...opts, method, headers, credentials: "same-origin" };
}

// Resolves true when new tokens were issued. Concurrent callers share one request.
export function refreshSession() {
  if (!refreshInFlight) {
    refreshInFlight = fetch("/auth/refresh", withAuth({ method: "POST" }))
      .then(res => res.ok)
      .catch(() => false)
      .finally(() => { refreshInFlight = null; });
  }
  return refreshInFlight;
}

export async function apiFetch(url, opts = {}) {
  const res = await fetch(url, withAuth(opts));
  if (res.status !== 401) return res;

  if (await refreshSession()) {
    const retry = await fetch(url, withAuth(opts));
    if (retry.status !== 401) return retry;
  }
  onUnauthorized();
  return res;
}
