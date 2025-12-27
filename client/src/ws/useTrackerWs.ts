import { useEffect } from "react";
import { useAuth } from "../state/auth";
import { useTracker } from "../state/tracker";
import { wsBaseUrl } from "../api/http";
import type { WsMessage } from "../types";

let sharedWs: WebSocket | null = null;
let sharedToken: string | null = null;
let pingTimer: number | null = null;
let closeTimer: number | null = null;

const subscribers = new Set<(msg: WsMessage) => void>();

function clearTimers() {
  if (pingTimer) {
    window.clearInterval(pingTimer);
    pingTimer = null;
  }
  if (closeTimer) {
    window.clearTimeout(closeTimer);
    closeTimer = null;
  }
}

function ensureWs(token: string) {
  // cancel any pending close (important for StrictMode)
  if (closeTimer) {
    window.clearTimeout(closeTimer);
    closeTimer = null;
  }

  // already connected for same token
  if (sharedWs && sharedToken === token && sharedWs.readyState !== WebSocket.CLOSED) return;

  // token changed => close old socket
  if (sharedWs && sharedToken !== token) {
    try { sharedWs.close(1000, "token changed"); } catch {}
    sharedWs = null;
    sharedToken = null;
  }

  const url = `${wsBaseUrl()}/ws?token=${encodeURIComponent(token)}`;
  console.log("[ws] connecting", url);

  const ws = new WebSocket(url);
  sharedWs = ws;
  sharedToken = token;

  clearTimers();

  pingTimer = window.setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) ws.send("ping");
  }, 25000);

  ws.onopen = () => {
    console.log("[ws] open");
    try { ws.send("ping"); } catch {}
  };

  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data) as WsMessage;
      for (const fn of subscribers) fn(msg);
    } catch {
      // ignore non-json
    }
  };

  ws.onerror = (e) => {
    console.error("[ws] error", e);
  };

  ws.onclose = (e) => {
    console.warn("[ws] close", { code: e.code, reason: e.reason, wasClean: e.wasClean });

    // Auto-reconnect if we still have listeners and token is still valid
    if (subscribers.size > 0 && sharedToken) {
      // small backoff
      window.setTimeout(() => {
        if (subscribers.size > 0 && sharedToken) ensureWs(sharedToken);
      }, 500);
    }
  };
}

export function useTrackerWs() {
  const token = useAuth((s) => s.token);
  const applyWs = useTracker((s) => s.applyWs);

  useEffect(() => {
    if (!token) return;

    subscribers.add(applyWs);
    ensureWs(token);

    return () => {
      subscribers.delete(applyWs);

      // Grace-close: StrictMode will remount quickly, so don't close immediately
      if (subscribers.size === 0) {
        closeTimer = window.setTimeout(() => {
          if (subscribers.size === 0 && sharedWs) {
            try { sharedWs.close(1000, "no subscribers"); } catch {}
            sharedWs = null;
            sharedToken = null;
            clearTimers();
          }
        }, 750); // grace period
      }
    };
  }, [token, applyWs]);
}