from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import json

from app.auth.deps import get_current_user, get_db
from app.core.models import ContactCreate
from app.core.capabilities import Platform
from app.core.models import Contact as ContactOut, capabilities_for
from app.db.models import Contact as ContactOrm, User

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("", response_model=list[ContactOut])
async def list_contacts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ContactOut]:
    rows = (await db.scalars(select(ContactOrm).where(ContactOrm.user_id == user.id))).all()
    return [
        ContactOut(
            id=str(c.id),
            platform=Platform(c.platform),
            target=c.target,
            display_name=c.display_name or "",
            display_number=c.display_number or "",
            capabilities=capabilities_for(Platform(c.platform)),
        )
        for c in rows
    ]


@router.post("", response_model=ContactOut)
async def create_contact(
    payload: ContactCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContactOut:
    c = ContactOrm(
        user_id=user.id,
        platform=payload.platform.value,
        target=payload.target,
        display_name=payload.display_name,
        display_number=payload.display_number,
        avatar_url=payload.avatar_url,
        platform_meta_json=json.dumps(payload.platform_meta or {}, ensure_ascii=False),
    )
    db.add(c)
    await db.commit()
    await db.refresh(c)

    return ContactOut(
        id=str(c.id),
        platform=payload.platform,
        target=c.target,
        display_name=c.display_name or "",
        display_number=c.display_number or "",
        platform_meta=json.loads(c.platform_meta_json or "{}"),
        capabilities=capabilities_for(payload.platform),
    )


@router.delete("/{contact_id}")
async def delete_contact(
    contact_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    c = await db.scalar(select(ContactOrm).where(ContactOrm.id == contact_id, ContactOrm.user_id == user.id))
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")
    await db.delete(c)
    await db.commit()
    return {"ok": True}
