from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque


def now_ms() -> int:
    return int(time.time() * 1000)


def percentile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    q = 0.0 if q < 0 else 1.0 if q > 1 else q
    idx = int(q * (len(sorted_vals) - 1))
    return float(sorted_vals[idx])


def clamp0(x: float) -> float:
    return 0.0 if x < 0 else x


@dataclass
class SessionWindow:
    # store (state, rtt_ms)
    points: Deque[tuple[str, float]] = field(default_factory=lambda: deque(maxlen=600))
    last_broadcast_ms: int = 0


class InsightsManager:
    def __init__(self, *, window_size: int = 600, broadcast_interval_ms: int = 2000) -> None:
        self.window_size = window_size
        self.broadcast_interval_ms = broadcast_interval_ms
        self._sessions: dict[tuple[int, int, str], SessionWindow] = {}

    def observe_point(self, *, user_id: int, contact_id: int, platform: str, point: dict) -> dict | None:
        key = (user_id, contact_id, platform)
        sess = self._sessions.get(key)
        if sess is None:
            sess = SessionWindow(points=deque(maxlen=self.window_size))
            self._sessions[key] = sess

        state = str(point.get("state") or "")
        rtt = point.get("rtt_ms")
        try:
            rtt_f = float(rtt) if rtt is not None else 0.0
        except Exception:
            rtt_f = 0.0

        sess.points.append((state, rtt_f))

        now = now_ms()
        if now - sess.last_broadcast_ms < self.broadcast_interval_ms:
            return None

        sess.last_broadcast_ms = now
        return self._compute(sess.points, now)

    def _compute(self, pts: Deque[tuple[str, float]], computed_at_ms: int) -> dict:
        items = list(pts)
        total = len(items)
        if total == 0:
            return {
                "total": 0,
                "online_ratio": 0.0,
                "timeout_rate": 0.0,
                "median_rtt_ms": 0.0,
                "jitter_ms": 0.0,
                "streak_max": 0,
                "computed_at_ms": computed_at_ms,
            }

        online = 0
        timeoutish = 0
        rtts: list[float] = []

        # streak_max of TIMEOUT/OFFLINE
        streak = 0
        streak_max = 0

        for state, rtt in items:
            if state == "ONLINE":
                online += 1
            if state in ("TIMEOUT", "OFFLINE"):
                timeoutish += 1

            if rtt and rtt > 0:
                rtts.append(float(rtt))

            if state in ("TIMEOUT", "OFFLINE"):
                streak += 1
                if streak > streak_max:
                    streak_max = streak
            else:
                streak = 0

        rtts.sort()
        p50 = percentile(rtts, 0.50)
        p95 = percentile(rtts, 0.95)

        return {
            "total": total,
            "online_ratio": online / total,
            "timeout_rate": timeoutish / total,
            "median_rtt_ms": p50,
            "jitter_ms": clamp0(p95 - p50),
            "streak_max": int(streak_max),
            "computed_at_ms": computed_at_ms,
        }
