from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, get_db
from app.db.models import Contact as ContactOrm, User
from app.engine.runtime import engine_runtime

from contextlib import asynccontextmanager

from app.adapters.mock import MockAdapter
from app.db.session import SessionLocal
from app.engine.runner import ContactRunner

from app.adapters.hub import adapter_hub
from app.core.capabilities import Platform


router = APIRouter(prefix="/tracking", tags=["tracking"])

@asynccontextmanager
async def session_scope():
    async with SessionLocal() as db:
        yield db


def coerce_platform(raw: object) -> Platform:
    # raw is commonly a string from DB
    if isinstance(raw, Platform):
        return raw
    if isinstance(raw, str):
        try:
            return Platform(raw)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unsupported platform: {raw}")
    raise HTTPException(status_code=400, detail=f"Invalid platform type: {type(raw)}")


def parse_platform_from_request(query_platform: str | None, body: dict | None) -> str | None:
    if query_platform:
        return query_platform
    if body and isinstance(body, dict):
        v = body.get("platform")
        if isinstance(v, str):
            return v
    return None


@router.post("/{contact_id}/start")
async def start_tracking(
    contact_id: int,
    platform: str | None = Query(default=None),
    body: dict | None = Body(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    contact = await db.scalar(select(ContactOrm).where(ContactOrm.id == contact_id, ContactOrm.user_id == user.id))
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    requested = parse_platform_from_request(platform, body)

    # default keeps prior behavior (use contact.platform)
    if not requested:
        requested = str(getattr(contact, "platform", ""))

    if requested == "all":
        # Start all platforms that are registered in adapter_hub.
        # (we can add any extra filters here: e. exclude WhatsApp Cloud if you keep it disabled.)
        to_start: list[Platform] = [p for p in Platform if adapter_hub.supports(p)]
    else:
        to_start = [coerce_platform(requested)]
    
    started: list[str] = []
    for plat in to_start:
        # Validate adapter is available BEFORE scheduling background runner
        if not adapter_hub.supports(plat):
            raise HTTPException(
                status_code=400,
                detail=f"Adapter not available for platform '{plat.value}' (disabled or not registered)",
            )

    async def runner(p: Platform = plat) -> None:
        adapter = adapter_hub.create(p, user.id, contact.id)
        
        try:
            cr = ContactRunner(
                adapter=adapter,
                correlator=engine_runtime.correlator,
                points_repo=engine_runtime.points_repo,
                db_factory=session_scope,
                user_id=user.id,
                contact_id=contact.id,
                platform=platform.value,
                timeout_ms=10_000,
            )
            await cr.run()
        finally:
            await adapter.close()

    await engine_runtime.tracking.start_platform(user.id, contact.id, plat.value, runner)
    started.append(plat.value)
    return {"ok": True}


@router.post("/{contact_id}/stop")
async def stop_tracking(
    contact_id: int,
    platform: str | None = Query(default=None),
    body: dict | None = Body(default=None),
    user: User = Depends(get_current_user),
) -> dict:
    requested = parse_platform_from_request(platform, body)
    if requested == "all" or not requested:
        await engine_runtime.tracking.stop_all_for_contact(user.id, contact_id)
        return {"ok": True, "stopped": "all"}

    plat = coerce_platform(requested)
    await engine_runtime.tracking.stop_platform(user.id, contact_id, plat.value)
    return {"ok": True, "stopped": plat.value}
 

@router.get("/running")
async def running(user: User = Depends(get_current_user)) -> dict:
    running_map = await engine_runtime.tracking.list_running(user.id)
    # JSON: keys must be strings
    return {"running": {str(cid): platforms for cid, platforms in running_map.items()}}


@router.get("/{contact_id}/status")
async def status(
    contact_id: int,
    platform: str | None = Query(default=None),
    user: User = Depends(get_current_user),
) -> dict:
    if platform:
        plat = coerce_platform(platform)
        is_running = await engine_runtime.tracking.is_running_platform(user.id, contact_id, plat.value)
        return {"contact_id": contact_id, "platform": plat.value, "running": is_running}

    is_running_any = await engine_runtime.tracking.is_running(user.id, contact_id)
    return {"contact_id": contact_id, "running": is_running_any}