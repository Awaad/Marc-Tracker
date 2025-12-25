from __future__ import annotations

import asyncio
import json
import logging

import websockets
from websockets.exceptions import ConnectionClosed
from sqlalchemy import select

from app.db.models import PlatformProbe
from app.db.session import SessionLocal
from app.settings import settings

log = logging.getLogger("app.waweb")


class WhatsAppWebService:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._lock = asyncio.Lock()
        self._queues: dict[tuple[int, int], asyncio.Queue[dict]] = {}

    async def start_all(self) -> None:
        if not settings.whatsapp_web_enabled:
            log.info("whatsapp_web disabled")
            return
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="waweb-bridge-loop")
        log.info("whatsapp_web service started")

    async def stop_all(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except Exception:
                pass
            self._task = None
        async with self._lock:
            self._queues.clear()

    async def subscribe(self, user_id: int, contact_id: int) -> asyncio.Queue[dict]:
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

    async def _publish(self, user_id: int, contact_id: int, ev: dict) -> None:
        async with self._lock:
            q = self._queues.get((user_id, contact_id))
        if not q:
            return
        try:
            q.put_nowait(ev)
        except asyncio.QueueFull:
            log.warning("waweb queue full; dropping")

    async def _run(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                async with websockets.connect(settings.whatsapp_web_bridge_ws, ping_interval=20, ping_timeout=20) as ws:
                    backoff = 1.0
                    log.info("connected to waweb bridge ws")
                    while not self._stop.is_set():
                        raw = await ws.recv()
                        msg = json.loads(raw)
                        await self._handle(msg)
            except (ConnectionClosed, OSError) as e:
                log.warning("waweb ws disconnected", extra={"err": str(e)})
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
            except asyncio.CancelledError:
                return
            except Exception as e:
                log.exception("waweb error", extra={"err": str(e)})
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    async def _handle(self, msg: dict) -> None:
        if msg.get("type") != "wa:update":
            return
        message_id = msg.get("message_id")
        if not isinstance(message_id, str):
            return

        when_ms = int(msg.get("ts") or 0)

        # Resolve message_id -> platform_probes row for platform "whatsapp_web"
        async with SessionLocal() as db:
            row = await db.scalar(
                select(PlatformProbe).where(
                    PlatformProbe.platform == "whatsapp_web",
                    PlatformProbe.platform_message_id == message_id,
                )
            )
            if not row:
                return

            # V1: treat any update as "delivered-like".
            # Later we'll map Baileys 'status/ack' values into delivered vs read.
            if row.delivered_at_ms is None and when_ms:
                row.delivered_at_ms = when_ms
                await db.commit()

            await self._publish(
                row.user_id,
                row.contact_id,
                {
                    "probe_id": row.probe_id,
                    "message_id": message_id,
                    "when_ms": when_ms,
                    "kind": "delivered",
                },
            )


whatsapp_web_service = WhatsAppWebService()
