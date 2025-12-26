export type Platform = "mock" | "signal" | "whatsapp" | "whatsapp_web" | "telegram" | "sms";

export type DeviceState =
  | "CALIBRATING"
  | "ONLINE"
  | "STANDBY"
  | "TIMEOUT"
  | "OFFLINE";

export type Capabilities = {
  delivery_receipts: boolean;
  read_receipts: boolean;
  presence: boolean;
};

export type Contact = {
  id: string;
  platform: Platform;
  target: string;
  display_name: string;
  display_number: string;
  avatar_url: string | null;
  platform_meta: Record<string, any>;
  capabilities: Capabilities;
};

export type TrackerPoint = {
  timestamp_ms: number;
  device_id: string;
  state: DeviceState;
  rtt_ms: number;
  avg_ms: number;
  median_ms: number;
  threshold_ms: number;
  timeout_streak?: number;
  probe_id?: string | null;

  platform?: Platform | string;
};

export type SnapshotDevice = {
  device_id: string;
  state: DeviceState;
  rtt_ms: number;
  avg_ms: number;
  updated_at_ms: number;
  timeout_streak: number;
};

export type TrackerSnapshot = {
  devices: SnapshotDevice[];
  device_count: number;
  median_ms: number;
  threshold_ms: number;
};

export type InsightsV1 = {
  total: number;
  online_ratio: number;      
  timeout_rate: number;      
  median_rtt_ms: number;
  jitter_ms: number;
  streak_max: number;
  computed_at_ms: number;
};

export type WsMessage =
  | { type: "contacts:init"; contacts: Contact[] }
  | { type: "tracker:point"; contact_id: number; platform: Platform; point: TrackerPoint }
  | { type: "tracker:snapshot"; contact_id: number; platform: Platform; snapshot: TrackerSnapshot }
  | { type: "insights:update"; contact_id: number; platform: Platform; insights: InsightsV1 }
  | { type: string; [k: string]: any };

export type ContactCreatePayload = {
  platform: "mock" | "signal" | "whatsapp_web"; 
  target: string;
  display_name: string;
  display_number: string;
  avatar_url: string | null;
  platform_meta: Record<string, unknown>;
};
