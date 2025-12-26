import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../api/http";
import { useAuth } from "../state/auth";
import { useTracker } from "../state/tracker";
import { useTrackerWs } from "../ws/useTrackerWs";
import type { Contact, ContactCreatePayload, Platform, TrackerPoint } from "../types";

import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Input } from "../components/ui/input";
import TrackerChart from "../components/TrackerChart";
import { useNetVitals } from "../state/netvitals";

const SUPPORTED_PLATFORMS: ContactCreatePayload["platform"][] = ["signal", "whatsapp_web", "mock"];

function ageText(ms: number | undefined) {
  if (!ms) return "-";
  const s = Math.max(0, Math.floor((Date.now() - ms) / 1000));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  return `${h}h`;
}

function clamp0(n: number) {
  return n < 0 ? 0 : n;
}

function initials(name: string) {
  const s = name.trim();
  if (!s) return "?";
  const parts = s.split(/\s+/).slice(0, 2);
  return parts.map((p) => p[0]?.toUpperCase()).join("");
}

function Avatar({ url, label }: { url: string | null; label: string }) {
  if (url) {
    return (
      <img
        src={url}
        alt={label}
        className="w-10 h-10 rounded-full object-cover border"
        referrerPolicy="no-referrer"
      />
    );
  }
  return (
    <div className="w-10 h-10 rounded-full border flex items-center justify-center text-sm font-medium bg-muted">
      {initials(label)}
    </div>
  );
}

function StateBadge({ state }: { state: string }) {
  const cls =
    state === "ONLINE"
      ? "bg-green-600 text-white hover:bg-green-600"
      : state === "STANDBY"
      ? "bg-yellow-500 text-black hover:bg-yellow-500"
      : state === "TIMEOUT"
      ? "bg-orange-500 text-white hover:bg-orange-500"
      : state === "OFFLINE"
      ? "bg-red-600 text-white hover:bg-red-600"
      : "bg-slate-500 text-white hover:bg-slate-500";
  return <Badge className={cls}>{state}</Badge>;
}

function interpretInsights(opts: { insights: any | undefined; netStale: boolean; hasNet: boolean }) {
  const i = opts.insights;
  if (!i) return { verdict: "No insights yet.", bullets: ["Start tracking to collect samples."] };

  const bullets: string[] = [];

  const online = Number(i.online_ratio ?? 0);
  const timeoutRate = Number(i.timeout_rate ?? 0);
  const jitter = Number(i.jitter_ms ?? 0);
  const median = Number(i.median_rtt_ms ?? 0);
  const streak = Number(i.streak_max ?? 0);

  let verdict = "Mixed signal.";

  if (timeoutRate >= 0.2 || streak >= 2) {
    verdict = "Frequent missed receipts.";
    bullets.push("Likely unreachable periods, delivery delays, or the device/app not responding.");
  } else if (online >= 0.9 && jitter < 200) {
    verdict = "Mostly reachable and stable.";
    bullets.push("Good reliability with low variability.");
  } else if (online >= 0.75) {
    verdict = "Generally reachable, but variable.";
    bullets.push("Some variability; occasional delays possible.");
  } else {
    verdict = "Intermittently reachable.";
    bullets.push("Consider network instability, background restrictions, or device sleep.");
  }

  if (median > 0) bullets.push(`Typical latency ~${Math.round(median)}ms.`);
  if (jitter >= 500) bullets.push("High jitter: results are volatile (network fluctuations likely).");
  else if (jitter >= 250) bullets.push("Moderate jitter: expect occasional spikes.");

  if (opts.hasNet && opts.netStale) bullets.push("Network confidence is stale; adjusted RTT may be misleading.");
  if (!opts.hasNet) bullets.push("Network confidence unknown; raw RTT may include network baseline.");

  return { verdict, bullets: bullets.slice(0, 3) };
}

type BusyKey =
  | null
  | "create"
  | "refresh"
  | "start"
  | "stop"
  | "start_all"
  | "stop_all"
  | "refresh_profile"
  | "delete";

