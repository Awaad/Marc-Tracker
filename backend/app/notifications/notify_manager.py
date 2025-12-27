from __future__ import annotations
from dataclasses import dataclass

from app.notifications.mailer import send_email_background

ONLINE_STATES = {"ONLINE", "STANDBY"}

@dataclass(frozen=True)
class NotifyContext:
    user_id: int
    user_email: str
    contact_id: int
    contact_label: str
    contact_target: str
    platform: str
    notify_enabled: bool


class NotifyManager:
    def __init__(self) -> None:
        # (user_id, contact_id, platform, device_id) -> last_state
        self._last_state: dict[tuple[int, int, str, str], str] = {}

    def observe_primary(
        self,
        *,
        ctx: NotifyContext,
        device_id: str,
        new_state: str,
        rtt_ms: float,
        avg_ms: float,
        median_ms: float,
        threshold_ms: float,
        timeout_streak: int | None,
        at_ms: int,
    ) -> None:
        key = (ctx.user_id, ctx.contact_id, ctx.platform, device_id)
        prev = self._last_state.get(key)
        self._last_state[key] = new_state

        if not ctx.notify_enabled:
            return

        if prev != "OFFLINE":
            return
        if new_state not in ONLINE_STATES:
            return

        subject = f"✅ {ctx.contact_label} is back online ({new_state})"
        text = (
            f"Contact: {ctx.contact_label}\n"
            f"Target: {ctx.contact_target}\n"
            f"Platform: {ctx.platform}\n"
            f"Transition: OFFLINE → {new_state}\n\n"
            f"RTT: {round(rtt_ms)} ms\n"
            f"Avg: {round(avg_ms)} ms\n"
            f"Median: {round(median_ms)} ms\n"
            f"Threshold: {round(threshold_ms)} ms\n"
            f"Timeout streak: {int(timeout_streak or 0)}\n"
            f"At(ms): {at_ms}\n"
        )
        send_email_background(to=ctx.user_email, subject=subject, text=text)
