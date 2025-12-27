from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Dict

from app.adapters.base import BaseAdapter
from app.engine.correlator import Correlator
from app.engine.insights import InsightsManager
from app.realtime.manager import ws_manager
from app.storage.points_repo import TrackerPointsRepo
from app.notifications.notify_manager import NotifyManager, NotifyContext


log = logging.getLogger("app.engine")


def now_ms() -> int:
    return int(time.time() * 1000)


class ContactRunner:
    def __init__(
        self,
        *,
        adapter: BaseAdapter,
        correlator: Correlator,
        points_repo: TrackerPointsRepo,
        insights: InsightsManager | None,
        notifier: NotifyManager | None,
        notify_ctx: NotifyContext | None,
        db_factory,
        user_id: int,
        contact_id: int,
        platform: str,
        timeout_ms: int = 10_000,
        interval_s: float = 2.0,
    ) -> None:
        self.adapter = adapter
        self.correlator = correlator
        self.points_repo = points_repo
        self.insights = insights
        self.db_factory = db_factory
        self.user_id = user_id
        self.contact_id = contact_id
        self.platform = platform
        self.timeout_ms = timeout_ms
        self.interval_s = interval_s
        self.notifier = notifier
        self.notify_ctx = notify_ctx

        self._stop = asyncio.Event()
        self._timeout_tasks: Dict[str, asyncio.Task] = {}

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        receipts_task = asyncio.create_task(self._receipt_loop(), name=f"receipts:{self.contact_id}:{self.platform}")
        try:
            while not self._stop.is_set():
                probe = await self.adapter.send_probe(user_id=self.user_id, contact_id=self.contact_id)

                self.correlator.mark_probe_sent(
                    self.user_id, self.contact_id, self.platform, probe.probe_id, probe.sent_at_ms
                )

                t = asyncio.create_task(
                    self._timeout_check(probe.probe_id, probe.sent_at_ms),
                    name=f"timeout:{self.contact_id}:{self.platform}:{probe.probe_id}",
                )
                self._timeout_tasks[probe.probe_id] = t

                devices = self.correlator.snapshot_devices(self.user_id, self.contact_id, self.platform)
                primary = next((d for d in devices if d["device_id"] == "primary"), None)
                streak = int((primary or {}).get("timeout_streak") or 0)

                base = 2.0
                if streak == 1:
                    base = 3.0
                elif streak >= 2:
                    base = 5.0

                await asyncio.sleep(base + random.random() * 0.15)
        finally:
            receipts_task.cancel()
            try:
                await receipts_task
            except asyncio.CancelledError:
                pass

            for task in list(self._timeout_tasks.values()):
                task.cancel()
            for task in list(self._timeout_tasks.values()):
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    log.exception("timeout task crashed", extra={"user_id": self.user_id, "contact_id": self.contact_id})
            self._timeout_tasks.clear()

    async def _timeout_check(self, probe_id: str, sent_at_ms: int) -> None:
        try:
            await asyncio.sleep(self.timeout_ms / 1000)

            if not self.correlator.is_probe_pending(self.user_id, self.contact_id, self.platform, probe_id):
                return

            result = self.correlator.mark_timeout(
                self.user_id,
                self.contact_id,
                self.platform,
                probe_id=probe_id,
                device_id="primary",
                timeout_ms=self.timeout_ms,
            )

            med, thr = self.correlator.global_stats(self.user_id, self.contact_id, self.platform)
            devices = self.correlator.snapshot_devices(self.user_id, self.contact_id, self.platform)

            await self._persist_and_broadcast(
                device_id="primary",
                state=result["state"],
                rtt_ms=float(self.timeout_ms),
                avg_ms=float(result["avg_ms"]),
                median_ms=float(med),
                threshold_ms=float(thr),
                timeout_streak=int(result.get("timeout_streak", 0)),
                probe_id=probe_id,
            )
            await self._broadcast_snapshot(devices, med, thr)
        finally:
            self._timeout_tasks.pop(probe_id, None)

    async def _receipt_loop(self) -> None:
        async for r in self.adapter.receipts(user_id=self.user_id, contact_id=self.contact_id):
            t = self._timeout_tasks.pop(r.probe_id, None)
            if t is not None:
                t.cancel()

            update = self.correlator.apply_receipt(
                self.user_id, self.contact_id, self.platform, r.probe_id, r.device_id, r.received_at_ms
            )
            if not update:
                continue

            devices = self.correlator.snapshot_devices(self.user_id, self.contact_id, self.platform)
            med, thr = self.correlator.global_stats(self.user_id, self.contact_id, self.platform)

            await self._persist_and_broadcast(
                device_id=r.device_id,
                state=update["state"],
                rtt_ms=float(update["rtt_ms"]),
                avg_ms=float(update["avg_ms"]),
                median_ms=float(update["median_ms"]),
                threshold_ms=float(update["threshold_ms"]),
                timeout_streak=int(update.get("timeout_streak", 0)),
                probe_id=r.probe_id,
            )
            await self._broadcast_snapshot(devices, med, thr)

    async def _persist_and_broadcast(
        self,
        *,
        device_id: str,
        state: str,
        rtt_ms: float,
        avg_ms: float,
        median_ms: float,
        threshold_ms: float,
        timeout_streak: int | None = None,
        probe_id: str | None = None,
    ) -> None:
        ts = now_ms()
        async with self.db_factory() as db:  # type: ignore
            await self.points_repo.add_point(
                db,
                user_id=self.user_id,
                contact_id=self.contact_id,
                device_id=device_id,
                state=state,
                timestamp_ms=ts,
                rtt_ms=rtt_ms,
                avg_ms=avg_ms,
                median_ms=median_ms,
                threshold_ms=threshold_ms,
                probe_id=probe_id,
            )

        point_payload = {
            "timestamp_ms": ts,
            "device_id": device_id,
            "state": state,
            "rtt_ms": rtt_ms,
            "avg_ms": avg_ms,
            "median_ms": median_ms,
            "threshold_ms": threshold_ms,
            "timeout_streak": timeout_streak,
            "probe_id": probe_id,
        }

        if self.notifier is not None and device_id == "primary":
            # you need these values:
            # - user_email (from DB / current user)
            # - contact label/target + notify_enabled (from DB contact row)
            if self.notifier is not None and self.notify_ctx is not None and device_id == "primary":
                self.notifier.observe_primary(
                    ctx=self.notify_ctx,
                    device_id=device_id,
                    new_state=state,
                    rtt_ms=rtt_ms,
                    avg_ms=avg_ms,
                    median_ms=median_ms,
                    threshold_ms=threshold_ms,
                    timeout_streak=timeout_streak,
                    at_ms=ts,
                )


        await ws_manager.broadcast_to_user(
            self.user_id,
            {
                "type": "tracker:point",
                "contact_id": self.contact_id,
                "platform": self.platform,
                "point": point_payload,
            },
        )

        if self.insights is not None:
            insights = self.insights.observe_point(
                user_id=self.user_id,
                contact_id=self.contact_id,
                platform=self.platform,
                point=point_payload,
            )
            if insights is not None:
                await ws_manager.broadcast_to_user(
                    self.user_id,
                    {
                        "type": "insights:update",
                        "contact_id": self.contact_id,
                        "platform": self.platform,
                        "insights": insights,
                    },
                )

    async def _broadcast_snapshot(self, devices: list[dict], median_ms: float, threshold_ms: float) -> None:
        await ws_manager.broadcast_to_user(
            self.user_id,
            {
                "type": "tracker:snapshot",
                "contact_id": self.contact_id,
                "platform": self.platform,
                "snapshot": {
                    "devices": devices,
                    "device_count": len(devices),
                    "median_ms": median_ms,
                    "threshold_ms": threshold_ms,
                },
            },
        )