export default function Dashboard() {
  const logout = useAuth((s) => s.logout);

  const {
    contacts,
    selectedContactId,
    selectedPlatform,
    setContacts,
    setSelected,
    setSelectedPlatform,
    running,
    setRunning,
    seedHistory,
  } = useTracker();

  const snapshots = useTracker((s) => s.snapshots);
  const points = useTracker((s) => s.points);
  const insights = useTracker((s) => s.insights);

  const [selectedDeviceId, setSelectedDeviceId] = useState<string>("primary");

  // add contact
  const [newPlatform, setNewPlatform] = useState<ContactCreatePayload["platform"]>("whatsapp_web");
  const [newTarget, setNewTarget] = useState<string>("");
  const [newDisplayName, setNewDisplayName] = useState<string>("");

  // search
  const [q, setQ] = useState("");

  // adjusted
  const [useAdjusted, setUseAdjusted] = useState<boolean>(true);
  const net = useNetVitals((s) => s.v);
  const netBase = Number(net.rtt ?? 0) || 0;
  const netStale = net.updated_at_ms ? Date.now() - net.updated_at_ms > 60_000 : true;

  // UX indicators
  const [busy, setBusy] = useState<BusyKey>(null);
  const [notice, setNotice] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  useTrackerWs();

  function showNotice(kind: "ok" | "err", text: string) {
    setNotice({ kind, text });
    window.setTimeout(() => setNotice(null), 2500);
  }

  async function withAction(key: BusyKey, okText: string, fn: () => Promise<void>) {
    try {
      setBusy(key);
      await fn();
      showNotice("ok", okText);
    } catch (e: any) {
      console.error(e);
      showNotice("err", e?.message ? String(e.message) : "Request failed");
    } finally {
      setBusy(null);
    }
  }

  async function refreshContactsAndRunning() {
    const c = await apiFetch<Contact[]>("/contacts");
    setContacts(c);

    const r = await apiFetch<any>("/tracking/running");
    if (r?.running) {
      setRunning(r.running);
    } else if (r?.contact_ids) {
      setRunning(Object.fromEntries((r.contact_ids as number[]).map((id) => [String(id), []])));
    } else {
      setRunning({});
    }

    if (!selectedContactId && c.length) {
      setSelected(c[0].id);
      setSelectedPlatform(c[0].platform);
    }
  }

  useEffect(() => {
    refreshContactsAndRunning().catch(console.error);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [setContacts, setRunning]);

  const filteredContacts = useMemo(() => {
    const s = String(q ?? "").trim().toLowerCase();
    if (!s) return contacts;
    return contacts.filter((c) => {
      const name = String(c.display_name ?? "").toLowerCase();
      const target = String(c.target ?? "").toLowerCase();
      const plat = String(c.platform ?? "").toLowerCase();
      return name.includes(s) || target.includes(s) || plat.includes(s);
    });
  }, [contacts, q]);

  const selected = useMemo(
    () => contacts.find((c) => c.id === selectedContactId) ?? null,
    [contacts, selectedContactId]
  );

  // keep/choose platform
  useEffect(() => {
    if (!selected) return;

    const rset = running[selected.id];
    const keep = selectedPlatform && rset?.has(String(selectedPlatform));
    if (keep) return;

    const pickRunning = rset && rset.size ? ([...rset][0] as Platform) : null;
    const fallback = (pickRunning ?? selected.platform) as Platform;

    if (selectedPlatform !== fallback) setSelectedPlatform(fallback);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected?.id, running]);

  // history per session
  useEffect(() => {
    if (!selectedContactId || !selectedPlatform) return;

    (async () => {
      const hist = await apiFetch<TrackerPoint[]>(`/contacts/${selectedContactId}/points?limit=300`);
      const filtered = (hist as any[]).filter((p) => {
        const pPlat = (p as any).platform;
        if (!pPlat) return true;
        return String(pPlat) === String(selectedPlatform);
      });
      seedHistory(selectedContactId, selectedPlatform, filtered as any);
    })().catch(console.error);
  }, [selectedContactId, selectedPlatform, seedHistory]);

  useEffect(() => {
    setSelectedDeviceId("primary");
  }, [selectedContactId, selectedPlatform]);

  const sessionKey = selectedContactId && selectedPlatform ? `${selectedContactId}:${selectedPlatform}` : null;

  const selectedSnapshot = sessionKey ? snapshots[sessionKey] : undefined;
  const selectedPointsByDevice = sessionKey ? points[sessionKey] ?? {} : {};
  const sessInsights = sessionKey ? insights[sessionKey] : undefined;

  const deviceIds = Object.keys(selectedPointsByDevice);
  const effectiveDeviceId = deviceIds.includes(selectedDeviceId) ? selectedDeviceId : deviceIds[0] ?? "primary";

  const rb = selectedPointsByDevice[effectiveDeviceId];
  const rawPoints = rb ? rb.toArray() : [];

  const chartPoints = useMemo(() => {
    if (!useAdjusted || !net.rtt) return rawPoints;
    return rawPoints.map((p: any) => ({
      ...p,
      rtt_ms: clamp0(Number(p.rtt_ms ?? 0) - netBase),
      avg_ms: clamp0(Number(p.avg_ms ?? 0) - netBase),
    }));
  }, [rawPoints, useAdjusted, net.rtt, netBase]);

  const interp = interpretInsights({ insights: sessInsights, netStale, hasNet: Boolean(net.rtt) });

  const selectedRunningSet = selected ? running[selected.id] : undefined;
  const selectedIsRunning =
    selected && selectedPlatform ? Boolean(selectedRunningSet?.has(String(selectedPlatform))) : false;

  async function createContact() {
    const target = newTarget.trim();
    if (!target) return;

    const payload: ContactCreatePayload = {
      platform: newPlatform,
      target,
      display_name: newDisplayName.trim(),
      display_number: target,
      avatar_url: null,
      platform_meta: {},
    };

    const created = await apiFetch<Contact>("/contacts", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    setNewTarget("");
    setNewDisplayName("");

    await refreshContactsAndRunning();
    setSelected(created.id);
    setSelectedPlatform(created.platform);
  }

  async function deleteSelectedContact() {
    if (!selected) return;
    const ok = window.confirm(`Delete contact "${selected.display_name || selected.target}"? This cannot be undone.`);
    if (!ok) return;

    await apiFetch(`/contacts/${selected.id}`, { method: "DELETE" });
    await refreshContactsAndRunning();

    const remaining = contacts.filter((c) => c.id !== selected.id);
    const next = remaining[0] ?? null;
    setSelected(next ? next.id : null);
    if (next) setSelectedPlatform(next.platform);
  }

  async function refreshProfileSelected() {
    if (!selected) return;
    await apiFetch(`/contacts/${selected.id}/refresh_profile`, { method: "POST" });
    await refreshContactsAndRunning();
  }

  async function startSelected(platform: Platform | "all") {
    if (!selected) return;
    await apiFetch(`/tracking/${selected.id}/start?platform=${encodeURIComponent(platform)}`, { method: "POST" });
    await refreshContactsAndRunning();
  }

  async function stopSelected(platform: Platform | "all") {
    if (!selected) return;
    await apiFetch(`/tracking/${selected.id}/stop?platform=${encodeURIComponent(platform)}`, { method: "POST" });
    await refreshContactsAndRunning();
  }

  const statusText = selected ? ((selected.platform_meta as any)?.status_text as string | undefined) : undefined;

  return (
    <div className="min-h-screen p-6">
      {/* header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold">Marc-Tracker</h1>
          <p className="text-sm text-muted-foreground">Contacts, per-platform sessions, history, and insights</p>
        </div>
        <Button variant="outline" onClick={logout}>
          Logout
        </Button>
      </div>

      {/* 2 columns: contacts | right stack */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
        {/* left */}
        <Card className="l:col-span-2">
          <CardHeader>
            <CardTitle>Contacts</CardTitle>
          </CardHeader>

          <CardContent className="space-y-4">
            {/* add contact */}
            <div className="p-3 rounded-lg border space-y-2">
              <div className="text-sm font-medium">Add contact</div>

              <div className="grid grid-cols-2 gap-2">
                <Select value={newPlatform} onValueChange={(v) => setNewPlatform(v as ContactCreatePayload["platform"])}>
                  <SelectTrigger>
                    <SelectValue placeholder="Platform" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="signal">signal</SelectItem>
                    <SelectItem value="whatsapp_web">whatsapp</SelectItem>
                    <SelectItem value="mock">mock</SelectItem>
                  </SelectContent>
                </Select>

                <Input
                  placeholder="Target (e.g. +905...)"
                  value={newTarget}
                  onChange={(e) => setNewTarget(e.target.value)}
                />
              </div>

              <Input
                placeholder="Display name (optional)"
                value={newDisplayName}
                onChange={(e) => setNewDisplayName(e.target.value)}
              />

              <div className="flex gap-2">
                <Button
                  size="sm"
                  disabled={busy === "create" || !newTarget.trim()}
                  onClick={() => withAction("create", "Contact created.", createContact)}
                >
                  {busy === "create" ? "Creating…" : "Create"}
                </Button>

                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy === "refresh"}
                  onClick={() => withAction("refresh", "Refreshed.", refreshContactsAndRunning)}
                >
                  {busy === "refresh" ? "Refreshing…" : "Refresh"}
                </Button>
              </div>

              <div className="text-xs text-muted-foreground">
                WhatsApp Cloud disabled for now; use whatsapp_web bridge or signal.
              </div>
            </div>

            {/* search (fixed) */}
            <Input
              placeholder="Search contacts…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onInput={(e) => setQ((e.target as HTMLInputElement).value)}
            />

            {/* list */}
            <div className="space-y-2">
              {filteredContacts.map((c) => {
                const rset = running[c.id];
                const runningAny = Boolean(rset && rset.size);
                const name = c.display_name || c.target;

                return (
                  <button
                    key={c.id}
                    className={`w-full text-left p-3 rounded-lg border transition ${
                      selectedContactId === c.id ? "bg-muted" : "hover:bg-muted/50"
                    }`}
                    onClick={() => {
                      setSelected(c.id);
                      const pick = rset && rset.size ? ([...rset][0] as Platform) : (c.platform as Platform);
                      setSelectedPlatform(pick);
                    }}
                  >
                    <div className="flex items-center gap-3">
                      <Avatar url={c.avatar_url} label={name} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <div className="font-medium truncate">{name}</div>
                          <Badge variant={runningAny ? "default" : "secondary"} className="shrink-0">
                            {runningAny ? `${rset!.size} running` : "stopped"}
                          </Badge>
                        </div>
                        <div className="text-xs text-muted-foreground truncate">
                          {c.platform} • {c.target}
                        </div>
                      </div>
                    </div>
                  </button>
                );
              })}

              {filteredContacts.length === 0 && (
                <div className="text-sm text-muted-foreground p-2">No contacts match your search.</div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* right: stacked */}
        <div className="xl:col-span-3 space-y-4">
          {/* notice */}
          {notice ? (
            <div
              className={`rounded-lg border px-3 py-2 text-sm ${
                notice.kind === "ok" ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200"
              }`}
            >
              {notice.text}
            </div>
          ) : null}

          {!selected ? (
            <Card>
              <CardContent className="p-6 text-sm text-muted-foreground">Select a contact</CardContent>
            </Card>
          ) : (
            <>
              {/* contact overview + controls */}
              <Card>
                <CardContent className="p-4 space-y-3">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-center gap-3">
                      <Avatar url={selected.avatar_url} label={selected.display_name || selected.target} />
                      <div>
                        <div className="text-lg font-semibold">{selected.display_name || selected.target}</div>
                        <div className="text-sm text-muted-foreground">
                          {selected.platform} • {selected.target}
                        </div>
                        {statusText ? <div className="text-xs text-muted-foreground">status: {statusText}</div> : null}
                        <div className="text-xs text-muted-foreground">
                          receipts: {selected.capabilities.delivery_receipts ? "yes" : "no"} / read:{" "}
                          {selected.capabilities.read_receipts ? "yes" : "no"} / presence:{" "}
                          {selected.capabilities.presence ? "yes" : "no"}
                        </div>
                      </div>
                    </div>

                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={busy === "refresh_profile"}
                        onClick={() => withAction("refresh_profile", "Profile refreshed.", refreshProfileSelected)}
                      >
                        {busy === "refresh_profile" ? "Refreshing…" : "Refresh profile"}
                      </Button>

                      <Button
                        size="sm"
                        variant="destructive"
                        disabled={busy === "delete"}
                        onClick={() => withAction("delete", "Contact deleted.", deleteSelectedContact)}
                      >
                        {busy === "delete" ? "Deleting…" : "Delete"}
                      </Button>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 p-3 rounded-lg border">
                    <div className="text-sm font-medium mr-2">Session</div>

                    <div className="w-56">
                      <Select
                        value={String(selectedPlatform ?? selected.platform)}
                        onValueChange={(v) => setSelectedPlatform(v as Platform)}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Platform" />
                        </SelectTrigger>
                        <SelectContent>
                          {SUPPORTED_PLATFORMS.map((p) => (
                            <SelectItem key={p} value={p}>
                              {p}
                              {running[selected.id]?.has(p) ? " (running)" : ""}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    <Badge variant={selectedIsRunning ? "default" : "secondary"}>
                      {selectedIsRunning ? "running" : "stopped"}
                    </Badge>

                    <div className="flex gap-2 ml-auto">
                      <Button
                        size="sm"
                        disabled={busy === "start" || !selectedPlatform}
                        onClick={() =>
                          withAction("start", "Started tracking.", () => startSelected(selectedPlatform as Platform))
                        }
                      >
                        {busy === "start" ? "Starting…" : "Start"}
                      </Button>

                      <Button
                        size="sm"
                        variant="outline"
                        disabled={busy === "stop" || !selectedPlatform}
                        onClick={() =>
                          withAction("stop", "Stopped tracking.", () => stopSelected(selectedPlatform as Platform))
                        }
                      >
                        {busy === "stop" ? "Stopping…" : "Stop"}
                      </Button>

                      <Button
                        size="sm"
                        variant="outline"
                        disabled={busy === "start_all"}
                        onClick={() => withAction("start_all", "Started all platforms.", () => startSelected("all"))}
                      >
                        {busy === "start_all" ? "Starting…" : "Start all"}
                      </Button>

                      <Button
                        size="sm"
                        variant="outline"
                        disabled={busy === "stop_all"}
                        onClick={() => withAction("stop_all", "Stopped all platforms.", () => stopSelected("all"))}
                      >
                        {busy === "stop_all" ? "Stopping…" : "Stop all"}
                      </Button>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-2 p-3 rounded-lg border">
                    <div className="text-sm">
                      <span className="font-medium">Network confidence:</span>{" "}
                      {!net.rtt ? "unknown" : netStale ? "stale" : "ok"}{" "}
                      <span className="text-muted-foreground">(net.rtt={net.rtt ?? "-"})</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button size="sm" variant={useAdjusted ? "default" : "outline"} onClick={() => setUseAdjusted(true)}>
                        Adjusted
                      </Button>
                      <Button size="sm" variant={!useAdjusted ? "default" : "outline"} onClick={() => setUseAdjusted(false)}>
                        Raw
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Live session: devices (full width) above chart (full width) */}
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle>Live session</CardTitle>
                    <div className="w-56">
                      <Select value={effectiveDeviceId} onValueChange={setSelectedDeviceId}>
                        <SelectTrigger>
                          <SelectValue placeholder="Device" />
                        </SelectTrigger>
                        <SelectContent>
                          {deviceIds.length === 0 ? (
                            <SelectItem value="primary">primary</SelectItem>
                          ) : (
                            deviceIds.map((id) => (
                              <SelectItem key={id} value={id}>
                                {id}
                              </SelectItem>
                            ))
                          )}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </CardHeader>

                <CardContent className="space-y-4">
                  {/* devices */}
                  <div>
                    {selectedSnapshot ? (
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Device</TableHead>
                            <TableHead>State</TableHead>
                            <TableHead>RTT</TableHead>
                            <TableHead>Adj RTT</TableHead>
                            <TableHead>Avg</TableHead>
                            <TableHead>Streak</TableHead>
                            <TableHead>Last</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {selectedSnapshot.devices.map((d) => {
                            const adj = net.rtt ? clamp0(Number(d.rtt_ms ?? 0) - netBase) : null;
                            return (
                              <TableRow key={d.device_id}>
                                <TableCell>{d.device_id}</TableCell>
                                <TableCell>
                                  <StateBadge state={d.state} />
                                </TableCell>
                                <TableCell>{Math.round(d.rtt_ms)} ms</TableCell>
                                <TableCell>{adj === null ? "-" : `${Math.round(adj)} ms`}</TableCell>
                                <TableCell>{Math.round(d.avg_ms)} ms</TableCell>
                                <TableCell>{(d as any).timeout_streak ?? 0}</TableCell>
                                <TableCell>{ageText(d.updated_at_ms)}</TableCell>
                              </TableRow>
                            );
                          })}
                        </TableBody>
                      </Table>
                    ) : (
                      <p className="text-sm text-muted-foreground">No snapshot yet (start tracking)</p>
                    )}
                  </div>

                  {/* chart full width */}
                  <div className="rounded-lg border p-2">
                    <TrackerChart points={chartPoints} />
                  </div>

                  <div className="text-xs text-muted-foreground">
                    session: {selectedContactId}:{selectedPlatform} • device: {effectiveDeviceId} • points:{" "}
                    {chartPoints.length}
                  </div>
                </CardContent>
              </Card>

              {/* Insights */}
              <Card>
                <CardHeader>
                  <CardTitle>Insights</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {sessInsights ? (
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div>points: {sessInsights.total}</div>
                      <div>online ratio: {(sessInsights.online_ratio * 100).toFixed(1)}%</div>
                      <div>timeout rate: {(sessInsights.timeout_rate * 100).toFixed(1)}%</div>
                      <div>median RTT: {Math.round(sessInsights.median_rtt_ms)} ms</div>
                      <div>jitter (p95-p50): {Math.round(sessInsights.jitter_ms)} ms</div>
                      <div>max timeout streak: {sessInsights.streak_max}</div>
                      <div>updated: {ageText(sessInsights.computed_at_ms)}</div>
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">No insights yet (start tracking)</p>
                  )}

                  <div className="text-sm">
                    <div className="font-medium">{interp.verdict}</div>
                    <ul className="list-disc pl-5 text-muted-foreground">
                      {interp.bullets.map((b, idx) => (
                        <li key={idx}>{b}</li>
                      ))}
                    </ul>
                  </div>
                </CardContent>
              </Card>

              {/* NetVitals last */}
              <Card>
                <CardHeader>
                  <CardTitle>NetVitals</CardTitle>
                </CardHeader>
                <CardContent className="text-sm space-y-2">
                  <div className="grid grid-cols-2 gap-2">
                    <div>effectiveType: {net.effectiveType ?? "-"}</div>
                    <div>rtt: {net.rtt ?? "-"} ms</div>
                    <div>downlink: {net.downlink ?? "-"} Mbps</div>
                    <div>updated: {Math.floor((Date.now() - (net.updated_at_ms ?? Date.now())) / 1000)}s ago</div>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>CLS: {net.cls ?? "-"}</div>
                    <div>INP: {net.inp ? `${Math.round(net.inp)} ms` : "-"}</div>
                    <div>LCP: {net.lcp ? `${Math.round(net.lcp)} ms` : "-"}</div>
                    <div>FCP: {net.fcp ? `${Math.round(net.fcp)} ms` : "-"}</div>
                    <div>TTFB: {net.ttfb ? `${Math.round(net.ttfb)} ms` : "-"}</div>
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
