from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TrackerPoint as TrackerPointOrm


class TrackerReadRepo:
    async def get_recent_points(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        contact_id: int,
        limit: int,
    ) -> list[TrackerPointOrm]:
        stmt = (
            select(TrackerPointOrm)
            .where(TrackerPointOrm.user_id == user_id, TrackerPointOrm.contact_id == contact_id)
            .order_by(desc(TrackerPointOrm.timestamp_ms))
            .limit(limit)
        )
        rows = (await db.scalars(stmt)).all()
        # return ascending time for charts
        return list(reversed(rows))

    async def get_latest_point(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        contact_id: int,
    ) -> TrackerPointOrm | None:
        stmt = (
            select(TrackerPointOrm)
            .where(TrackerPointOrm.user_id == user_id, TrackerPointOrm.contact_id == contact_id)
            .order_by(desc(TrackerPointOrm.timestamp_ms))
            .limit(1)
        )
        return await db.scalar(stmt)
