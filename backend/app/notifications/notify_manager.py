from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from app.notifications.mailer import send_email_background

ONLINE_STATES = {"ONLINE", "STANDBY"}

@dataclass
class NotifyEvent:
    user_email: str
    contact_label: str
    contact_target: str
    platform: str
    new_state: str
    rtt_ms: float
    avg_ms: float
    median_ms: float
    threshold_ms: float
    timeout_streak: int | None
    at_ms: int

class NotifyManager:
    def __init__(self) -> None:
        # (user_id, contact_id, platform, device_id) -> last_state
        self._last_state: dict[tuple[int, int, str, str], str] = {}

    def observe_state_change(
        self,
        *,
        user_id: int,
        user_email: str,
        contact_id: int,
        contact_label: str,
        contact_target: str,
        platform: str,
        device_id: str,
        new_state: str,
        rtt_ms: float,
        avg_ms: float,
        median_ms: float,
        threshold_ms: float,
        timeout_streak: int | None,
        at_ms: int,
        notify_enabled: bool,
    ) -> None:
        if not notify_enabled:
            # still track last state so toggling on behaves predictably
            self._last_state[(user_id, contact_id, platform, device_id)] = new_state
            return

        key = (user_id, contact_id, platform, device_id)
        prev = self._last_state.get(key)
        self._last_state[key] = new_state

        # Only fire on OFFLINE -> ONLINE/STANDBY (your request)
        if prev != "OFFLINE":
            return
        if new_state not in ONLINE_STATES:
            return

        subject = f"✅ {contact_label} is back online ({new_state})"
        body = (
            f"Contact: {contact_label}\n"
            f"Target: {contact_target}\n"
            f"Platform: {platform}\n"
            f"New state: {new_state}\n"
            f"RTT: {round(rtt_ms)} ms\n"
            f"Avg: {round(avg_ms)} ms\n"
            f"Median: {round(median_ms)} ms\n"
            f"Threshold: {round(threshold_ms)} ms\n"
            f"Timeout streak: {timeout_streak or 0}\n"
            f"Time: {at_ms}\n"
        )
        send_email_background(to=user_email, subject=subject, text=body)
