from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TrackerPoint as TrackerPointOrm


class TrackerPointsRepo:
    async def add_point(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        contact_id: int,
        device_id: str,
        state: str,
        timestamp_ms: int,
        rtt_ms: float,
        avg_ms: float,
        median_ms: float,
        threshold_ms: float,
    ) -> None:
        db.add(
            TrackerPointOrm(
                user_id=user_id,
                contact_id=contact_id,
                device_id=device_id,
                state=state,
                timestamp_ms=timestamp_ms,
                rtt_ms=rtt_ms,
                avg_ms=avg_ms,
                median_ms=median_ms,
                threshold_ms=threshold_ms,
            )
        )
        await db.commit()
