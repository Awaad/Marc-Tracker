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


router = APIRouter(tags=["stream"])


async def _auth_ws_and_load_user(ws: WebSocket) -> User:
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=1008)
        raise RuntimeError("No token")

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        sub = payload.get("sub")
        user_id = int(sub)
    except (JWTError, TypeError, ValueError):
        await ws.close(code=1008)
        raise RuntimeError("Bad token")

    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.id == user_id))
        if not user:
            await ws.close(code=1008)
            raise RuntimeError("No user")
        return user
    

@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    try:
        user = await _auth_ws_and_load_user(ws)
    except RuntimeError:
        return
    ws.state.user = user

    await ws_manager.connect(ws)
    try:
        # Send initial contacts list
        async with SessionLocal() as db:
            rows = (await db.scalars(select(ContactOrm).where(ContactOrm.user_id == user.id))).all()
            contacts = [
                ContactOut(
                    id=str(c.id),
                    platform=Platform(c.platform),
                    target=c.target,
                    display_name=c.display_name or "",
                    display_number=c.display_number or "",
                    capabilities=capabilities_for(Platform(c.platform)),
                ).model_dump()
                for c in rows
            ]

        await ws.send_text(json.dumps({"type": "contacts:init", "contacts": contacts}))

        while True:
            # keepalive / optional client messages later
            await ws.receive_text()

    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(ws)
