from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.core.capabilities import Platform

DeviceState = Literal["CALIBRATING", "ONLINE", "STANDBY", "OFFLINE"]


class Capabilities(BaseModel):
    delivery_receipts: bool = False
    read_receipts: bool = False
    presence: bool = False


def capabilities_for(platform: Platform) -> Capabilities:
    # Conservative defaults; adapters can override later.
    if platform == Platform.sms:
        return Capabilities(delivery_receipts=True)
    if platform == Platform.whatsapp:
        return Capabilities(delivery_receipts=True, read_receipts=True)
    if platform == Platform.signal:
        return Capabilities(delivery_receipts=True)
    if platform == Platform.telegram:
        return Capabilities()  # bot API doesn't support delivered/read
    return Capabilities()


class DeviceInfo(BaseModel):
    device_id: str
    state: DeviceState
    rtt_ms: float
    avg_ms: float
    updated_at_ms: int


class TrackerPoint(BaseModel):
    timestamp_ms: int
    device_id: str
    state: DeviceState
    rtt_ms: float
    avg_ms: float
    median_ms: float
    threshold_ms: float


class ContactCreate(BaseModel):
    platform: Platform
    target: str = Field(..., description="Platform-specific target identifier")
    display_name: str = ""
    display_number: str = ""


class Contact(BaseModel):
    id: str
    platform: Platform
    target: str
    display_name: str = ""
    display_number: str = ""
    capabilities: Capabilities


class ContactSnapshot(BaseModel):
    contact_id: str
    platform: Platform
    devices: list[DeviceInfo]
    device_count: int
    presence: Optional[str] = None
    median_ms: float = 0.0
    threshold_ms: float = 0.0
    capabilities: Capabilities


# ---- engine-internal events (dataclasses, not API) ----
@dataclass(frozen=True)
class ProbeSent:
    contact_id: str
    probe_id: str
    sent_at_ms: int


@dataclass(frozen=True)
class ReceiptEvent:
    contact_id: str
    probe_id: str
    device_id: str
    received_at_ms: int
    status: str


@dataclass(frozen=True)
class MeasurementEvent:
    contact_id: str
    device_id: str
    rtt_ms: float
    measured_at_ms: int
