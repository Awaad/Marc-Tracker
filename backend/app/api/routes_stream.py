from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.realtime.manager import ws_manager

router = APIRouter(tags=["stream"])


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws_manager.connect(ws)
    try:
        # For now, we only push server->client events.
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(ws)
