"""Tenant-aware JWT authentication."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import hashlib

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from genesis.config import settings
from genesis.db.models import Tenant, TenantUser
from genesis.db.session import get_session

security = HTTPBearer()


def hash_password(password: str) -> str:
    """Hash password using SHA-256 with salt. Production should use bcrypt."""
    import secrets
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return f"{salt}${hashed}"


def verify_password(plain: str, hashed: str) -> bool:
    if "$" not in hashed:
        return False
    salt, hash_val = hashed.split("$", 1)
    return hashlib.sha256(f"{salt}:{plain}".encode()).hexdigest() == hash_val


def create_access_token(
    user_id: str,
    tenant_id: str,
    email: str,
    extra: dict[str, Any] | None = None,
) -> str:
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(hours=settings.jwt_expiry_hours),
        **(extra or {}),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


class CurrentUser:
    """Resolved user + tenant from JWT."""

    def __init__(self, user: TenantUser, tenant: Tenant) -> None:
        self.user = user
        self.tenant = tenant

    @property
    def user_id(self) -> str:
        return self.user.id

    @property
    def tenant_id(self) -> str:
        return self.tenant.id

    @property
    def email(self) -> str:
        return self.user.email


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_session),
) -> CurrentUser:
    """FastAPI dependency: extracts and validates JWT, returns user + tenant."""
    payload = decode_token(creds.credentials)
    user_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")
    if not user_id or not tenant_id:
        raise HTTPException(status_code=401, detail="Malformed token")

    user = await db.get(TenantUser, user_id)
    if not user or user.tenant_id != tenant_id:
        raise HTTPException(status_code=401, detail="User not found")

    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=401, detail="Tenant not found")

    return CurrentUser(user=user, tenant=tenant)


async def get_current_tenant(
    current_user: CurrentUser = Depends(get_current_user),
) -> Tenant:
    """Convenience dependency: returns just the tenant."""
    return current_user.tenant
