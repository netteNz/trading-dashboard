import { useEffect, useRef, useState } from "react";
import { io } from "socket.io-client";

let _socket = null;

function getSocket() {
  if (!_socket) {
    _socket = io("/", { transports: ["websocket"], autoConnect: true });
  }
  return _socket;
}

export function useWebSocket(symbol) {
  const [lastTick, setLastTick] = useState(null);
  const [connected, setConnected] = useState(false);
  const symRef = useRef(symbol);

  useEffect(() => { symRef.current = symbol; }, [symbol]);

  useEffect(() => {
    const socket = getSocket();

    socket.on("connect",    () => setConnected(true));
    socket.on("disconnect", () => setConnected(false));

    socket.on("tick", (tick) => {
      if (tick.symbol === symRef.current) setLastTick(tick);
    });

    // Subscribe to symbol
    if (symbol) socket.emit("subscribe", { symbol });

    return () => {
      socket.off("tick");
      socket.off("connect");
      socket.off("disconnect");
    };
  }, [symbol]);

  return { lastTick, connected };
}
