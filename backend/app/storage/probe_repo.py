from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PlatformProbe


class ProbeRepo:
    async def insert_probe(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        contact_id: int,
        platform: str,
        probe_id: str,
        sent_at_ms: int,
        platform_message_ts: int | None,
        send_response: dict | None,
    ) -> None:
        db.add(
            PlatformProbe(
                user_id=user_id,
                contact_id=contact_id,
                platform=platform,
                probe_id=probe_id,
                sent_at_ms=sent_at_ms,
                platform_message_ts=platform_message_ts,
                send_response=send_response,
            )
        )
        await db.commit()

    async def find_by_platform_ts(
        self,
        db: AsyncSession,
        *,
        platform: str,
        platform_message_ts: int,
    ) -> PlatformProbe | None:
        stmt = select(PlatformProbe).where(
            PlatformProbe.platform == platform,
            PlatformProbe.platform_message_ts == platform_message_ts,
        )
        return await db.scalar(stmt)

    async def mark_delivered(
        self,
        db: AsyncSession,
        *,
        probe_id: str,
        delivered_at_ms: int,
    ) -> None:
        stmt = (
            update(PlatformProbe)
            .where(PlatformProbe.probe_id == probe_id)
            .values(delivered_at_ms=delivered_at_ms)
        )
        await db.execute(stmt)
        await db.commit()

    async def mark_read(
        self,
        db: AsyncSession,
        *,
        probe_id: str,
        read_at_ms: int,
    ) -> None:
        stmt = (
            update(PlatformProbe)
            .where(PlatformProbe.probe_id == probe_id)
            .values(read_at_ms=read_at_ms)
        )
        await db.execute(stmt)
        await db.commit()

    
