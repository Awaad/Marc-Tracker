from __future__ import annotations

from random import random
import string
import time
import uuid
from typing import AsyncIterator

from sqlalchemy import select

from app.adapters.base import AdapterProbe, AdapterReceipt, BaseAdapter
from app.adapters.whatsapp.client import WhatsAppClient
from app.adapters.whatsapp.service import whatsapp_service, WhatsAppService
from app.db.models import Contact as ContactOrm
from app.db.session import SessionLocal
from app.storage.probe_repo import ProbeRepo


def now_ms() -> int:
    return int(time.time() * 1000)


def extract_message_id(resp: dict) -> str | None:
    # typical: {"messages":[{"id":"wamid...."}]}
    msgs = resp.get("messages")
    if isinstance(msgs, list) and msgs:
        m0 = msgs[0]
        if isinstance(m0, dict) and isinstance(m0.get("id"), str):
            return m0["id"]
    return None


class WhatsAppAdapter(BaseAdapter):
    def __init__(self, *, user_id: int, contact_id: int, service: WhatsAppService = whatsapp_service) -> None:
        self.user_id = user_id
        self.contact_id = contact_id
        self._service = service
        self._client = WhatsAppClient()
        self._repo = ProbeRepo()
        self._queue = None
        self._closed = False

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._client.close()
        await self._service.unsubscribe(self.user_id, self.contact_id)


    async def send_probe(self, *, user_id: int, contact_id: int) -> Dict[str, Any]:
        """Send a fake delete message probe similar to TypeScript implementation."""
        if user_id != self.user_id or contact_id != self.contact_id:
            raise RuntimeError("WhatsAppAdapter bound to different user/contact")

        async with SessionLocal() as db:
            c = await db.scalar(select(ContactOrm).where(
                ContactOrm.id == self.contact_id, 
                ContactOrm.user_id == self.user_id
            ))
            if not c:
                raise RuntimeError("Contact not found for WhatsAppAdapter")
            recipient = c.target  # should be international phone number

        # Generate random message ID similar to TypeScript version
        prefixes = ['3EB0', 'BAE5', 'F1D2', 'A9C4', '7E8B', 'C3F9', '2D6A']
        random_prefix = random.choice(prefixes)
        
        # Generate random suffix (8 characters, uppercase alphanumeric)
        random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        random_msg_id = random_prefix + random_suffix
        
        sent_at = now_ms()
        
        # Since we're sending a fake delete, we need to track it differently
        # Create a unique probe ID for tracking
        probe_id = uuid.uuid4().hex
        
        # Check if your WhatsAppClient supports sending raw message objects
        # This might need adjustment based on your actual client API
        try:
            # Method 1: If client supports raw JSON messages
            resp = await self._client.send_message(
                to=recipient,
                message={
                    "delete": {
                        "remoteJid": recipient,
                        "fromMe": True,
                        "id": random_msg_id,
                    }
                }
            )
            
            # Method 2: If you need to use a different approach
            # resp = await self._client.send_text(
            #     to=recipient,
            #     body=f"[delete_probe:{probe_id}]"
            # )
            
            message_id = extract_message_id(resp) if resp else random_msg_id
            
        except Exception as e:
            # Fallback to sending a text message if delete fails
            resp = await self._client.send_text(
                to=recipient, 
                body=f"[delete_probe:{probe_id}:{random_msg_id}]"
            )
            message_id = extract_message_id(resp)

        # Store the probe in database
        async with SessionLocal() as db:
            await self._repo.insert_probe(
                db,
                user_id=self.user_id,
                contact_id=self.contact_id,
                platform="whatsapp",
                probe_id=probe_id,
                sent_at_ms=sent_at,
                platform_message_id=message_id,
                send_response=resp,
            )

        return {
            "probe_id": probe_id,
            "delete_message_id": random_msg_id,
            "sent_at_ms": sent_at,
            "platform_message_id": message_id,
            "response": resp,
        }


    # async def send_probe(self, *, user_id: int, contact_id: int) -> AdapterProbe:
        if user_id != self.user_id or contact_id != self.contact_id:
            raise RuntimeError("WhatsAppAdapter bound to different user/contact")

        async with SessionLocal() as db:
            c = await db.scalar(select(ContactOrm).where(ContactOrm.id == self.contact_id, ContactOrm.user_id == self.user_id))
            if not c:
                raise RuntimeError("Contact not found for WhatsAppAdapter")
            recipient = c.target  # should be international phone number

        probe_id = uuid.uuid4().hex
        sent_at = now_ms()

        resp = await self._client.send_text(to=recipient, body=f"[probe:{probe_id}] ping")
        message_id = extract_message_id(resp)

        async with SessionLocal() as db:
            await self._repo.insert_probe(
                db,
                user_id=self.user_id,
                contact_id=self.contact_id,
                platform="whatsapp",
                probe_id=probe_id,
                sent_at_ms=sent_at,
                platform_message_id=message_id,
                send_response=resp,
            )

        return AdapterProbe(
            probe_id=probe_id,
            sent_at_ms=sent_at,
            platform_message_id=message_id,
        )

    async def receipts(self, *, user_id: int, contact_id: int) -> AsyncIterator[AdapterReceipt]:
        if user_id != self.user_id or contact_id != self.contact_id:
            raise RuntimeError("WhatsAppAdapter bound to different user/contact")

        if self._queue is None:
            self._queue = await self._service.subscribe(self.user_id, self.contact_id)

        while not self._closed:
            ev = await self._queue.get()

            # keep RTT semantics: treat "delivered" as ACK
            if ev.kind != "delivered":
                continue

            yield AdapterReceipt(
                probe_id=ev.probe_id,
                device_id="primary",
                received_at_ms=ev.when_ms,
                status="delivered",
                platform_message_id=ev.message_id,
            )
