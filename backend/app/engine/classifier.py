from __future__ import annotations

from statistics import median
from typing import Literal

DeviceState = Literal["CALIBRATING", "ONLINE", "STANDBY", "OFFLINE"]


def moving_avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


class ClassifierV1:
    """
    V2 Logic (stable + intuitive):
    - baseline = median(global_history)
    - threshold = max(baseline * 1.25, baseline + 80ms)  (guard for tiny baselines)
    - ONLINE if recent_avg <= threshold, else STANDBY
    - CALIBRATING until we have enough history (>=10)
    """

    def __init__(self, history_limit: int = 2000, recent_limit: int = 3, min_history: int = 10) -> None:
        self.history_limit = history_limit
        self.recent_limit = recent_limit
        self.min_history = min_history

    def compute_threshold(self, global_history: list[float]) -> tuple[float, float]:
        if len(global_history) < self.min_history:
            return (0.0, 0.0)
        b = float(median(global_history))
        thr = max(b * 1.25, b + 80.0)
        return (b, thr)

    def classify(
        self,
        *,
        global_history: list[float],
        recent: list[float],
        is_offline: bool,
    ) -> tuple[DeviceState, float, float]:
        if is_offline:
            b, thr = self.compute_threshold(global_history)
            return ("OFFLINE", b, thr)

        if len(global_history) < self.min_history:
            return ("CALIBRATING", 0.0, 0.0)

        b, thr = self.compute_threshold(global_history)
        avg = moving_avg(recent)
        state: DeviceState = "ONLINE" if avg and avg <= thr else "STANDBY"
        return (state, b, thr)
