from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, get_db
from app.db.models import Contact as ContactOrm, User
from app.engine.runtime import engine_runtime

router = APIRouter(prefix="/tracking", tags=["tracking"])


@router.post("/{contact_id}/start")
async def start_tracking(
    contact_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    contact = await db.scalar(select(ContactOrm).where(ContactOrm.id == contact_id, ContactOrm.user_id == user.id))
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    # For now: we can't start without an adapter instance; next we will provide a mock adapter
    return {"ok": True, "note": "adapter not wired yet"}


@router.post("/{contact_id}/stop")
async def stop_tracking(contact_id: int, user: User = Depends(get_current_user)) -> dict:
    await engine_runtime.tracking.stop(user.id, contact_id)
    return {"ok": True}
