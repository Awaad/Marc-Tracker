import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from sqlalchemy import select

from app.core.capabilities import Platform
from app.core.models import Contact as ContactOut, capabilities_for
from app.db.models import Contact as ContactOrm, User
from app.db.session import SessionLocal
from app.realtime.manager import ws_manager
from app.settings import settings
import logging


log = logging.getLogger("app.ws")
router = APIRouter(tags=["stream"])


async def _auth_ws_and_load_user(ws: WebSocket) -> User:
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=1008, reason="missing token")
        raise RuntimeError("No token")

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        sub = payload.get("sub")
        user_id = int(sub)
    except (JWTError, TypeError, ValueError):
        await ws.close(code=1008, reason="bad token")
        raise RuntimeError("Bad token")

    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.id == user_id))
        if not user:
            await ws.close(code=1008, reason="user not found")
            raise RuntimeError("No user")
        return user
    
def coerce_platform(raw) -> Platform:
    if isinstance(raw, Platform):
        return raw
    s = str(raw)
    if s.startswith("Platform."):
        s = s.split(".", 1)[1]
    try:
        return Platform(s)
    except Exception:
        return Platform.whatsapp_web


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    try:
        user = await _auth_ws_and_load_user(ws)
    except RuntimeError:
        return
    await ws.accept()
    

    await ws_manager.connect(user.id, ws)

    try:
            await ws.send_text(json.dumps({"type": "ws:direct-test", "ok": True}))
            await ws_manager.broadcast_to_user(user.id, {"type": "ws:broadcast-test", "ok": True})

            async with SessionLocal() as db:
                rows = (await db.scalars(select(ContactOrm).where(ContactOrm.user_id == user.id))).all()

            contacts = []
            for c in rows:
                p = coerce_platform(c.platform)
                contacts.append(
                    ContactOut(
                        id=str(c.id),
                        platform=p,
                        target=c.target,
                        display_name=c.display_name or "",
                        display_number=c.display_number or "",
                        capabilities=capabilities_for(p),
                    ).model_dump()
                )

            await ws.send_text(json.dumps({"type": "contacts:init", "contacts": contacts}))

            while True:
                text = await ws.receive_text()
                if text == "ping":
                    await ws.send_text("pong")
                    continue

    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("ws handler crashed", extra={"user_id": getattr(user, "id", None)})
        try:
            await ws.close(code=1011, reason="server error")
        except Exception:
            pass
    finally:
        await ws_manager.disconnect(user.id, ws)