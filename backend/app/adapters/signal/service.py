from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass

import websockets
from websockets.exceptions import ConnectionClosed

from app.db.session import SessionLocal
from app.settings import settings
from app.storage.probe_repo import ProbeRepo

log = logging.getLogger("app.signal")


@dataclass
class ReceiptEvent:
    kind: str  # "delivery" | "read"
    when_ms: int
    message_ts: int


class SignalService:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._waiters: dict[int, asyncio.Future[ReceiptEvent]] = {}  # message_ts -> future
        self._lock = asyncio.Lock()
        self._repo = ProbeRepo()

    async def start_all(self) -> None:
        if not settings.signal_enabled:
            log.info("signal disabled")
            return
        if not settings.signal_account:
            log.warning("signal enabled but SIGNAL_ACCOUNT missing")
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

    async def wait_receipt(self, message_ts: int, timeout_ms: int) -> ReceiptEvent | None:
        fut = asyncio.get_running_loop().create_future()

        async with self._lock:
            self._waiters[message_ts] = fut

        try:
            return await asyncio.wait_for(fut, timeout=timeout_ms / 1000)
        except asyncio.TimeoutError:
            return None
        finally:
            async with self._lock:
                self._waiters.pop(message_ts, None)

    async def _notify(self, ev: ReceiptEvent) -> None:
        async with self._lock:
            fut = self._waiters.get(ev.message_ts)
            if fut and not fut.done():
                fut.set_result(ev)

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

            # Persist: map receipt -> probe row (if we have it)
            async with SessionLocal() as db:
                row = await self._repo.find_by_platform_ts(db, platform="signal", platform_message_ts=message_ts)
                if row:
                    if kind == "delivery":
                        await self._repo.mark_delivered(db, probe_id=row.probe_id, delivered_at_ms=when_ms)
                    elif kind == "read":
                        await self._repo.mark_read(db, probe_id=row.probe_id, read_at_ms=when_ms)

            await self._notify(ReceiptEvent(kind=kind, when_ms=when_ms, message_ts=message_ts))


signal_service = SignalService()
