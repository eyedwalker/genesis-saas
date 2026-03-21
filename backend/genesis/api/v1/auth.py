"""Auth endpoints — register, login, me. With rate limiting and validation."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from genesis.auth.middleware import (
    CurrentUser,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from genesis.auth.rate_limit import check_rate_limit
from genesis.db.models import Tenant, TenantUser
from genesis.db.session import get_session

router = APIRouter()


# ── Schemas with validation ───────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    tenant_name: str = Field(..., min_length=2, max_length=100)
    tenant_slug: str = Field(..., min_length=2, max_length=50)
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(default="", max_length=100)

    @field_validator("tenant_slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", v):
            raise ValueError("Slug must be lowercase alphanumeric with hyphens")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email format")
        return v.lower().strip()


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., max_length=128)
    tenant_slug: str = Field(..., max_length=50)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: str
    user_id: str
    email: str


class MeResponse(BaseModel):
    user_id: str
    tenant_id: str
    tenant_name: str
    email: str
    name: str
    is_admin: bool


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.post("/register", response_model=TokenResponse)
async def register(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    """Register a new tenant + admin user."""
    check_rate_limit(request)

    existing = await db.execute(
        select(Tenant).where(Tenant.slug == body.tenant_slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Tenant slug already taken")

    tenant = Tenant(name=body.tenant_name, slug=body.tenant_slug)
    db.add(tenant)
    await db.flush()

    user = TenantUser(
        tenant_id=tenant.id,
        email=body.email,
        name=body.name,
        hashed_password=hash_password(body.password),
        is_admin=True,
    )
    db.add(user)
    await db.flush()

    token = create_access_token(user.id, tenant.id, user.email)
    return TokenResponse(
        access_token=token,
        tenant_id=tenant.id,
        user_id=user.id,
        email=user.email,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    """Login with email + password + tenant slug."""
    check_rate_limit(request)

    tenant = (
        await db.execute(select(Tenant).where(Tenant.slug == body.tenant_slug))
    ).scalar_one_or_none()
    if not tenant:
        raise HTTPException(401, "Invalid credentials")

    user = (
        await db.execute(
            select(TenantUser).where(
                TenantUser.tenant_id == tenant.id,
                TenantUser.email == body.email,
            )
        )
    ).scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(401, "Invalid credentials")

    token = create_access_token(user.id, tenant.id, user.email)
    return TokenResponse(
        access_token=token,
        tenant_id=tenant.id,
        user_id=user.id,
        email=user.email,
    )


@router.get("/me", response_model=MeResponse)
async def me(current: CurrentUser = Depends(get_current_user)):
    """Get current user info."""
    return MeResponse(
        user_id=current.user.id,
        tenant_id=current.tenant.id,
        tenant_name=current.tenant.name,
        email=current.user.email,
        name=current.user.name,
        is_admin=current.user.is_admin,
    )
