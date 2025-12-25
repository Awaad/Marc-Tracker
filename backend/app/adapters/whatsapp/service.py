from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

log = logging.getLogger("app.whatsapp")


@dataclass(frozen=True)
class WhatsAppReceipt:
    user_id: int
    contact_id: int
    probe_id: str
    kind: str          # "delivered" | "read"
    when_ms: int
    message_id: str


class WhatsAppService:
    """
    Webhook-driven: start_all is mostly a no-op, but we keep it to match the "init all adapters" architecture.
    The webhook route will call publish_receipt() after DB correlation.
    """
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._queues: dict[tuple[int, int], asyncio.Queue[WhatsAppReceipt]] = {}

    async def start_all(self) -> None:
        log.info("whatsapp service ready")

    async def stop_all(self) -> None:
        async with self._lock:
            self._queues.clear()

    async def subscribe(self, user_id: int, contact_id: int) -> asyncio.Queue[WhatsAppReceipt]:
        async with self._lock:
            key = (user_id, contact_id)
            q = self._queues.get(key)
            if not q:
                q = asyncio.Queue(maxsize=10_000)
                self._queues[key] = q
            return q

    async def unsubscribe(self, user_id: int, contact_id: int) -> None:
        async with self._lock:
            self._queues.pop((user_id, contact_id), None)

    async def publish(self, ev: WhatsAppReceipt) -> None:
        async with self._lock:
            q = self._queues.get((ev.user_id, ev.contact_id))
        if not q:
            return
        try:
            q.put_nowait(ev)
        except asyncio.QueueFull:
            log.warning("whatsapp queue full, dropping", extra={"user_id": ev.user_id, "contact_id": ev.contact_id})


whatsapp_service = WhatsAppService()
