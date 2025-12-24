from __future__ import annotations

import asyncio
import random
import time
import uuid
from typing import AsyncIterator

from app.adapters.base import AdapterProbe, AdapterReceipt, BaseAdapter


def now_ms() -> int:
    return int(time.time() * 1000)


class MockAdapter(BaseAdapter):
    """
    Simulates a platform with delivery receipts.

    Behavior:
    - send_probe returns immediately
    - after a random delay, a receipt is emitted (or dropped to simulate offline)
    """

    def __init__(
        self,
        *,
        min_delay_ms: int = 80,
        max_delay_ms: int = 800,
        drop_rate: float = 0.05,  # 5% of probes get no receipt => offline timeout
        device_id: str = "primary",
    ) -> None:
        self.min_delay_ms = min_delay_ms
        self.max_delay_ms = max_delay_ms
        self.drop_rate = drop_rate
        self.device_id = device_id

        self._q: asyncio.Queue[AdapterReceipt] = asyncio.Queue()
        self._closed = asyncio.Event()
        self._bg_tasks: set[asyncio.Task[None]] = set()

    async def send_probe(self, *, user_id: int, contact_id: int) -> AdapterProbe:
        probe_id = uuid.uuid4().hex
        sent = now_ms()

        # schedule receipt simulation
        t = asyncio.create_task(self._simulate_receipt(probe_id))
        self._bg_tasks.add(t)
        t.add_done_callback(lambda task: self._bg_tasks.discard(task))

        return AdapterProbe(probe_id=probe_id, sent_at_ms=sent, platform_message_id=None)

    async def receipts(self, *, user_id: int, contact_id: int) -> AsyncIterator[AdapterReceipt]:
        while True:
            if self._closed.is_set():
                return
            receipt = await self._q.get()
            yield receipt

    async def close(self) -> None:
        self._closed.set()
        for t in list(self._bg_tasks):
            t.cancel()
        # drain tasks
        for t in list(self._bg_tasks):
            try:
                await t
            except asyncio.CancelledError:
                pass

    async def _simulate_receipt(self, probe_id: str) -> None:
        # maybe drop receipt to simulate offline
        if random.random() < self.drop_rate:
            return

        delay = random.randint(self.min_delay_ms, self.max_delay_ms)
        await asyncio.sleep(delay / 1000)

        await self._q.put(
            AdapterReceipt(
                probe_id=probe_id,
                device_id=self.device_id,
                received_at_ms=now_ms(),
                status="delivered",
                platform_message_id=None,
            )
        )
