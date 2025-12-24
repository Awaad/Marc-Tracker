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
    offline: bool = False


@dataclass
class ContactMetrics:
    global_history: list[float] = field(default_factory=list)
    devices: dict[str, DeviceMetrics] = field(default_factory=dict)


class Correlator:
    def __init__(self, classifier: ClassifierV1) -> None:
        self.classifier = classifier
        self._by_contact: dict[tuple[int, int], ContactMetrics] = {}
        self._probe_sent_at: dict[tuple[int, int, str], int] = {}  # (user,contact,probe_id)->sent_ms

    def mark_probe_sent(self, user_id: int, contact_id: int, probe_id: str, sent_at_ms: int) -> None:
        self._probe_sent_at[(user_id, contact_id, probe_id)] = sent_at_ms

    def mark_offline(self, user_id: int, contact_id: int, device_id: str, timeout_ms: int) -> dict:
        cm = self._by_contact.setdefault((user_id, contact_id), ContactMetrics())
        dm = cm.devices.setdefault(device_id, DeviceMetrics())
        dm.offline = True
        dm.last_rtt = float(timeout_ms)
        dm.updated_at_ms = now_ms()

        state, med, thr = self.classifier.classify(
            global_history=cm.global_history,
            recent=dm.recent,
            is_offline=True,
        )
        return {"state": state, "median_ms": med, "threshold_ms": thr, "avg_ms": moving_avg(dm.recent)}

    def apply_receipt(self, user_id: int, contact_id: int, probe_id: str, device_id: str, received_at_ms: int) -> dict | None:
        key = (user_id, contact_id, probe_id)
        sent_at = self._probe_sent_at.pop(key, None)
        if sent_at is None:
            return None  # unknown probe / already handled

        rtt = float(max(0, received_at_ms - sent_at))
        cm = self._by_contact.setdefault((user_id, contact_id), ContactMetrics())
        dm = cm.devices.setdefault(device_id, DeviceMetrics())

        dm.offline = False
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
        }

    def snapshot_devices(self, user_id: int, contact_id: int) -> list[dict]:
        cm = self._by_contact.get((user_id, contact_id))
        if not cm:
            return []
        out: list[dict] = []
        for device_id, dm in cm.devices.items():
            state, _, _ = self.classifier.classify(
                global_history=cm.global_history,
                recent=dm.recent,
                is_offline=dm.offline,
            )
            out.append(
                {
                    "device_id": device_id,
                    "state": state,
                    "rtt_ms": dm.last_rtt,
                    "avg_ms": moving_avg(dm.recent),
                    "updated_at_ms": dm.updated_at_ms,
                }
            )
        return out

    def global_stats(self, user_id: int, contact_id: int) -> tuple[float, float]:
        cm = self._by_contact.get((user_id, contact_id))
        if not cm:
            return (0.0, 0.0)
        return self.classifier.compute_threshold(cm.global_history)
