from __future__ import annotations

import httpx
from app.settings import settings


class SignalRestClient:
    """
    REST client for signal-cli-rest-api.

    We use:
      - POST /v2/send for sending probes
      - GET  /v1/receive/<account> for receiving envelopes in normal/native mode

    In JSON-RPC mode, receive must be done via websocket (/v1/receive/<account>).
    """

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(base_url=settings.signal_rest_base, timeout=35.0)

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
        # response is usually JSON with timestamp-ish fields (varies by version)
        return r.json()

    async def receive_http_once(self) -> list[dict]:
        """
        Normal/native mode polling endpoint.
        Returns a list of envelopes/messages (shape depends on version).
        """
        if not settings.signal_account:
            raise RuntimeError("SIGNAL_ACCOUNT missing")

        # Many installs expose: GET /v1/receive/<number>
        r = await self._client.get(f"/v1/receive/{settings.signal_account}")
        r.raise_for_status()

        # Some versions return [] when no messages.
        data = r.json()
        if isinstance(data, list):
            return data
        # Some versions wrap it
        if isinstance(data, dict) and isinstance(data.get("messages"), list):
            return data["messages"]
        return []


    
    async def send_read_receipt(self, recipient: str, timestamp: int) -> dict:
        """Send a read receipt for a message."""
        try:
            response = await self._client.post(
                f"/v1/receipts/{recipient}",
                json={
                    "receiptType": "read",
                    "timestamp": timestamp,
                    "recipient": recipient
                }
            )
            
            if response.status_code == 204:
                return {
                    "status": 204,
                    "success": True,
                    "message": "Read receipt sent"
                }
            
            return response.json()
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }