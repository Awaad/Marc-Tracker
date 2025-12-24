from __future__ import annotations

import time
from typing import Any

from sqlalchemy import select

from app.adapters.base import BaseAdapter
from app.adapters.signal.client import SignalRestClient
from app.adapters.signal.service import SignalService, signal_service
from app.db.models import Contact as ContactOrm
from app.db.session import SessionLocal
from app.storage.probe_repo import ProbeRepo


def _now_ms() -> int:
    return int(time.time() * 1000)


def _extract_message_ts(send_response: dict) -> int | None:
    """
    signal-cli-rest-api versions differ; try a few shapes.
    We want the message timestamp that later appears in receiptMessage.timestamps[].
    """
    # common guesses (best-effort)
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
        self._probe_to_ts: dict[str, int] = {}

    async def close(self) -> None:
        await self._client.close()

    async def send_probe(self, probe_id: str) -> dict[str, Any]:
        # Load recipient (contact.target) lazily
        async with SessionLocal() as db:
            c = await db.scalar(select(ContactOrm).where(ContactOrm.id == self.contact_id, ContactOrm.user_id == self.user_id))
            if not c:
                raise RuntimeError("Contact not found for SignalAdapter")
            recipient = c.target

        message = f"[probe:{probe_id}] ping"
        resp = await self._client.send_text(recipient=recipient, message=message)
        ts = _extract_message_ts(resp)

        sent_ms = _now_ms()
        async with SessionLocal() as db:
            await self._repo.insert_probe(
                db,
                user_id=self.user_id,
                contact_id=self.contact_id,
                platform="signal",
                probe_id=probe_id,
                sent_at_ms=sent_ms,
                platform_message_ts=ts,
                send_response=resp,
            )

        if ts is not None:
            self._probe_to_ts[probe_id] = ts

        return {"platform_message_ts": ts, "send_response": resp}

    async def wait_delivery(self, probe_id: str, timeout_ms: int) -> dict[str, Any] | None:
        ts = self._probe_to_ts.get(probe_id)
        if ts is None:
            # Can't wait if send didn't yield a timestamp
            return None

        ev = await self._service.wait_receipt(ts, timeout_ms=timeout_ms)
        if not ev:
            return None
        if ev.kind != "delivery":
            # for now we treat only delivery as ACK (read/view can be later)
            return None

        return {"delivered_at_ms": ev.when_ms, "platform_message_ts": ev.message_ts}
