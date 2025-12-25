from __future__ import annotations

import httpx
from app.settings import settings


class WhatsAppClient:
    def __init__(self) -> None:
        if not settings.whatsapp_phone_number_id:
            raise RuntimeError("WHATSAPP_PHONE_NUMBER_ID missing")
        if not settings.whatsapp_access_token:
            raise RuntimeError("WHATSAPP_ACCESS_TOKEN missing")

        self._client = httpx.AsyncClient(
            base_url=settings.whatsapp_graph_base,
            timeout=20.0,
            headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"},
        )
        self._phone_number_id = settings.whatsapp_phone_number_id

    async def close(self) -> None:
        await self._client.aclose()

    async def send_text(self, *, to: str, body: str) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "to": to.lstrip("+"),
            "type": "text",
            "text": {"body": body},
        }
        r = await self._client.post(f"/{self._phone_number_id}/messages", json=payload)
        r.raise_for_status()
        return r.json()
