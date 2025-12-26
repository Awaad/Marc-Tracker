import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../api/http";
import { useAuth } from "../state/auth";
import { useTracker } from "../state/tracker";
import { useTrackerWs } from "../ws/useTrackerWs";
import type { Contact, ContactCreatePayload, TrackerPoint } from "../types";

import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Input } from "../components/ui/input"; 
import TrackerChart from "../components/TrackerChart";
import { useNetVitals } from "../state/netvitals";


export default function Dashboard() {
  const logout = useAuth((s) => s.logout);
  const { contacts, selectedContactId, setContacts, setSelected, runningContactIds, setRunning, seedHistory } =
    useTracker();
  const snapshots = useTracker((s) => s.snapshots);
  const points = useTracker((s) => s.points);

  const [selectedDeviceId, setSelectedDeviceId] = useState<string>("primary");

  // contact form state
  const [newPlatform, setNewPlatform] = useState<ContactCreatePayload["platform"]>("whatsapp_web");
  const [newTarget, setNewTarget] = useState<string>("");
  const [newDisplayName, setNewDisplayName] = useState<string>("");
  const [newDisplayNumber, setNewDisplayNumber] = useState<string>("");

  useTrackerWs();

  async function refreshContactsAndRunning() {
    const c = await apiFetch<Contact[]>("/contacts");
    setContacts(c);
    const r = await apiFetch<{ contact_ids: number[] }>("/tracking/running");
    setRunning(r.contact_ids.map(String));
  }

  useEffect(() => {
    refreshContactsAndRunning().catch(console.error);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [setContacts, setRunning]);

  const selected = useMemo(
    () => contacts.find((c) => c.id === selectedContactId) ?? null,
    [contacts, selectedContactId]
  );

  useEffect(() => {
    if (!selectedContactId) return;
    (async () => {
      const hist = await apiFetch<TrackerPoint[]>(`/contacts/${selectedContactId}/points?limit=300`);
      seedHistory(selectedContactId, hist);
    })().catch(console.error);
  }, [selectedContactId, seedHistory]);

  useEffect(() => {
    setSelectedDeviceId("primary");
  }, [selectedContactId]);

  const selectedSnapshot = selectedContactId ? snapshots[selectedContactId] : undefined;

  const selectedPointsByDevice = selectedContactId ? points[selectedContactId] ?? {} : {};
  const deviceIds = Object.keys(selectedPointsByDevice);
  const effectiveDeviceId = deviceIds.includes(selectedDeviceId)
    ? selectedDeviceId
    : (deviceIds[0] ?? "primary");

  const rb = selectedContactId ? selectedPointsByDevice[effectiveDeviceId] : undefined;
  const primaryPoints = rb ? rb.toArray() : [];

  async function createContact() {
    const target = newTarget.trim();
    if (!target) return;

    const payload: ContactCreatePayload = {
      platform: newPlatform,
      target,
      display_name: newDisplayName.trim(),
      display_number: (newDisplayNumber.trim() || target),
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

    // refresh list + running; also select created
    await refreshContactsAndRunning();
    setSelected(created.id);
  }

  function ageText(ms: number | undefined) {
  if (!ms) return "-";
  const s = Math.max(0, Math.floor((Date.now() - ms) / 1000));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  return `${h}h`;
}

const net = useNetVitals((s) => s.v);

  return (
    <div className="min-h-screen p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold">Marc-Tracker</h1>
          <p className="text-sm text-muted-foreground">Contacts, live status, and history</p>
        </div>
        <Button variant="outline" onClick={logout}>Logout</Button>
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
                    {/* WhatsApp Cloud intentionally not shown */}
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
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => refreshContactsAndRunning().catch(console.error)}
                >
                  Refresh
                </Button>
              </div>

              <div className="text-xs text-muted-foreground">
                WhatsApp Cloud is disabled for now; use whatsapp_web bridge or signal.
              </div>
            </div>

            {contacts.map((c) => {
              const running = runningContactIds.has(c.id);

              // Safety: keep WABA off + respect capabilities
              const startDisabled = (c.platform === "whatsapp") || !c.capabilities.delivery_receipts;

              return (
                <div
                  key={c.id}
                  className={`p-3 rounded-lg border cursor-pointer ${selectedContactId === c.id ? "bg-muted" : ""}`}
                  onClick={() => setSelected(c.id)}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium">{c.display_name || c.target}</div>
                      <div className="text-xs text-muted-foreground">{c.platform} • {c.display_number}</div>
                    </div>
                    <Badge variant={running ? "default" : "secondary"}>{running ? "running" : "stopped"}</Badge>
                  </div>

                  <div className="mt-2 flex gap-2">
                    <Button
                      size="sm"
                      disabled={startDisabled}
                      onClick={async (e) => {
                        e.stopPropagation();
                        await apiFetch(`/tracking/${c.id}/start`, { method: "POST" });
                        await refreshContactsAndRunning();
                      }}
                      title={startDisabled ? "Platform not enabled / no delivery receipts" : undefined}
                    >
                      Start
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={async (e) => {
                        e.stopPropagation();
                        await apiFetch(`/tracking/${c.id}/stop`, { method: "POST" });
                        await refreshContactsAndRunning();
                      }}
                    >
                      Stop
                    </Button>
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
                <div className="flex items-center justify-between">
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
                          <TableHead>Avg</TableHead>
                          <TableHead>Streak</TableHead>
                          <TableHead>Last</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {selectedSnapshot.devices.map((d) => (
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
                            <TableCell>{Math.round(d.avg_ms)} ms</TableCell>
                            <TableCell>{d.timeout_streak ?? 0}</TableCell>
                            <TableCell>{ageText(d.updated_at_ms)}</TableCell>
                          </TableRow>
                        ))}
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

                <TrackerChart points={primaryPoints} />

                <div className="text-xs text-muted-foreground">
                  device: {effectiveDeviceId} • points: {primaryPoints.length}
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
