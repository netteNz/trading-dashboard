import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { apiFetch, refreshSession, setUnauthorizedHandler } from "../lib/api";
import { closeSocket } from "../hooks/useWebSocket";
import LoginScreen from "./LoginScreen";

const AuthContext = createContext(null);

export function useAuth() {
  return useContext(AuthContext);
}

async function fetchMe() {
  const res = await fetch("/auth/me", { credentials: "same-origin" });
  return res.ok ? res.json() : null;
}

// Renders <LoginScreen> until /auth/me succeeds; children (the dashboard) only
// mount once signed in, so no API or socket traffic happens before login.
export function AuthProvider({ children }) {
  const [status, setStatus] = useState("loading");   // loading | authed | anon
  const [user,   setUser]   = useState(null);

  const toAnon = useCallback(() => {
    closeSocket();
    setUser(null);
    setStatus("anon");
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(toAnon);
    (async () => {
      let me = await fetchMe();
      if (!me && await refreshSession()) me = await fetchMe();
      if (me) { setUser(me); setStatus("authed"); }
      else toAnon();
    })().catch(toAnon);
  }, [toAnon]);

  const logout = useCallback(async () => {
    await apiFetch("/auth/logout", { method: "POST" }).catch(() => {});
    toAnon();
  }, [toAnon]);

  if (status === "loading") {
    return (
      <div className="h-screen flex items-center justify-center bg-surface-0">
        <div className="w-5 h-5 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (status === "anon") return <LoginScreen />;

  return (
    <AuthContext.Provider value={{ status, user, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
