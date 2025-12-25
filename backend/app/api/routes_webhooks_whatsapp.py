from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.adapters.whatsapp.service import WhatsAppReceipt, whatsapp_service
from app.db.session import SessionLocal
from app.storage.probe_repo import ProbeRepo
from app.settings import settings

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
repo = ProbeRepo()


def _verify_signature(raw_body: bytes, header_value: str | None) -> bool:
    """
    Meta-style: X-Hub-Signature-256: sha256=<hexdigest>
    HMAC key: app secret.
    """
    if not settings.whatsapp_app_secret:
        return True  # signature verification disabled
    if not header_value or not header_value.startswith("sha256="):
        return False

    expected = header_value.split("sha256=", 1)[1].strip()
    mac = hmac.new(settings.whatsapp_app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return secrets.compare_digest(mac, expected)


@router.get("/whatsapp")
async def whatsapp_verify(request: Request) -> Any:
    qp = request.query_params
    mode = qp.get("hub.mode")
    token = qp.get("hub.verify_token")
    challenge = qp.get("hub.challenge")

    if mode == "subscribe" and token and settings.whatsapp_verify_token and token == settings.whatsapp_verify_token:
        return int(challenge) if (challenge and challenge.isdigit()) else (challenge or "")
    raise HTTPException(status_code=403, detail="verification failed")


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request) -> dict:
    raw = await request.body()
    sig = request.headers.get("X-Hub-Signature-256")

    if not _verify_signature(raw, sig):
        raise HTTPException(status_code=401, detail="bad signature")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")

    # We care about status updates: entry[].changes[].value.statuses[]
    entries = payload.get("entry") or []
    for e in entries:
        changes = e.get("changes") or []
        for ch in changes:
            value = (ch.get("value") or {})
            statuses = value.get("statuses") or []
            for st in statuses:
                message_id = st.get("id")
                status = st.get("status")  # "sent" | "delivered" | "read" | ...
                ts = st.get("timestamp")   # unix seconds string typically

                if not isinstance(message_id, str) or not isinstance(status, str):
                    continue

                when_ms: int | None = None
                if isinstance(ts, str) and ts.isdigit():
                    when_ms = int(ts) * 1000

                # Resolve message_id -> platform_probes row
                async with SessionLocal() as db:
                    row = await repo.find_by_platform_message_id(db, platform="whatsapp", platform_message_id=message_id)
                    if not row:
                        continue

                    # persist status times
                    if when_ms is not None:
                        if status == "delivered" and row.delivered_at_ms is None:
                            row.delivered_at_ms = when_ms
                            await db.commit()
                        elif status == "read" and row.read_at_ms is None:
                            row.read_at_ms = when_ms
                            await db.commit()

                    # publish to live subscribers (adapter receipts())
                    if when_ms is not None and status in ("delivered", "read"):
                        await whatsapp_service.publish(
                            WhatsAppReceipt(
                                user_id=row.user_id,
                                contact_id=row.contact_id,
                                probe_id=row.probe_id,
                                kind=status,
                                when_ms=when_ms,
                                message_id=message_id,
                            )
                        )

    return {"ok": True}
