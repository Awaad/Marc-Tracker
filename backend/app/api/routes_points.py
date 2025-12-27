from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, get_db
from app.core.models import TrackerPoint
from app.db.models import Contact as ContactOrm, User
from app.storage.read_repo import TrackerReadRepo

router = APIRouter(prefix="/contacts", tags=["points"])

repo = TrackerReadRepo()


@router.get("/{contact_id}/points", response_model=list[TrackerPoint])
async def recent_points(
    contact_id: int,
    limit: int = Query(default=1000, ge=1, le=5000),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TrackerPoint]:
    # ensure contact belongs to user
    contact = await db.scalar(select(ContactOrm).where(ContactOrm.id == contact_id, ContactOrm.user_id == user.id))
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    rows = await repo.get_recent_points(db, user_id=user.id, contact_id=contact_id, limit=limit)
    return [
        TrackerPoint(
            timestamp_ms=r.timestamp_ms,
            device_id=r.device_id,
            state=r.state,  # type: ignore[arg-type]
            rtt_ms=r.rtt_ms,
            avg_ms=r.avg_ms,
            median_ms=r.median_ms,
            threshold_ms=r.threshold_ms,
        )
        for r in rows
    ]


@router.get("/{contact_id}/points/latest", response_model=TrackerPoint | None)
async def latest_point(
    contact_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TrackerPoint | None:
    contact = await db.scalar(select(ContactOrm).where(ContactOrm.id == contact_id, ContactOrm.user_id == user.id))
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    r = await repo.get_latest_point(db, user_id=user.id, contact_id=contact_id)
    if not r:
        return None

    return TrackerPoint(
        timestamp_ms=r.timestamp_ms,
        device_id=r.device_id,
        state=r.state,  # type: ignore[arg-type]
        rtt_ms=r.rtt_ms,
        avg_ms=r.avg_ms,
        median_ms=r.median_ms,
        threshold_ms=r.threshold_ms,
    )
