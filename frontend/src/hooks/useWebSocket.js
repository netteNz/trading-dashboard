import { useEffect, useRef, useState } from "react";
import { io } from "socket.io-client";
import { refreshSession } from "../lib/api";

// Disconnect after the tab has been hidden this long. An open WebSocket keeps
// the Azure Container Apps replica alive (and billed), so idle tabs let go.
const HIDDEN_DISCONNECT_MS = 2 * 60 * 1000;

let _socket = null;

function getSocket() {
  if (!_socket) {
    // Auth cookies travel with the same-origin handshake; nothing to pass here.
    _socket = io("/", { autoConnect: false, withCredentials: true });
  }
  return _socket;
}

// Called on sign-out / session loss.
export function closeSocket() {
  if (_socket) {
    _socket.disconnect();
    _socket = null;
  }
}

export function useWebSocket(symbol) {
  const [lastTick,  setLastTick]  = useState(null);
  const [connected, setConnected] = useState(false);
  const symRef = useRef(symbol);

  // Connection lifecycle: connect once, re-auth on rejection, idle out when hidden.
  useEffect(() => {
    const socket = getSocket();
    let hiddenTimer = null;

    const onConnect = () => {
      setConnected(true);
      // Rooms don't survive a reconnect (or a server restart): resubscribe.
      if (symRef.current) socket.emit("subscribe", { symbol: symRef.current });
    };
    const onDisconnect = () => setConnected(false);
    const reauth = async () => {
      if (await refreshSession()) socket.connect();
    };
    const onConnectError = (err) => {
      if (err?.message === "unauthorized") reauth();
    };
    const onTick = (tick) => {
      if (tick.symbol === symRef.current) setLastTick(tick);
    };
    const onVisibility = () => {
      clearTimeout(hiddenTimer);
      if (document.hidden) {
        hiddenTimer = setTimeout(() => socket.disconnect(), HIDDEN_DISCONNECT_MS);
      } else if (!socket.connected) {
        socket.connect();
      }
    };

    socket.on("connect", onConnect);
    socket.on("disconnect", onDisconnect);
    socket.on("connect_error", onConnectError);
    socket.on("auth_expired", reauth);
    socket.on("tick", onTick);
    document.addEventListener("visibilitychange", onVisibility);
    if (!socket.connected) socket.connect();

    return () => {
      clearTimeout(hiddenTimer);
      document.removeEventListener("visibilitychange", onVisibility);
      socket.off("connect", onConnect);
      socket.off("disconnect", onDisconnect);
      socket.off("connect_error", onConnectError);
      socket.off("auth_expired", reauth);
      socket.off("tick", onTick);
    };
  }, []);

  // Symbol switch: move the subscription and drop the previous symbol's tick.
  useEffect(() => {
    symRef.current = symbol;
    setLastTick(null);
    const socket = getSocket();
    if (symbol && socket.connected) socket.emit("subscribe", { symbol });
    return () => {
      if (symbol && socket.connected) socket.emit("unsubscribe", { symbol });
    };
  }, [symbol]);

  return { lastTick, connected };
}
