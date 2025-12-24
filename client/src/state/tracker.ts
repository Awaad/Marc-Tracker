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
    set((s) => ({
      points: { ...s.points, [contactId]: grouped },
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
