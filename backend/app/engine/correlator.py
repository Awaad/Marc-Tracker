from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.engine.classifier import ClassifierV1, moving_avg


def now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class DeviceMetrics:
    last_rtt: float = 0.0
    recent: list[float] = field(default_factory=list)
    updated_at_ms: int = 0

    # reliability
    timeout_streak: int = 0
    offline: bool = False


@dataclass
class ContactMetrics:
    global_history: list[float] = field(default_factory=list)
    devices: dict[str, DeviceMetrics] = field(default_factory=dict)


class Correlator:
    """
    Correlates sent probes with receipts and produces per-device and per-contact stats.

    v2 change:
    - State is now isolated per (user_id, contact_id, platform) to avoid mixing RTT distributions.

    Reliability rules (v1):
    - Receipt resets timeout_streak and sets offline=False
    - Timeout increments timeout_streak
      - streak == 1 => state "TIMEOUT" (not yet OFFLINE)
      - streak >= 2 => offline=True and classifier sees is_offline=True
    """

    def __init__(self, classifier: ClassifierV1) -> None:
        self.classifier = classifier

        # (user, contact, platform) -> metrics
        self._by_session: dict[tuple[int, int, str], ContactMetrics] = {}

        # (user, contact, platform, probe_id) -> sent_ms
        self._probe_sent_at: dict[tuple[int, int, str, str], int] = {}

        self._timed_out_sent_at: dict[tuple[int, int, str, str], int] = {}
        self._timed_out_at_ms: dict[tuple[int, int, str, str], int] = {}
        self._late_window_ms = 120_000


    def is_probe_pending(self, user_id: int, contact_id: int, platform: str, probe_id: str) -> bool:
        return (user_id, contact_id, platform, probe_id) in self._probe_sent_at

    def mark_probe_sent(self, user_id: int, contact_id: int, platform: str, probe_id: str, sent_at_ms: int) -> None:
        self._probe_sent_at[(user_id, contact_id, platform, probe_id)] = sent_at_ms

    def mark_timeout(
        self,
        user_id: int,
        contact_id: int,
        platform: str,
        *,
        probe_id: str,
        device_id: str,
        timeout_ms: int,
    ) -> dict:
        """
        Mark a specific probe as timed out:
        - removes it from pending (prevents repeated timeouts on the same probe)
        - increments timeout streak
        - escalates to offline if streak >= 2
        """
        key = (user_id, contact_id, platform, probe_id)
        sent_at = self._probe_sent_at.pop(key, None)

        if sent_at is not None:
            self._timed_out_sent_at[key] = sent_at
            self._timed_out_at_ms[key] = now_ms()

        cm = self._by_session.setdefault((user_id, contact_id, platform), ContactMetrics())
        dm = cm.devices.setdefault(device_id, DeviceMetrics())

        dm.timeout_streak += 1
        dm.last_rtt = float(timeout_ms)
        dm.updated_at_ms = now_ms()

        dm.offline = dm.timeout_streak >= 2

        state, med, thr = self.classifier.classify(
            global_history=cm.global_history,
            recent=dm.recent,
            is_offline=dm.offline,
        )

        if dm.offline:
            state = "OFFLINE"
        else:
            state = "TIMEOUT"

        return {
            "state": state,
            "median_ms": med,
            "threshold_ms": thr,
            "avg_ms": moving_avg(dm.recent),
            "timeout_streak": dm.timeout_streak,
            "updated_at_ms": dm.updated_at_ms,
        }

    def apply_receipt(
        self,
        user_id: int,
        contact_id: int,
        platform: str,
        probe_id: str,
        device_id: str,
        received_at_ms: int,
    ) -> dict | None:
        key = (user_id, contact_id, platform, probe_id)

        sent_at = self._probe_sent_at.pop(key, None)
        if sent_at is None:
                    sent_at = self._timed_out_sent_at.pop(key, None)
                    to_at = self._timed_out_at_ms.pop(key, None)
                    # expire old timed-out probes
                    if to_at is not None and now_ms() - to_at > self._late_window_ms:
                        sent_at = None

        if sent_at is None:
                return None

        rtt = float(max(0, received_at_ms - sent_at))
        cm = self._by_session.setdefault((user_id, contact_id, platform), ContactMetrics())
        dm = cm.devices.setdefault(device_id, DeviceMetrics())

        dm.offline = False
        dm.timeout_streak = 0
        dm.last_rtt = rtt
        dm.updated_at_ms = received_at_ms

        dm.recent.append(rtt)
        if len(dm.recent) > self.classifier.recent_limit:
            dm.recent = dm.recent[-self.classifier.recent_limit :]

        cm.global_history.append(rtt)
        if len(cm.global_history) > self.classifier.history_limit:
            cm.global_history = cm.global_history[-self.classifier.history_limit :]

        state, med, thr = self.classifier.classify(
            global_history=cm.global_history,
            recent=dm.recent,
            is_offline=False,
        )

        return {
            "rtt_ms": rtt,
            "avg_ms": moving_avg(dm.recent),
            "state": state,
            "median_ms": med,
            "threshold_ms": thr,
            "updated_at_ms": received_at_ms,
            "timeout_streak": dm.timeout_streak,
        }

    def snapshot_devices(self, user_id: int, contact_id: int, platform: str) -> list[dict]:
        cm = self._by_session.get((user_id, contact_id, platform))
        if not cm:
            return []

        out: list[dict] = []
        for device_id, dm in cm.devices.items():
            state, _, _ = self.classifier.classify(
                global_history=cm.global_history,
                recent=dm.recent,
                is_offline=dm.offline,
            )

            if dm.offline:
                state = "OFFLINE"
            elif dm.timeout_streak > 0:
                state = "TIMEOUT"

            out.append(
                {
                    "device_id": device_id,
                    "state": state,
                    "rtt_ms": dm.last_rtt,
                    "avg_ms": moving_avg(dm.recent),
                    "updated_at_ms": dm.updated_at_ms,
                    "timeout_streak": dm.timeout_streak,
                }
            )
        return out

    def global_stats(self, user_id: int, contact_id: int, platform: str) -> tuple[float, float]:
        cm = self._by_session.get((user_id, contact_id, platform))
        if not cm:
            return (0.0, 0.0)
        return self.classifier.compute_threshold(cm.global_history)
