import asyncio
from fastapi import Request
from app.notifications.mailer import send_email_background
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, get_db
from app.auth.security import create_access_token, hash_password, verify_password
from app.db.models import User
from app.engine.runtime import engine_runtime
from app.settings import settings

from app.notifications.admin_notify import notify_admin_login
import time

router = APIRouter(prefix="/auth", tags=["auth"])



class RegisterIn(BaseModel):
    email: EmailStr
    user_name: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_\.]+$")
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    identifier: str = Field(
        ...,
        description="Email or user_name",
        min_length=3,
        max_length=320,
    )
    password: str = Field(min_length=8, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeOut(BaseModel):
    id: int
    email: EmailStr
    user_name: str

@router.post("/register", response_model=TokenOut)
async def register(payload: RegisterIn, db: AsyncSession = Depends(get_db)) -> TokenOut:
    # Check email uniqueness
    existing_email = await db.scalar(select(User).where(User.email == payload.email))
    if existing_email:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Check username uniqueness
    existing_un = await db.scalar(select(User).where(User.user_name == payload.user_name))
    if existing_un:
        raise HTTPException(status_code=409, detail="Username already taken")

    user = User(
        email=payload.email,
        user_name=payload.user_name,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(subject=str(user.id), expires_minutes=settings.jwt_expires_minutes)
    return TokenOut(access_token=token)


@router.post("/login", response_model=TokenOut)
async def login(payload: LoginIn, request: Request, db: AsyncSession = Depends(get_db)) -> TokenOut:
    user = await db.scalar(
        select(User).where(or_(User.email == payload.identifier, User.user_name == payload.identifier))
    )
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    
    
    token = create_access_token(subject=str(user.id), expires_minutes=settings.jwt_expires_minutes)
    notify_admin_login(user_email=user.email, user_id=user.id, when_ms=int(time.time() * 1000))
    return TokenOut(access_token=token)


@router.get("/me", response_model=MeOut)
async def me(user: User = Depends(get_current_user)) -> MeOut:
    return MeOut(id=user.id, email=user.email, user_name=user.user_name)