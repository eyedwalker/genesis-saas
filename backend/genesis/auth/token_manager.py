"""Claude Max/Pro token management.

The Claude Agent SDK uses OAuth tokens from Claude Max/Pro subscriptions.
These tokens expire every ~6 hours. On macOS, the CLI refreshes automatically
via the system keychain. On Linux servers, we need to manage this ourselves.

Strategy:
1. Extract credentials from local keychain (macOS)
2. Store access token + refresh token + expiry in tenant DB
3. Monitor expiry and notify when refresh needed
4. Provide a sync endpoint that accepts fresh credentials from the CLI
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def parse_claude_credentials(creds_json: str) -> dict[str, Any] | None:
    """Parse Claude Code credentials JSON (from keychain or file)."""
    try:
        data = json.loads(creds_json)
        oauth = data.get("claudeAiOauth", {})
        return {
            "access_token": oauth.get("accessToken", ""),
            "refresh_token": oauth.get("refreshToken", ""),
            "expires_at": oauth.get("expiresAt", 0),
            "subscription_type": oauth.get("subscriptionType", ""),
            "rate_limit_tier": oauth.get("rateLimitTier", ""),
            "organization_uuid": data.get("organizationUuid", ""),
            "scopes": oauth.get("scopes", []),
        }
    except (json.JSONDecodeError, KeyError) as e:
        logger.error("Failed to parse Claude credentials: %s", e)
        return None


def is_token_expired(expires_at_ms: int, buffer_minutes: int = 30) -> bool:
    """Check if an OAuth token is expired or about to expire."""
    if not expires_at_ms:
        return True
    expires_at_sec = expires_at_ms / 1000
    now = time.time()
    buffer_sec = buffer_minutes * 60
    return now >= (expires_at_sec - buffer_sec)


def token_status(expires_at_ms: int) -> dict[str, Any]:
    """Get human-readable token status."""
    if not expires_at_ms:
        return {"status": "no_token", "message": "No token configured"}

    now = time.time()
    expires_sec = expires_at_ms / 1000
    remaining_sec = expires_sec - now

    if remaining_sec <= 0:
        return {
            "status": "expired",
            "message": "Token expired",
            "expired_ago_minutes": round(abs(remaining_sec) / 60),
        }
    elif remaining_sec < 1800:  # 30 min
        return {
            "status": "expiring_soon",
            "message": f"Token expires in {round(remaining_sec / 60)} minutes",
            "remaining_minutes": round(remaining_sec / 60),
        }
    elif remaining_sec < 7200:  # 2 hours
        return {
            "status": "valid",
            "message": f"Token valid for {round(remaining_sec / 3600, 1)} hours",
            "remaining_hours": round(remaining_sec / 3600, 1),
        }
    else:
        return {
            "status": "valid",
            "message": f"Token valid for {round(remaining_sec / 3600, 1)} hours",
            "remaining_hours": round(remaining_sec / 3600, 1),
        }
