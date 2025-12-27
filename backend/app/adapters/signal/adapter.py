from __future__ import annotations

import time
import uuid
from typing import AsyncIterator, Any

from sqlalchemy import select

from app.adapters.base import AdapterProbe, AdapterReceipt, BaseAdapter
from app.adapters.signal.client import SignalRestClient
from app.adapters.signal.service import SignalService, signal_service
from app.db.models import Contact as ContactOrm
from app.db.session import SessionLocal
from app.storage.probe_repo import ProbeRepo


def now_ms() -> int:
    return int(time.time() * 1000)


def _as_int(v: Any) -> int | None:
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str) and v.strip().isdigit():
        return int(v.strip())
    return None


def normalize_ts_ms(ts: int | None, fallback_ms: int) -> int:
    """
    Normalize Signal timestamps to milliseconds.
    Signal sometimes emits seconds (10 digits) vs ms (13 digits).
    """
    if ts is None:
        return fallback_ms
    # anything below 1e12 is almost certainly seconds in modern epoch time
    if ts < 1_000_000_000_000:
        return ts * 1000
    return ts


def extract_message_ts(send_response: dict) -> int | None:
    # common locations across versions
    for key in ("timestamp", "messageTimestamp", "sentTimestamp"):
        ts = _as_int(send_response.get(key))
        if ts is not None:
            return ts

    results = send_response.get("results")
    if isinstance(results, list) and results:
        r0 = results[0]
        if isinstance(r0, dict):
            for key in ("timestamp", "messageTimestamp", "sentTimestamp"):
                ts = _as_int(r0.get(key))
                if ts is not None:
                    return ts

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

    async def _get_recipient(self) -> str:
        async with SessionLocal() as db:
            c = await db.scalar(
                select(ContactOrm).where(ContactOrm.id == self.contact_id, ContactOrm.user_id == self.user_id)
            )
            if not c:
                raise RuntimeError("Contact not found for SignalAdapter")
            return c.target

    # async def send_probe(self, *, user_id: int, contact_id: int) -> AdapterProbe:
    #     if user_id != self.user_id or contact_id != self.contact_id:
    #         raise RuntimeError("SignalAdapter bound to different user/contact")

    #     recipient = await self._get_recipient()
    #     probe_id = uuid.uuid4().hex
    #     sent_at_ms = now_ms()

    #     resp = await self._client.send_text(recipient=recipient, message=f"[probe:{probe_id}] ping")

    #     raw_ts = extract_message_ts(resp)
    #     msg_ts_ms = normalize_ts_ms(raw_ts, sent_at_ms)

    #     async with SessionLocal() as db:
    #         await self._repo.insert_probe(
    #             db,
    #             user_id=self.user_id,
    #             contact_id=self.contact_id,
    #             platform="signal",
    #             probe_id=probe_id,
    #             sent_at_ms=sent_at_ms,
    #             platform_message_ts=msg_ts_ms,
    #             send_response=resp,
    #         )

    #     return AdapterProbe(probe_id=probe_id, sent_at_ms=sent_at_ms, platform_message_id=str(msg_ts_ms))


    async def send_probe(self, *, user_id: int, contact_id: int) -> AdapterProbe:
        if user_id != self.user_id or contact_id != self.contact_id:
            raise RuntimeError("SignalAdapter bound to different user/contact")

        recipient = await self._get_recipient()
        probe_id = uuid.uuid4().hex
        sent_at_ms = now_ms()

        # First, check if we need to send a base message for reactions
        # Reactions need a message to react to
        
        # Option A: React to existing message (if you have one)
        # Option B: Send invisible message, then react to it
        
        # For now, send minimal message
        message = "\u200B"  # Zero-width space
        
        resp = await self._client.send_text(recipient=recipient, message=message)

        raw_ts = extract_message_ts(resp)
        msg_ts_ms = normalize_ts_ms(raw_ts, sent_at_ms)

        # If you want to add a reaction too:
        try:
            # Send empty reaction (removing reaction) to same timestamp
            reaction_resp = await self._client.send_reaction(
                recipient=recipient,
                target_timestamp=raw_ts,  # React to our own message
                reaction=""
            )
        except:
            pass  # Reaction not supported or failed

        async with SessionLocal() as db:
            await self._repo.insert_probe(
                db,
                user_id=self.user_id,
                contact_id=self.contact_id,
                platform="signal",
                probe_id=probe_id,
                sent_at_ms=sent_at_ms,
                platform_message_ts=msg_ts_ms,
                send_response=resp,
            )

        return AdapterProbe(probe_id=probe_id, sent_at_ms=sent_at_ms, platform_message_id=str(msg_ts_ms))

    


    async def receipts(self, *, user_id: int, contact_id: int) -> AsyncIterator[AdapterReceipt]:
        if user_id != self.user_id or contact_id != self.contact_id:
            raise RuntimeError("SignalAdapter bound to different user/contact")

        # ensure receive loop is running
        await self._service.start_all()

        if self._queue is None:
            self._queue = await self._service.subscribe(self.user_id, self.contact_id)

        while not self._closed:
            ev = await self._queue.get()

            # Treat DELIVERY or READ as ACK for RTT (Signal installs vary)
            if ev.kind not in ("delivery", "read"):
                continue

            yield AdapterReceipt(
                probe_id=ev.probe_id,
                device_id="primary",
                received_at_ms=ev.when_ms,
                status="delivered",  # keep semantics: this is our ACK
                platform_message_id=str(ev.message_ts),
            )
