from __future__ import annotations

from statistics import median
from typing import Literal

DeviceState = Literal["CALIBRATING", "ONLINE", "STANDBY", "OFFLINE"]


def moving_avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


class ClassifierV1:
    """
    Logic:
    - global median from history
    - threshold = median * 0.9
    - moving avg from last 3 RTT samples per device
    """

    def __init__(self, history_limit: int = 2000, recent_limit: int = 3) -> None:
        self.history_limit = history_limit
        self.recent_limit = recent_limit

    def compute_threshold(self, global_history: list[float]) -> tuple[float, float]:
        if len(global_history) < 3:
            return (0.0, 0.0)
        m = float(median(global_history))
        return (m, m * 0.9)

    def classify(
        self,
        *,
        global_history: list[float],
        recent: list[float],
        is_offline: bool,
    ) -> tuple[DeviceState, float, float]:
        if is_offline:
            m, t = self.compute_threshold(global_history)
            return ("OFFLINE", m, t)

        if len(global_history) < 3:
            return ("CALIBRATING", 0.0, 0.0)

        m, t = self.compute_threshold(global_history)
        avg = moving_avg(recent)
        state: DeviceState = "ONLINE" if avg and avg < t else "STANDBY"
        return (state, m, t)
