from __future__ import annotations

import time
import uuid
from typing import AsyncIterator

import httpx
from sqlalchemy import select

from app.adapters.base import AdapterProbe, AdapterReceipt, BaseAdapter
from app.adapters.whatsapp_web.service import WhatsAppWebService, whatsapp_web_service
from app.db.models import Contact as ContactOrm
from app.db.session import SessionLocal
from app.settings import settings
from app.storage.probe_repo import ProbeRepo


def now_ms() -> int:
    return int(time.time() * 1000)


class WhatsAppWebAdapter(BaseAdapter):
    def __init__(self, *, user_id: int, contact_id: int, service: WhatsAppWebService = whatsapp_web_service) -> None:
        self.user_id = user_id
        self.contact_id = contact_id
        self._service = service
        self._repo = ProbeRepo()
        self._queue = None
        self._closed = False
        self._http = httpx.AsyncClient(base_url=settings.whatsapp_web_bridge_base, timeout=20.0)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._http.aclose()
        await self._service.unsubscribe(self.user_id, self.contact_id)

    async def send_probe(self, *, user_id: int, contact_id: int) -> AdapterProbe:
        if user_id != self.user_id or contact_id != self.contact_id:
            raise RuntimeError("WhatsAppWebAdapter bound to different user/contact")

        async with SessionLocal() as db:
            c = await db.scalar(
                select(ContactOrm).where(ContactOrm.id == self.contact_id, ContactOrm.user_id == self.user_id)
            )
            if not c:
                raise RuntimeError("Contact not found for WhatsAppWebAdapter")
            recipient = c.target

        probe_id = uuid.uuid4().hex
        sent_at = now_ms()

        resp = await self._http.post("/send", json={"to": recipient, "text": f"[probe:{probe_id}] ping"})
        resp.raise_for_status()
        data = resp.json()
        message_id = data.get("message_id")

        async with SessionLocal() as db:
            await self._repo.insert_probe(
                db,
                user_id=self.user_id,
                contact_id=self.contact_id,
                platform="whatsapp_web",
                probe_id=probe_id,
                sent_at_ms=sent_at,
                platform_message_id=message_id if isinstance(message_id, str) else None,
                platform_message_ts=sent_at,
                send_response=data,
            )

        return AdapterProbe(
            probe_id=probe_id,
            sent_at_ms=sent_at,
            platform_message_id=message_id if isinstance(message_id, str) else None,
        )

    async def receipts(self, *, user_id: int, contact_id: int) -> AsyncIterator[AdapterReceipt]:
        if user_id != self.user_id or contact_id != self.contact_id:
            raise RuntimeError("WhatsAppWebAdapter bound to different user/contact")

        if self._queue is None:
            self._queue = await self._service.subscribe(self.user_id, self.contact_id)

        while not self._closed:
            ev = await self._queue.get()
            yield AdapterReceipt(
                probe_id=str(ev["probe_id"]),
                device_id="primary",
                received_at_ms=int(ev.get("when_ms") or now_ms()),
                status="delivered",
                platform_message_id=str(ev.get("message_id") or ""),
            )
