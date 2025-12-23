import asyncio
import json
from typing import Any

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._by_user: dict[int, set[WebSocket]] = {}

    async def connect(self, ws: WebSocket, user_id: int) -> None:
        await ws.accept()
        async with self._lock:
            if user_id not in self._by_user:
                self._by_user[user_id] = set()
            self._by_user.setdefault(user_id, set()).add(ws)

    async def disconnect(self, user_id: int, ws: WebSocket) -> None:
        async with self._lock:
            if user_id in self._by_user:
                self._by_user[user_id].discard(ws)
                if not self._by_user[user_id]:
                    self._by_user.pop(user_id, None)

    async def broadcast_to_user(self, user_id: int, event: dict[str, Any]) -> None:
        message = json.dumps(event, ensure_ascii=False)
        async with self._lock:
            clients = list(self._by_user.get(user_id, set()))

        
        dead: list[WebSocket] = []
        for ws in clients:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                s = self._by_user.get(user_id)
                if s:
                    for ws in dead:
                        s.discard(ws)


ws_manager = WebSocketManager()
