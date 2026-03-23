"""Tenant settings API — API key management, preferences."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from genesis.auth.middleware import CurrentUser, get_current_user
from genesis.db.models import Tenant
from genesis.db.session import get_session

router = APIRouter()


class ApiKeyRequest(BaseModel):
    api_key: str = Field(..., min_length=10, max_length=200)


class ApiKeyStatus(BaseModel):
    has_key: bool
    key_preview: str  # "sk-ant-...xyz"
    auth_method: str


class SettingsResponse(BaseModel):
    tenant_id: str
    tenant_name: str
    plan: str
    credits_used: float
    credits_limit: float
    max_concurrent_builds: int
    has_api_key: bool
    api_key_preview: str
    auth_method: str


def _key_preview(key: str | None) -> str:
    if not key:
        return ""
    if len(key) > 10:
        return f"{key[:7]}...{key[-4:]}"
    return "***"


@router.get("", response_model=SettingsResponse)
async def get_settings(
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get current tenant settings."""
    tenant = current.tenant
    return SettingsResponse(
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        plan=tenant.plan,
        credits_used=tenant.credits_used,
        credits_limit=tenant.credits_limit,
        max_concurrent_builds=tenant.max_concurrent_builds,
        has_api_key=bool(tenant.anthropic_api_key),
        api_key_preview=_key_preview(tenant.anthropic_api_key),
        auth_method=tenant.claude_auth_method,
    )


@router.post("/api-key", response_model=ApiKeyStatus)
async def set_api_key(
    body: ApiKeyRequest,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Set the Anthropic API key for this tenant.

    This key is used by all Claude Agent SDK calls for this tenant's builds.
    The key is stored per-tenant and passed via env to the SDK.
    """
    if not current.user.is_admin:
        raise HTTPException(403, "Only tenant admins can set the API key")

    tenant = await db.get(Tenant, current.tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")

    tenant.anthropic_api_key = body.api_key
    tenant.claude_auth_method = "api_key"
    await db.flush()

    return ApiKeyStatus(
        has_key=True,
        key_preview=_key_preview(body.api_key),
        auth_method="api_key",
    )


@router.delete("/api-key")
async def remove_api_key(
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Remove the API key for this tenant."""
    if not current.user.is_admin:
        raise HTTPException(403, "Only tenant admins can remove the API key")

    tenant = await db.get(Tenant, current.tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")

    tenant.anthropic_api_key = None
    await db.flush()

    return {"status": "removed"}


@router.post("/sync-claude-credentials")
async def sync_claude_credentials(
    body: dict,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Sync Claude Max/Pro credentials from your local Claude Code CLI.

    Accepts the full credentials JSON from the keychain.
    Run locally: security find-generic-password -s "Claude Code-credentials" -w
    """
    if not current.user.is_admin:
        raise HTTPException(403, "Only tenant admins can sync credentials")

    from genesis.auth.token_manager import parse_claude_credentials, token_status

    creds = parse_claude_credentials(json.dumps(body) if isinstance(body, dict) else body)
    if not creds or not creds["access_token"]:
        raise HTTPException(400, "Invalid credentials format")

    tenant = await db.get(Tenant, current.tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")

    tenant.anthropic_api_key = creds["access_token"]
    tenant.claude_auth_method = "max_pro"
    await db.flush()

    status = token_status(creds["expires_at"])

    return {
        "status": "synced",
        "subscription": creds["subscription_type"],
        "token_status": status,
        "expires_at": creds["expires_at"],
    }


@router.get("/token-status")
async def get_token_status(
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Check the status of the Claude auth token (valid/expiring/expired)."""
    tenant = await db.get(Tenant, current.tenant_id)
    if not tenant or not tenant.anthropic_api_key:
        return {"status": "no_token", "message": "No Claude auth configured"}

    # Test with a real call
    try:
        from genesis.agents.claude_client import run_agent
        result = await run_agent(
            prompt="Say OK",
            model="haiku",
            max_turns=1,
            api_key=tenant.anthropic_api_key,
        )
        return {
            "status": "valid",
            "message": "Claude connected",
            "response": result.result,
            "auth_method": tenant.claude_auth_method,
        }
    except Exception as e:
        error_msg = str(e)[:200]
        if "expired" in error_msg.lower() or "unauthorized" in error_msg.lower() or "401" in error_msg:
            return {"status": "expired", "message": "Token expired — sync fresh credentials"}
        return {"status": "error", "message": error_msg}


@router.post("/test-connection")
async def test_connection(
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Test that Claude is connected and responding."""
    tenant = await db.get(Tenant, current.tenant_id)
    if not tenant or not tenant.anthropic_api_key:
        raise HTTPException(400, "No Claude auth configured — set API key or sync Claude Max credentials")

    try:
        from genesis.agents.claude_client import run_agent
        result = await run_agent(
            prompt="Say 'Genesis connected!' and nothing else.",
            model="haiku",
            max_turns=1,
            api_key=tenant.anthropic_api_key,
        )
        return {
            "status": "connected",
            "response": result.result,
            "model": "haiku",
            "cost_usd": result.total_cost_usd,
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)[:200],
        }
