"""Genesis SaaS — FastAPI application with security hardening."""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from genesis.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: create tables (dev), apply RLS (PostgreSQL)."""
    from genesis.db.session import engine, async_session_factory
    from genesis.db.models import Base

    async with engine.begin() as conn:
        if settings.debug:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Tables auto-created (debug mode)")

    # Apply RLS policies (PostgreSQL only, skipped for SQLite)
    if not settings.database_url.startswith("sqlite"):
        try:
            from genesis.db.rls import apply_rls_policies
            async with async_session_factory() as session:
                await apply_rls_policies(session)
                logger.info("RLS policies applied")
        except Exception as e:
            logger.warning("RLS setup failed (non-fatal): %s", e)

    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url=None,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ── Global error handler — sanitize exceptions ────────────────────────────────


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch unhandled exceptions and return safe error response.

    Never expose internal details, stack traces, or API keys to clients.
    """
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)

    if settings.debug:
        detail = str(exc)[:500]
    else:
        detail = "Internal server error"

    return JSONResponse(
        status_code=500,
        content={"detail": detail, "error_code": "INTERNAL_ERROR"},
    )


# ── Health ─────────────────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "genesis-saas",
        "debug": settings.debug,
    }


# ── Register API routers ──────────────────────────────────────────────────────

from genesis.api.v1.auth import router as auth_router  # noqa: E402
from genesis.api.v1.factories import router as factories_router  # noqa: E402
from genesis.api.v1.builds import router as builds_router  # noqa: E402
from genesis.api.v1.supervisor import router as supervisor_router  # noqa: E402
from genesis.api.v1.review import router as review_router  # noqa: E402
from genesis.api.v1.genesis import router as genesis_router  # noqa: E402
from genesis.api.v1.conversation import router as conversation_router  # noqa: E402
from genesis.api.v1.assistants import router as assistants_router  # noqa: E402
from genesis.api.v1.settings import router as settings_router  # noqa: E402

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(factories_router, prefix="/api/v1/factories", tags=["factories"])
app.include_router(builds_router, prefix="/api/v1/builds", tags=["builds"])
app.include_router(supervisor_router, prefix="/api/v1/supervisor", tags=["supervisor"])
app.include_router(review_router, prefix="/api/v1/review", tags=["review"])
app.include_router(genesis_router, prefix="/api/v1/genesis", tags=["genesis"])
app.include_router(conversation_router, prefix="/api/v1/conversation", tags=["conversation"])
app.include_router(assistants_router, prefix="/api/v1/assistants", tags=["assistants"])
app.include_router(settings_router, prefix="/api/v1/settings", tags=["settings"])
