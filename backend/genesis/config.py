"""Application configuration with startup validation."""

import logging
import sys

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Genesis SaaS configuration."""

    # App
    app_name: str = "Genesis SaaS"
    debug: bool = False  # Default OFF — must explicitly enable
    cors_origins: list[str] = ["http://localhost:3000"]

    # Database (SQLite for dev, PostgreSQL for production)
    database_url: str = "sqlite+aiosqlite:///genesis.db"
    database_echo: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24

    # Anthropic
    anthropic_api_key: str = ""

    # Supervisor
    max_concurrent_builds: int = 5
    default_cost_cap_usd: float = 50.0

    # Rate limiting
    auth_rate_limit: int = 10  # max login attempts per minute per IP

    model_config = {"env_prefix": "GENESIS_", "env_file": ".env"}


settings = Settings()


def validate_settings() -> None:
    """Validate critical settings at startup. Warns or fails for unsafe configs."""
    warnings = []
    errors = []

    if settings.jwt_secret == "change-me-in-production":
        if settings.debug:
            warnings.append("JWT secret is default — OK for dev, CHANGE for production")
        else:
            errors.append(
                "GENESIS_JWT_SECRET is set to default value. "
                "Set a secure random secret: python -c \"import secrets; print(secrets.token_hex(32))\""
            )

    if not settings.debug and settings.database_url.startswith("sqlite"):
        warnings.append("Using SQLite in non-debug mode — use PostgreSQL for production")

    if settings.debug:
        warnings.append("Debug mode is ON — disable for production (GENESIS_DEBUG=false)")

    for w in warnings:
        logger.warning("CONFIG WARNING: %s", w)

    if errors:
        for e in errors:
            logger.error("CONFIG ERROR: %s", e)
        if not settings.debug:
            print("\n".join(f"FATAL: {e}" for e in errors), file=sys.stderr)
            sys.exit(1)


# Validate on import (startup)
validate_settings()
