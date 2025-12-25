from __future__ import annotations

import time
import uuid
from typing import AsyncIterator

from sqlalchemy import select

from app.adapters.base import AdapterProbe, AdapterReceipt, BaseAdapter
from app.adapters.signal.client import SignalRestClient
from app.adapters.signal.service import SignalService, signal_service
from app.db.models import Contact as ContactOrm
from app.db.session import SessionLocal
from app.storage.probe_repo import ProbeRepo


def now_ms() -> int:
    return int(time.time() * 1000)


def extract_message_ts(send_response: dict) -> int | None:
    # best-effort: shape depends on signal-cli-rest-api version
    for key in ("timestamp", "messageTimestamp", "sentTimestamp"):
        v = send_response.get(key)
        if isinstance(v, (int, float)):
            return int(v)

    results = send_response.get("results")
    if isinstance(results, list) and results:
        r0 = results[0]
        if isinstance(r0, dict):
            for key in ("timestamp", "messageTimestamp", "sentTimestamp"):
                v = r0.get(key)
                if isinstance(v, (int, float)):
                    return int(v)

    return None


class SignalAdapter(BaseAdapter):
    def __init__(self, *, user_id: int, contact_id: int, service: SignalService = signal_service) -> None:
        self.user_id = user_id
        self.contact_id = contact_id
        self._service = service
        self._client = SignalRestClient()
        self._repo = ProbeRepo()
        self._queue = None
        self._closed = False

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._client.close()
        await self._service.unsubscribe(self.user_id, self.contact_id)

    async def send_probe(self, *, user_id: int, contact_id: int) -> AdapterProbe:
        # guard (engine passes same ids)
        if user_id != self.user_id or contact_id != self.contact_id:
            raise RuntimeError("SignalAdapter bound to different user/contact")

        async with SessionLocal() as db:
            c = await db.scalar(
                select(ContactOrm).where(ContactOrm.id == self.contact_id, ContactOrm.user_id == self.user_id)
            )
            if not c:
                raise RuntimeError("Contact not found for SignalAdapter")
            recipient = c.target

        probe_id = uuid.uuid4().hex
        sent_at = now_ms()

        resp = await self._client.send_text(recipient=recipient, message=f"[probe:{probe_id}] ping")
        msg_ts = extract_message_ts(resp)

        async with SessionLocal() as db:
            await self._repo.insert_probe(
                db,
                user_id=self.user_id,
                contact_id=self.contact_id,
                platform="signal",
                probe_id=probe_id,
                sent_at_ms=sent_at,
                platform_message_ts=msg_ts,
                send_response=resp,
            )

        return AdapterProbe(probe_id=probe_id, sent_at_ms=sent_at, platform_message_id=str(msg_ts) if msg_ts else None)

    async def receipts(self, *, user_id: int, contact_id: int) -> AsyncIterator[AdapterReceipt]:
        if user_id != self.user_id or contact_id != self.contact_id:
            raise RuntimeError("SignalAdapter bound to different user/contact")

        if self._queue is None:
            self._queue = await self._service.subscribe(self.user_id, self.contact_id)

        while not self._closed:
            ev = await self._queue.get()

            # IMPORTANT: to keep RTT semantics consistent, yield only "delivery" as ACK.
            if ev.kind != "delivery":
                continue

            yield AdapterReceipt(
                probe_id=ev.probe_id,
                device_id="primary",  # Signal multi-device support can be enhanced later
                received_at_ms=ev.when_ms,
                status="delivered",
                platform_message_id=str(ev.message_ts),
            )
