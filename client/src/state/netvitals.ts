import { create } from "zustand";

export type NetVitals = {
  cls?: number;
  inp?: number;
  lcp?: number;
  fcp?: number;
  ttfb?: number;

  effectiveType?: string;
  rtt?: number;
  downlink?: number;

  updated_at_ms: number;
};

type NetVitalsState = {
  v: NetVitals;
  update: (patch: Partial<NetVitals>) => void;
};

export const useNetVitals = create<NetVitalsState>((set) => ({
  v: { updated_at_ms: Date.now() },
  update: (patch) =>
    set((s) => ({ v: { ...s.v, ...patch, updated_at_ms: Date.now() } })),
}));
