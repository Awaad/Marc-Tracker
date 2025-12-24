from fastapi import APIRouter, Depends, HTTPException
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


@router.post("/{contact_id}/start")
async def start_tracking(
    contact_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    contact = await db.scalar(select(ContactOrm).where(ContactOrm.id == contact_id, ContactOrm.user_id == user.id))
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    # For now, only wire mock in a clean, deterministic way.
    # Next we’ll add Signal + WhatsApp adapters and choose based on contact.platform.
    platform = contact.platform

    async def runner() -> None:
        try:
            adapter = adapter_hub.create(platform, user.id, contact.id)
        except RuntimeError as e:
            # log and stop quickly
            raise RuntimeError(str(e))
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

    await engine_runtime.tracking.start(user.id, contact.id, runner)
    return {"ok": True}


@router.post("/{contact_id}/stop")
async def stop_tracking(contact_id: int, user: User = Depends(get_current_user)) -> dict:
    await engine_runtime.tracking.stop(user.id, contact_id)
    return {"ok": True}


@router.get("/running")
async def running(user: User = Depends(get_current_user)) -> dict:
    contact_ids = await engine_runtime.tracking.list_running(user.id)
    return {"contact_ids": contact_ids}


@router.get("/{contact_id}/status")
async def status(contact_id: int, user: User = Depends(get_current_user)) -> dict:
    is_running = await engine_runtime.tracking.is_running(user.id, contact_id)
    return {"contact_id": contact_id, "running": is_running}
