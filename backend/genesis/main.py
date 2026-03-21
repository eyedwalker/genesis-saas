"""Genesis SaaS — FastAPI application."""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from genesis.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown events."""
    # Startup: verify DB connection, seed data if needed
    from genesis.db.session import engine

    async with engine.begin() as conn:
        # Import models so they're registered
        from genesis.db.models import Base

        # In dev, auto-create tables (use Alembic in prod)
        if settings.debug:
            await conn.run_sync(Base.metadata.create_all)

    yield

    # Shutdown
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ─────────────────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "genesis-saas"}


# ── Register API routers ──────────────────────────────────────────────────────

from genesis.api.v1.auth import router as auth_router  # noqa: E402
from genesis.api.v1.factories import router as factories_router  # noqa: E402
from genesis.api.v1.builds import router as builds_router  # noqa: E402
from genesis.api.v1.supervisor import router as supervisor_router  # noqa: E402
from genesis.api.v1.review import router as review_router  # noqa: E402
from genesis.api.v1.genesis import router as genesis_router  # noqa: E402
from genesis.api.v1.conversation import router as conversation_router  # noqa: E402
from genesis.api.v1.assistants import router as assistants_router  # noqa: E402

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(factories_router, prefix="/api/v1/factories", tags=["factories"])
app.include_router(builds_router, prefix="/api/v1/builds", tags=["builds"])
app.include_router(supervisor_router, prefix="/api/v1/supervisor", tags=["supervisor"])
app.include_router(review_router, prefix="/api/v1/review", tags=["review"])
app.include_router(genesis_router, prefix="/api/v1/genesis", tags=["genesis"])
app.include_router(conversation_router, prefix="/api/v1/conversation", tags=["conversation"])
app.include_router(assistants_router, prefix="/api/v1/assistants", tags=["assistants"])
