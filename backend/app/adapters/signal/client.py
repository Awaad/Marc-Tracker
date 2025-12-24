from __future__ import annotations

import httpx

from app.settings import settings


class SignalRestClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(base_url=settings.signal_rest_base, timeout=20.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def send_text(self, *, recipient: str, message: str) -> dict:
        if not settings.signal_account:
            raise RuntimeError("SIGNAL_ACCOUNT missing")

        payload = {
            "message": message,
            "number": settings.signal_account,
            "recipients": [recipient],
        }
        r = await self._client.post("/v2/send", json=payload)
        r.raise_for_status()
        return r.json()
