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

  // contact form state
  const [newPlatform, setNewPlatform] = useState<ContactCreatePayload["platform"]>("whatsapp_web");
  const [newTarget, setNewTarget] = useState<string>("");
  const [newDisplayName, setNewDisplayName] = useState<string>("");
  const [newDisplayNumber, setNewDisplayNumber] = useState<string>("");

  // Commit 33
  const [useAdjusted, setUseAdjusted] = useState<boolean>(true);
  const net = useNetVitals((s) => s.v);
  const netBase = Number(net.rtt ?? 0) || 0;
  const netStale = net.updated_at_ms ? Date.now() - net.updated_at_ms > 60_000 : true;

  useTrackerWs();

  async function refreshContactsAndRunning() {
    const c = await apiFetch<Contact[]>("/contacts");
    setContacts(c);

    // backend now returns { contact_ids, running }
    const r = await apiFetch<any>("/tracking/running");

    if (r?.running) {
      setRunning(r.running);
    } else if (r?.contact_ids) {
      // backwards compat if needed
      setRunning(Object.fromEntries((r.contact_ids as number[]).map((id) => [String(id), []])));
    } else {
      setRunning({});
    }

    // If selection is empty after refresh, select first
    if (!selectedContactId && c.length) {
      setSelected(c[0].id);
      setSelectedPlatform(c[0].platform);
    }
  }

  useEffect(() => {
    refreshContactsAndRunning().catch(console.error);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [setContacts, setRunning]);

  const selected = useMemo(
    () => contacts.find((c) => c.id === selectedContactId) ?? null,
    [contacts, selectedContactId]
  );

  // When contact changes, choose a platform session:
  // - if current selectedPlatform is running for the contact, keep it
  // - else if any platform is running, pick the first
  // - else fallback to contact.platform
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

  // Load history per (contact, platform) session.
  // NOTE: points in DB may not have platform yet; we filter if platform exists, otherwise we keep all.
  useEffect(() => {
    if (!selectedContactId || !selectedPlatform) return;

    (async () => {
      const hist = await apiFetch<TrackerPoint[]>(`/contacts/${selectedContactId}/points?limit=300`);
      const filtered = (hist as any[]).filter((p) => {
        const pPlat = (p as any).platform;
        if (!pPlat) return true; // legacy points
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

  const deviceIds = Object.keys(selectedPointsByDevice);
  const effectiveDeviceId = deviceIds.includes(selectedDeviceId)
    ? selectedDeviceId
    : deviceIds[0] ?? "primary";

  const rb = selectedPointsByDevice[effectiveDeviceId];
  const rawPoints = rb ? rb.toArray() : [];

  // Commit 33: adjusted RTT for chart display (non-destructive)
  const chartPoints = useMemo(() => {
    if (!useAdjusted || !net.rtt) return rawPoints;
    return rawPoints.map((p: any) => ({
      ...p,
      rtt_ms: clamp0(Number(p.rtt_ms ?? 0) - netBase),
      avg_ms: clamp0(Number(p.avg_ms ?? 0) - netBase),
    }));
  }, [rawPoints, useAdjusted, net.rtt, netBase]);

  const sessInsights = sessionKey ? insights[sessionKey] : undefined;

  async function createContact() {
    const target = newTarget.trim();
    if (!target) return;

    const payload: ContactCreatePayload = {
      platform: newPlatform,
      target,
      display_name: newDisplayName.trim(),
      display_number: newDisplayNumber.trim() || target,
      avatar_url: null,
      platform_meta: {},
    };

    const created = await apiFetch<Contact>("/contacts", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    // clear form
    setNewTarget("");
    setNewDisplayName("");
    setNewDisplayNumber("");

    await refreshContactsAndRunning();
    setSelected(created.id);
    setSelectedPlatform(created.platform);
  }

  function platformBadge(p: string, isRunning: boolean) {
    return <Badge variant={isRunning ? "default" : "secondary"}>{p}</Badge>;
  }

  return (
    <div className="min-h-screen p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold">Marc-Tracker</h1>
          <p className="text-sm text-muted-foreground">Contacts, per-platform sessions, history, and insights</p>
        </div>
        <Button variant="outline" onClick={logout}>
          Logout
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>Contacts</CardTitle>
          </CardHeader>

          <CardContent className="space-y-3">
            {/* contact form */}
            <div className="p-3 rounded-lg border space-y-2">
              <div className="text-sm font-medium">Add contact</div>

              <div className="grid grid-cols-2 gap-2">
                <Select value={newPlatform} onValueChange={(v) => setNewPlatform(v as ContactCreatePayload["platform"])}>
                  <SelectTrigger>
                    <SelectValue placeholder="Platform" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="signal">signal</SelectItem>
                    <SelectItem value="whatsapp_web">whatsapp_web</SelectItem>
                    <SelectItem value="mock">mock</SelectItem>
                  </SelectContent>
                </Select>

                <Input
                  placeholder="Target (e.g. +905...)"
                  value={newTarget}
                  onChange={(e) => setNewTarget(e.target.value)}
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <Input
                  placeholder="Display name"
                  value={newDisplayName}
                  onChange={(e) => setNewDisplayName(e.target.value)}
                />
                <Input
                  placeholder="Display number"
                  value={newDisplayNumber}
                  onChange={(e) => setNewDisplayNumber(e.target.value)}
                />
              </div>

              <div className="flex gap-2">
                <Button size="sm" onClick={() => createContact().catch(console.error)} disabled={!newTarget.trim()}>
                  Create
                </Button>
                <Button size="sm" variant="outline" onClick={() => refreshContactsAndRunning().catch(console.error)}>
                  Refresh
                </Button>
              </div>

              <div className="text-xs text-muted-foreground">
                WhatsApp Cloud is disabled for now; use whatsapp_web bridge or signal.
              </div>
            </div>

            {contacts.map((c) => {
              const rset = running[c.id];
              const runningAny = Boolean(rset && rset.size);

              // Safety: keep WABA off + respect capabilities
              const baseStartDisabled = c.platform === "whatsapp" || !c.capabilities.delivery_receipts;

              return (
                <div
                  key={c.id}
                  className={`p-3 rounded-lg border cursor-pointer ${selectedContactId === c.id ? "bg-muted" : ""}`}
                  onClick={() => {
                    setSelected(c.id);
                    // prefer running platform if any
                    const pick = rset && rset.size ? ([...rset][0] as Platform) : (c.platform as Platform);
                    setSelectedPlatform(pick);
                  }}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium">{c.display_name || c.target}</div>
                      <div className="text-xs text-muted-foreground">
                        {c.platform} • {c.display_number}
                      </div>
                    </div>
                    <Badge variant={runningAny ? "default" : "secondary"}>
                      {runningAny ? `running (${rset!.size})` : "stopped"}
                    </Badge>
                  </div>

                  {/* Start/Stop all */}
                  <div className="mt-2 flex flex-wrap gap-2 items-center">
                    <Button
                      size="sm"
                      disabled={baseStartDisabled}
                      onClick={async (e) => {
                        e.stopPropagation();
                        await apiFetch(`/tracking/${c.id}/start?platform=all`, { method: "POST" });
                        await refreshContactsAndRunning();
                      }}
                      title={baseStartDisabled ? "No delivery receipts / platform disabled" : undefined}
                    >
                      Start all
                    </Button>

                    <Button
                      size="sm"
                      variant="outline"
                      onClick={async (e) => {
                        e.stopPropagation();
                        await apiFetch(`/tracking/${c.id}/stop?platform=all`, { method: "POST" });
                        await refreshContactsAndRunning();
                      }}
                    >
                      Stop all
                    </Button>

                    <div className="w-full h-px bg-border my-1" />

                    {/* Per-platform controls */}
                    {SUPPORTED_PLATFORMS.map((plat) => {
                      const isRunning = Boolean(rset?.has(plat));
                      return (
                        <div key={plat} className="flex items-center gap-2">
                          {platformBadge(plat, isRunning)}
                          <Button
                            size="sm"
                            // disabled={plat === "whatsapp" || baseStartDisabled}
                            onClick={async (e) => {
                              e.stopPropagation();
                              await apiFetch(`/tracking/${c.id}/start?platform=${encodeURIComponent(plat)}`, {
                                method: "POST",
                              });
                              await refreshContactsAndRunning();
                            }}
                          >
                            Start
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={async (e) => {
                              e.stopPropagation();
                              await apiFetch(`/tracking/${c.id}/stop?platform=${encodeURIComponent(plat)}`, {
                                method: "POST",
                              });
                              await refreshContactsAndRunning();
                            }}
                          >
                            Stop
                          </Button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Details</CardTitle>
          </CardHeader>
          <CardContent>
            {!selected ? (
              <p className="text-sm text-muted-foreground">Select a contact</p>
            ) : (
              <div className="space-y-4">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-lg font-semibold">{selected.display_name || selected.target}</div>
                    <div className="text-sm text-muted-foreground">
                      {selected.platform} • {selected.display_number}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      receipts: {selected.capabilities.delivery_receipts ? "yes" : "no"} / read:{" "}
                      {selected.capabilities.read_receipts ? "yes" : "no"}
                    </div>
                  </div>

                  {/* Platform selector (Commit 31) */}
                  <div className="flex items-center gap-2">
                    <div className="text-sm font-medium">Session</div>
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
                  </div>
                </div>

                {/* Commit 33: network confidence + raw/adjusted toggle */}
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

                {/* Commit 35: insights card */}
                <div className="p-3 rounded-lg border">
                  <div className="text-sm font-medium mb-2">Insights</div>
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
                </div>

                <div>
                  <div className="text-sm font-medium mb-2">Latest devices</div>
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
                                <Badge
                                  variant={
                                    d.state === "OFFLINE"
                                      ? "destructive"
                                      : d.state === "TIMEOUT"
                                      ? "secondary"
                                      : "default"
                                  }
                                >
                                  {d.state}
                                </Badge>
                              </TableCell>
                              <TableCell>{Math.round(d.rtt_ms)} ms</TableCell>
                              <TableCell>{adj === null ? "-" : `${Math.round(adj)} ms`}</TableCell>
                              <TableCell>{Math.round(d.avg_ms)} ms</TableCell>
                              <TableCell>{d.timeout_streak ?? 0}</TableCell>
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

                <div className="flex items-center justify-between">
                  <div className="text-sm font-medium">Chart</div>
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

                <TrackerChart points={chartPoints} />

                <div className="text-xs text-muted-foreground">
                  session: {selectedContactId}:{selectedPlatform} • device: {effectiveDeviceId} • points: {chartPoints.length}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
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
      </div>
    </div>
  );
}
