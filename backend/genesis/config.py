"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Genesis SaaS configuration."""

    # App
    app_name: str = "Genesis SaaS"
    debug: bool = True
    cors_origins: list[str] = ["http://localhost:3000"]

    # Database (defaults to SQLite for local dev; use PostgreSQL in production)
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

    model_config = {"env_prefix": "GENESIS_", "env_file": ".env"}


settings = Settings()
