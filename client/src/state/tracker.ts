import { create } from "zustand";
import type { Contact, TrackerPoint, TrackerSnapshot, WsMessage, Platform, InsightsV1 } from "../types";
import { RingBuffer } from "../lib/ring";

type ContactId = string;
type PlatformId = Platform | string;
type SessionKey = `${ContactId}:${PlatformId}`;

function makeSessionKey(contactId: ContactId, platform: PlatformId): SessionKey {
  return `${contactId}:${platform}` as SessionKey;
}

function safeGetLS(key: string): string | null {
  try {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSetLS(key: string, value: string | null) {
  try {
    if (typeof window === "undefined") return;
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {}
}

type TrackerState = {
  contacts: Contact[];
  selectedContactId: string | null;
  selectedPlatform: Platform | null;

  
  // running[contactId] => Set(platform)
  running: Record<string, Set<string>>;

  // bounded history per session/device
  points: Record<string, Record<string, RingBuffer<TrackerPoint>>>;
  snapshots: Record<string, TrackerSnapshot | undefined>;

  // server insights per session
  insights: Record<string, InsightsV1 | undefined>;

  setContacts: (c: Contact[]) => void;
  setSelected: (id: string | null) => void;
  setSelectedPlatform: (p: Platform | null) => void;

  // accepts { "123": ["signal","mock"], ... }
  setRunning: (running: Record<string, string[]>) => void;

  applyWs: (msg: WsMessage) => void;

  // seed per session
  seedHistory: (contactId: string, platform: Platform, history: TrackerPoint[]) => void;

  // convenience selectors
  getSessionKey: () => string | null;
};

const MAX_POINTS = 300;

export const useTracker = create<TrackerState>((set, get) => ({
  contacts: [],
  selectedContactId: safeGetLS("tracker:selectedContactId"),
  selectedPlatform: (safeGetLS("tracker:selectedPlatform") as Platform | null) ?? null,

  running: {},
  points: {},
  snapshots: {},
  insights: {},

  setContacts: (c) => set({ contacts: c }),

  setSelected: (id) => {
    safeSetLS("tracker:selectedContactId", id);
    set({ selectedContactId: id });
  },

  setSelectedPlatform: (p) => {
    safeSetLS("tracker:selectedPlatform", p);
    set({ selectedPlatform: p });
  },

  setRunning: (running) => {
    const mapped: Record<string, Set<string>> = {};
    for (const [cid, platforms] of Object.entries(running ?? {})) {
      mapped[cid] = new Set(platforms ?? []);
    }
    set({ running: mapped });
  },

  getSessionKey: () => {
    const { selectedContactId, selectedPlatform } = get();
    if (!selectedContactId || !selectedPlatform) return null;
    return makeSessionKey(selectedContactId, selectedPlatform);
  },

  seedHistory: (contactId, platform, history) => {
    const key = makeSessionKey(contactId, platform);

    const grouped: Record<string, RingBuffer<TrackerPoint>> = {};
    for (const p of history) {
      grouped[p.device_id] ||= new RingBuffer<TrackerPoint>(MAX_POINTS);
      grouped[p.device_id].push(p);
    }

    // derive snapshot from history (latest point per device)
    const devices = Object.entries(grouped)
      .map(([device_id, rb]) => {
        const arr = rb.toArray();
        const last = arr[arr.length - 1];

        if (!last) return null;

        // compute streak if missing
        let streak = last.timeout_streak ?? 0;
        if (streak === 0 && arr.length) {
          let s = 0;
          for (let i = arr.length - 1; i >= 0; i--) {
            const st = arr[i].state;
            if (st === "TIMEOUT" || st === "OFFLINE") s++;
            else break;
          }
          streak = s;
        }

        return {
          device_id,
          state: last.state,
          rtt_ms: last.rtt_ms,
          avg_ms: last.avg_ms,
          updated_at_ms: last.timestamp_ms,
          timeout_streak: streak,
        };
      })
      .filter(Boolean) as any[];

    const all = history.map((p) => p.rtt_ms).filter((x) => Number.isFinite(x));
    const sorted = [...all].sort((a, b) => a - b);
    const median_ms =
      sorted.length < 3
        ? 0
        : sorted.length % 2
        ? sorted[Math.floor(sorted.length / 2)]
        : (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2;

    const threshold_ms = median_ms * 0.9;

    set((s) => ({
      points: { ...s.points, [key]: grouped },
      snapshots: {
        ...s.snapshots,
        [key]: {
          devices,
          device_count: devices.length,
          median_ms,
          threshold_ms,
        },
      },
    }));
  },

  applyWs: (msg) => {
    if (msg.type === "contacts:init") {
      set({ contacts: msg.contacts });
      return;
    }

    if (msg.type === "tracker:point") {
      const cid = String(msg.contact_id);
      const plat = String(msg.platform ?? "unknown");
      const key = makeSessionKey(cid, plat);
      const p = msg.point;

      set((s) => {
        const bySession = s.points[key] ? { ...s.points[key] } : {};
        const rb = bySession[p.device_id] ?? new RingBuffer<TrackerPoint>(MAX_POINTS);
        rb.push(p);
        bySession[p.device_id] = rb;
        return { points: { ...s.points, [key]: bySession } };
      });
      return;
    }

    if (msg.type === "tracker:snapshot") {
      const cid = String(msg.contact_id);
      const plat = String(msg.platform ?? "unknown");
      const key = makeSessionKey(cid, plat);

      set((s) => ({ snapshots: { ...s.snapshots, [key]: msg.snapshot } }));
      return;
    }

    if (msg.type === "insights:update") {
      const cid = String(msg.contact_id);
      const plat = String(msg.platform ?? "unknown");
      const key = makeSessionKey(cid, plat);
      set((s) => ({ insights: { ...s.insights, [key]: msg.insights } }));
      return;
    }
  },
}));
