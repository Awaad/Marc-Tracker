from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, get_db
from app.core.models import PlatformProbeOut
from app.db.models import Contact as ContactOrm, PlatformProbe, User

router = APIRouter(prefix="/contacts", tags=["probes"])


@router.get("/{contact_id}/probes", response_model=list[PlatformProbeOut])
async def list_probes(
    contact_id: int,
    limit: int = Query(default=200, ge=1, le=5000),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlatformProbeOut]:
    contact = await db.scalar(select(ContactOrm).where(ContactOrm.id == contact_id, ContactOrm.user_id == user.id))
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    stmt = (
        select(PlatformProbe)
        .where(PlatformProbe.user_id == user.id, PlatformProbe.contact_id == contact_id)
        .order_by(desc(PlatformProbe.sent_at_ms))
        .limit(limit)
    )
    rows = (await db.scalars(stmt)).all()
    rows = list(reversed(rows))  # ascending for UI

    out: list[PlatformProbeOut] = []
    for r in rows:
        delivery_lag = (r.delivered_at_ms - r.sent_at_ms) if r.delivered_at_ms else None
        read_lag = (r.read_at_ms - r.sent_at_ms) if r.read_at_ms else None
        out.append(
            PlatformProbeOut(
                platform=r.platform,
                probe_id=r.probe_id,
                sent_at_ms=r.sent_at_ms,
                platform_message_ts=r.platform_message_ts,
                delivered_at_ms=r.delivered_at_ms,
                read_at_ms=r.read_at_ms,
                delivery_lag_ms=delivery_lag,
                read_lag_ms=read_lag,
            )
        )
    return out


@router.get("/{contact_id}/probes/latest", response_model=PlatformProbeOut | None)
async def latest_probe(
    contact_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformProbeOut | None:
    contact = await db.scalar(select(ContactOrm).where(ContactOrm.id == contact_id, ContactOrm.user_id == user.id))
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    stmt = (
        select(PlatformProbe)
        .where(PlatformProbe.user_id == user.id, PlatformProbe.contact_id == contact_id)
        .order_by(desc(PlatformProbe.sent_at_ms))
        .limit(1)
    )
    r = await db.scalar(stmt)
    if not r:
        return None

    delivery_lag = (r.delivered_at_ms - r.sent_at_ms) if r.delivered_at_ms else None
    read_lag = (r.read_at_ms - r.sent_at_ms) if r.read_at_ms else None
    return PlatformProbeOut(
        platform=r.platform,
        probe_id=r.probe_id,
        sent_at_ms=r.sent_at_ms,
        platform_message_ts=r.platform_message_ts,
        delivered_at_ms=r.delivered_at_ms,
        read_at_ms=r.read_at_ms,
        delivery_lag_ms=delivery_lag,
        read_lag_ms=read_lag,
    )
