import { onCLS, onINP, onLCP, onFCP, onTTFB } from "web-vitals";
import { useNetVitals } from "../state/netvitals";

let started = false;

export function startNetVitals() {
  if (started) return;
  started = true;

  const update = useNetVitals.getState().update;

  // web-vitals metrics (report when ready)
  onCLS((m) => update({ cls: m.value }));
  onINP((m) => update({ inp: m.value }));
  onLCP((m) => update({ lcp: m.value }));
  onFCP((m) => update({ fcp: m.value }));
  onTTFB((m) => update({ ttfb: m.value }));

  // network info (best-effort; not supported everywhere)
  const conn: any = (navigator as any).connection;
  if (conn) {
    const push = () =>
      update({
        effectiveType: conn.effectiveType,
        rtt: conn.rtt,
        downlink: conn.downlink,
      });

    push();
    if (typeof conn.addEventListener === "function") {
      conn.addEventListener("change", push);
    }
  }
}
