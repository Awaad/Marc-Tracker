import { create } from "zustand";
import type { Contact, TrackerPoint, TrackerSnapshot, WsMessage } from "../types";
import { RingBuffer } from "../lib/ring";


type TrackerState = {
  contacts: Contact[];
  selectedContactId: string | null;

  runningContactIds: Set<string>;

  // bounded history per contact/device
  points: Record<string, Record<string, RingBuffer<TrackerPoint>>>; // points[contactId][deviceId]=[]
  snapshots: Record<string, TrackerSnapshot | undefined>;

  setContacts: (c: Contact[]) => void;
  setSelected: (id: string | null) => void;
  setRunning: (ids: string[]) => void;

  applyWs: (msg: WsMessage) => void;
  seedHistory: (contactId: string, history: TrackerPoint[]) => void;
};

const MAX_POINTS = 300;

export const useTracker = create<TrackerState>((set, get) => ({
  contacts: [],
  selectedContactId: null,
  runningContactIds: new Set(),
  points: {},
  snapshots: {},

  setContacts: (c) => set({ contacts: c }),
  setSelected: (id) => set({ selectedContactId: id }),

  setRunning: (ids) => set({ runningContactIds: new Set(ids) }),

  seedHistory: (contactId, history) => {
  const grouped: Record<string, RingBuffer<TrackerPoint>> = {};
  for (const p of history) {
    grouped[p.device_id] ||= new RingBuffer<TrackerPoint>(MAX_POINTS);
    grouped[p.device_id].push(p);
  }

  // derive snapshot from history (latest point per device)
  const devices = Object.entries(grouped).map(([device_id, rb]) => {
    const arr = rb.toArray();
    const last = arr[arr.length - 1];

    // compute streak if missing
    let streak = last?.timeout_streak ?? 0;
    if (streak === 0 && arr.length) {
      let s = 0;
      for (let i = arr.length - 1; i >= 0; i--) {
        const st = arr[i].state;
        if (st === "TIMEOUT" || st === "OFFLINE") s++;
        else break;
      }
      streak = s;
    }

    return last
      ? {
          device_id,
          state: last.state,
          rtt_ms: last.rtt_ms,
          avg_ms: last.avg_ms,
          updated_at_ms: last.timestamp_ms,
          timeout_streak: streak,
        }
      : null;
  }).filter(Boolean) as any[];

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
    points: { ...s.points, [contactId]: grouped },
    snapshots: {
      ...s.snapshots,
      [contactId]: {
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
      const p = msg.point;
      set((s) => {
        const byContact = s.points[cid] ? { ...s.points[cid] } : {};
        const rb = byContact[p.device_id] ?? new RingBuffer<TrackerPoint>(MAX_POINTS);
        rb.push(p);
        byContact[p.device_id] = rb;
        return { points: { ...s.points, [cid]: byContact } };
      });
      return;
    }

    if (msg.type === "tracker:snapshot") {
      const cid = String(msg.contact_id);
      set((s) => ({ snapshots: { ...s.snapshots, [cid]: msg.snapshot } }));
      return;
    }
  },
}));
