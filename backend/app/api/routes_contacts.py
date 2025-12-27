from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import json
from pydantic import BaseModel

from app.auth.deps import get_current_user, get_db
from app.core.models import ContactCreate
from app.core.capabilities import Platform
from app.core.models import Contact as ContactOut, capabilities_for
from app.db.models import Contact as ContactOrm, User

# to support refresh_profile (safe even if you don't use it yet)
from app.adapters.hub import adapter_hub

router = APIRouter(prefix="/contacts", tags=["contacts"])


class ContactUpdate(BaseModel):
    display_name: str | None = None
    avatar_url: str | None = None
    platform_meta: dict | None = None
    notify_online: bool | None = None



@router.get("", response_model=list[ContactOut])
async def list_contacts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ContactOut]:
    rows = (await db.scalars(select(ContactOrm).where(ContactOrm.user_id == user.id))).all()
    out: list[ContactOut] = []
    for c in rows:
        plat = Platform(c.platform)
        out.append(
            ContactOut(
                id=str(c.id),
                platform=plat,
                target=c.target,
                display_name=c.display_name or "",
                display_number=c.display_number or "",
                avatar_url=c.avatar_url,
                platform_meta=json.loads(c.platform_meta_json or "{}"),
                capabilities=capabilities_for(plat),
                notify_online=bool(getattr(c, "notify_online", False)),
            )
        )
    return out


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
        avatar_url=c.avatar_url,
        platform_meta=json.loads(c.platform_meta_json or "{}"),
        capabilities=capabilities_for(payload.platform),
        notify_online=bool(getattr(c, "notify_online", False)),

    )


# refresh profile from adapter (when adapter supports it)
@router.post("/{contact_id}/refresh_profile", response_model=ContactOut)
async def refresh_profile(
    contact_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContactOut:
    c = await db.scalar(select(ContactOrm).where(ContactOrm.id == contact_id, ContactOrm.user_id == user.id))
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")

    plat = Platform(c.platform)

    # if adapter not available, fail clearly
    if not adapter_hub.supports(plat):
        raise HTTPException(status_code=400, detail=f"Adapter not available for platform '{plat.value}'")

    adapter = adapter_hub.create(plat, user.id, c.id)
    try:
        prof = await adapter.get_profile(user_id=user.id, contact_id=c.id)  # optional hook
        if not prof:
            raise HTTPException(status_code=400, detail=f"Profile fetch not supported for '{plat.value}'")

        # Only update if provided (don't overwrite with empty)
        avatar_url = prof.get("avatar_url")
        display_name = prof.get("display_name")
        status_text = prof.get("status_text")

        if isinstance(avatar_url, str) and avatar_url.strip():
            c.avatar_url = avatar_url.strip()
        if isinstance(display_name, str) and display_name.strip():
            c.display_name = display_name.strip()

        # store extra fields into platform_meta
        meta = json.loads(c.platform_meta_json or "{}")
        if isinstance(status_text, str):
            meta["status_text"] = status_text
        c.platform_meta_json = json.dumps(meta, ensure_ascii=False)

        await db.commit()
        await db.refresh(c)

        return ContactOut(
            id=str(c.id),
            platform=plat,
            target=c.target,
            display_name=c.display_name or "",
            display_number=c.display_number or "",
            avatar_url=c.avatar_url,
            platform_meta=json.loads(c.platform_meta_json or "{}"),
            capabilities=capabilities_for(plat),
        )
    finally:
        await adapter.close()


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


class NotifyOnlineIn(BaseModel):
    enabled: bool

@router.post("/{contact_id}/notify_online")
async def set_notify_online(
    contact_id: int,
    payload: NotifyOnlineIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    c = await db.scalar(select(ContactOrm).where(ContactOrm.id == contact_id, ContactOrm.user_id == user.id))
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")
    c.notify_online = bool(payload.enabled)
    await db.commit()
    return {"ok": True, "enabled": c.notify_online}



@router.patch("/{contact_id}", response_model=ContactOut)
async def update_contact(
    contact_id: int,
    payload: ContactUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContactOut:
    c = await db.scalar(select(ContactOrm).where(ContactOrm.id == contact_id, ContactOrm.user_id == user.id))
    if not c:
        raise HTTPException(status_code=404, detail="Contact not found")

    if payload.display_name is not None:
        c.display_name = payload.display_name
    if payload.avatar_url is not None:
        c.avatar_url = payload.avatar_url
    if payload.platform_meta is not None:
        c.platform_meta_json = json.dumps(payload.platform_meta or {}, ensure_ascii=False)
    if payload.notify_online is not None:
        c.notify_online = bool(payload.notify_online)

    await db.commit()
    await db.refresh(c)

    plat = Platform(c.platform)
    return ContactOut(
        id=str(c.id),
        platform=plat,
        target=c.target,
        display_name=c.display_name or "",
        display_number=c.display_number or "",
        avatar_url=c.avatar_url,
        platform_meta=json.loads(c.platform_meta_json or "{}"),
        notify_online=bool(getattr(c, "notify_online", False)),
        capabilities=capabilities_for(plat),
    )