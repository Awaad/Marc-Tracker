import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../api/http";
import { useAuth } from "../state/auth";
import { useTracker } from "../state/tracker";
import { useTrackerWs } from "../ws/useTrackerWs";
import type { Contact, TrackerPoint } from "../types";

import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import TrackerChart from "../components/TrackerChart";


export default function Dashboard() {
  const logout = useAuth((s) => s.logout);
  const { contacts, selectedContactId, setContacts, setSelected, runningContactIds, setRunning, seedHistory } =
    useTracker();
  const snapshots = useTracker((s) => s.snapshots);
  const points = useTracker((s) => s.points);

  const [selectedDeviceId, setSelectedDeviceId] = useState<string>("primary");

  useTrackerWs();

  useEffect(() => {
    (async () => {
      const c = await apiFetch<Contact[]>("/contacts");
      setContacts(c);
      const r = await apiFetch<{ contact_ids: number[] }>("/tracking/running");
      setRunning(r.contact_ids.map(String));
    })().catch(console.error);
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
  // If selected device doesn’t exist yet, fall back deterministically
  const effectiveDeviceId = deviceIds.includes(selectedDeviceId)
    ? selectedDeviceId
    : (deviceIds[0] ?? "primary");

  const rb = selectedContactId ? selectedPointsByDevice[effectiveDeviceId] : undefined;
  const primaryPoints = rb ? rb.toArray() : [];

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
          <CardContent className="space-y-2">
            {contacts.map((c) => {
              const running = runningContactIds.has(c.id);
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
                      onClick={async (e) => {
                        e.stopPropagation();
                        await apiFetch(`/tracking/${c.id}/start`, { method: "POST" });
                        const r = await apiFetch<{ contact_ids: number[] }>("/tracking/running");
                        setRunning(r.contact_ids.map(String));
                      }}
                    >
                      Start
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={async (e) => {
                        e.stopPropagation();
                        await apiFetch(`/tracking/${c.id}/stop`, { method: "POST" });
                        const r = await apiFetch<{ contact_ids: number[] }>("/tracking/running");
                        setRunning(r.contact_ids.map(String));
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
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {selectedSnapshot.devices.map((d) => (
                          <TableRow key={d.device_id}>
                            <TableCell>{d.device_id}</TableCell>
                            <TableCell>{d.state}</TableCell>
                            <TableCell>{Math.round(d.rtt_ms)} ms</TableCell>
                            <TableCell>{Math.round(d.avg_ms)} ms</TableCell>
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
      </div>
    </div>
  );
}
