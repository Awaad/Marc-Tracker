from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from sqlalchemy import select

import websockets
from websockets.exceptions import ConnectionClosed

from app.db.session import SessionLocal
from app.settings import settings
from app.db.models import PlatformProbe

log = logging.getLogger("app.signal")


@dataclass(frozen=True)
class ResolvedReceipt:
    user_id: int
    contact_id: int
    probe_id: str
    kind: str        # "delivery" | "read"
    when_ms: int
    message_ts: int


class SignalService:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        
        self._lock = asyncio.Lock()
        self._queues: dict[tuple[int, int], asyncio.Queue[ResolvedReceipt]] = {}

    async def start_all(self) -> None:
        if not settings.signal_enabled:
            log.info("signal disabled")
            return
        if not settings.signal_account:
            log.warning("signal enabled but SIGNAL_ACCOUNT missing")
            return
        
        if self._task and not self._task.done():
            return

        self._stop.clear()
        self._task = asyncio.create_task(self._run_loop(), name="signal-receive-loop")

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

    
    async def subscribe(self, user_id: int, contact_id: int) -> asyncio.Queue[ResolvedReceipt]:
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


    async def _publish(self, ev: ResolvedReceipt) -> None:
        async with self._lock:
            q = self._queues.get((ev.user_id, ev.contact_id))
        if not q:
            return
        try:
            q.put_nowait(ev)
        except asyncio.QueueFull:
            log.warning("signal queue full, dropping receipt", extra={"user_id": ev.user_id, "contact_id": ev.contact_id})


    async def _run_loop(self) -> None:
        ws_url = settings.signal_ws_url()
        backoff = 1.0

        while not self._stop.is_set():
            try:
                log.info("connecting to signal ws", extra={"url": ws_url})
                async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
                    backoff = 1.0
                    while not self._stop.is_set():
                        raw = await ws.recv()
                        await self._handle_ws_message(raw)
            except (ConnectionClosed, OSError) as e:
                log.warning("signal ws disconnected", extra={"err": str(e)})
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
            except asyncio.CancelledError:
                return
            except Exception as e:
                log.exception("signal ws error", extra={"err": str(e)})
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    async def _handle_ws_message(self, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except Exception:
            return

        env = (msg.get("envelope") or {})
        receipt = env.get("receiptMessage")
        if not receipt:
            return

        when_ms = int(receipt.get("when") or 0)
        timestamps = receipt.get("timestamps") or []
        is_delivery = bool(receipt.get("isDelivery"))
        is_read = bool(receipt.get("isRead"))

        kind = "delivery" if is_delivery else ("read" if is_read else "other")
        if kind == "other":
            return

        # receipts identify original messages by timestamp(s)
        for ts in timestamps:
            message_ts = int(ts)

            # Resolve message_ts -> platform_probes row -> probe_id/user/contact
            async with SessionLocal() as db:
                row = await db.scalar(
                    select(PlatformProbe).where(
                        PlatformProbe.platform == "signal",
                        PlatformProbe.platform_message_ts == message_ts,
                    )
                )
                if not row:
                    continue

                # Persist delivered/read time into DB
                if kind == "delivery" and row.delivered_at_ms is None:
                    row.delivered_at_ms = when_ms
                    await db.commit()
                elif kind == "read" and row.read_at_ms is None:
                    row.read_at_ms = when_ms
                    await db.commit()

                await self._publish(
                    ResolvedReceipt(
                        user_id=row.user_id,
                        contact_id=row.contact_id,
                        probe_id=row.probe_id,
                        kind=kind,
                        when_ms=when_ms,
                        message_ts=message_ts,
                    )
                )



signal_service = SignalService()
