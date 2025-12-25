from __future__ import annotations

import asyncio
import logging
import random
import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import BaseAdapter
from app.engine.correlator import Correlator
from app.realtime.manager import ws_manager
from app.storage.points_repo import TrackerPointsRepo

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
        db_factory,
        user_id: int,
        contact_id: int,
        platform: str,
        timeout_ms: int = 10_000,
    ) -> None:
        self.adapter = adapter
        self.correlator = correlator
        self.points_repo = points_repo
        self.db_factory = db_factory  # callable AsyncSession context
        self.user_id = user_id
        self.contact_id = contact_id
        self.platform = platform
        self.timeout_ms = timeout_ms

    async def run(self) -> None:
        receipts_task = asyncio.create_task(self._receipt_loop())
        try:
            while True:
                probe = await self.adapter.send_probe(user_id=self.user_id, contact_id=self.contact_id)
                self.correlator.mark_probe_sent(self.user_id, self.contact_id, probe.probe_id, probe.sent_at_ms)

                # schedule timeout
                asyncio.create_task(self._timeout_check(probe.probe_id, probe.sent_at_ms))

                await asyncio.sleep(2.0 + random.random() * 0.1)
        finally:
            receipts_task.cancel()
            try:
                await receipts_task
            except asyncio.CancelledError:
                pass

    async def _timeout_check(self, probe_id: str, sent_at_ms: int) -> None:
        await asyncio.sleep(self.timeout_ms / 1000)

        # only mark offline if probe is still pending
        if not self.correlator.is_probe_pending(self.user_id, self.contact_id, probe_id):
            return
        
        result = self.correlator.mark_offline(self.user_id, self.contact_id, device_id="primary", timeout_ms=self.timeout_ms)

        med, thr = self.correlator.global_stats(self.user_id, self.contact_id)
        devices = self.correlator.snapshot_devices(self.user_id, self.contact_id)

        await self._persist_and_broadcast(
            device_id="primary",
            state=result["state"],
            rtt_ms=float(self.timeout_ms),
            avg_ms=result["avg_ms"],
            median_ms=med,
            threshold_ms=thr,
            probe_id=probe_id,
        )

        await self._broadcast_snapshot(devices, med, thr)

    async def _receipt_loop(self) -> None:
        async for r in self.adapter.receipts(user_id=self.user_id, contact_id=self.contact_id):
            update = self.correlator.apply_receipt(
                self.user_id, self.contact_id, r.probe_id, r.device_id, r.received_at_ms
            )
            if not update:
                continue

            devices = self.correlator.snapshot_devices(self.user_id, self.contact_id)
            med, thr = self.correlator.global_stats(self.user_id, self.contact_id)

            await self._persist_and_broadcast(
                device_id=r.device_id,
                state=update["state"],
                rtt_ms=update["rtt_ms"],
                avg_ms=update["avg_ms"],
                median_ms=update["median_ms"],
                threshold_ms=update["threshold_ms"],
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

        await ws_manager.broadcast_to_user(
            self.user_id,
            {
                "type": "tracker:point",
                "contact_id": self.contact_id,
                "platform": self.platform,
                "point": {
                    "timestamp_ms": ts,
                    "device_id": device_id,
                    "state": state,
                    "rtt_ms": rtt_ms,
                    "avg_ms": avg_ms,
                    "median_ms": median_ms,
                    "threshold_ms": threshold_ms,
                    "probe_id": probe_id,
                },
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
