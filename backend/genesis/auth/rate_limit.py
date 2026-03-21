"""Simple in-memory rate limiter for auth endpoints.

Limits login/register attempts per IP to prevent brute force.
In production, use Redis-backed rate limiting.
"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request

from genesis.config import settings

_attempts: dict[str, list[float]] = defaultdict(list)
_window_seconds = 60


def check_rate_limit(request: Request) -> None:
    """Check rate limit for auth endpoints. Raises 429 if exceeded."""
    ip = request.client.host if request.client else "unknown"
    now = time.time()

    # Clean old entries
    _attempts[ip] = [t for t in _attempts[ip] if now - t < _window_seconds]

    if len(_attempts[ip]) >= settings.auth_rate_limit:
        raise HTTPException(
            status_code=429,
            detail=f"Too many attempts. Try again in {_window_seconds} seconds.",
        )

    _attempts[ip].append(now)
