import { useEffect, useRef } from "react";
import { useAuth } from "../state/auth";
import { useTracker } from "../state/tracker";
import { wsBaseUrl } from "../api/http";
import type { WsMessage } from "../types";

export function useTrackerWs() {
  const token = useAuth((s) => s.token);
  const applyWs = useTracker((s) => s.applyWs);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!token) return;

    const ws = new WebSocket(`${wsBaseUrl()}/ws?token=${encodeURIComponent(token)}`);
    wsRef.current = ws;

    const ping = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send("ping");
    }, 25000);

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data) as WsMessage;
        applyWs(msg);
      } catch {
        // ignore
      }
    };

    ws.onopen = () => ws.send("ping");
    ws.onerror = () => {};
    ws.onclose = () => {};

    return () => {
      clearInterval(ping);
      ws.close();
    };
  }, [token, applyWs]);

  return wsRef;
}
