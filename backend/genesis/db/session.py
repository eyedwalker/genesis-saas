"""Async database session management with tenant context for RLS."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from genesis.config import settings

_is_sqlite = settings.database_url.startswith("sqlite")

engine_kwargs: dict = {
    "echo": settings.database_echo,
}
if not _is_sqlite:
    engine_kwargs["pool_size"] = 20
    engine_kwargs["max_overflow"] = 10

engine = create_async_engine(settings.database_url, **engine_kwargs)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session.

    Note: For RLS, use get_tenant_session() instead — it sets the
    tenant context on the connection before any queries.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_tenant_session(tenant_id: str) -> AsyncGenerator[AsyncSession, None]:
    """Get a session with tenant context set for RLS.

    Sets app.current_tenant_id on the PostgreSQL connection so RLS
    policies filter rows automatically.
    """
    async with async_session_factory() as session:
        try:
            # Set tenant context for RLS (PostgreSQL only)
            from genesis.db.rls import set_tenant_context
            await set_tenant_context(session, tenant_id)
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
