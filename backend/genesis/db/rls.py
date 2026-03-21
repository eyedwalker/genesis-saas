"""PostgreSQL Row-Level Security (RLS) policies.

Defense-in-depth: Even if application code has a bug and misses a
WHERE tenant_id = ? clause, the database itself will prevent cross-tenant
data access.

Usage:
    Run apply_rls_policies() during application startup (after tables exist).
    Each DB connection must SET app.current_tenant_id before queries.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# All tables that have tenant_id and need RLS
RLS_TABLES = [
    "tenant_users",
    "factories",
    "factory_members",
    "builds",
    "approvals",
    "build_comments",
    "activities",
    "work_items",
    "documents",
    "deployments",
    "invitations",
    "assistants",
    "tenant_assistant_configs",
]


async def apply_rls_policies(session: AsyncSession) -> None:
    """Apply Row-Level Security policies to all tenant-scoped tables.

    Each table gets:
    1. RLS enabled
    2. A policy that only allows access to rows where
       tenant_id = current_setting('app.current_tenant_id')
    3. The policy applies to ALL operations (SELECT, INSERT, UPDATE, DELETE)

    The app user must SET app.current_tenant_id = 'xxx' on each connection.
    """
    for table in RLS_TABLES:
        try:
            # Enable RLS on table
            await session.execute(text(
                f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"
            ))

            # Force RLS even for table owners (important!)
            await session.execute(text(
                f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"
            ))

            # Drop existing policy if any
            await session.execute(text(
                f"DROP POLICY IF EXISTS tenant_isolation ON {table}"
            ))

            # Create tenant isolation policy
            await session.execute(text(f"""
                CREATE POLICY tenant_isolation ON {table}
                USING (tenant_id = current_setting('app.current_tenant_id', true))
                WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true))
            """))

            logger.info("RLS policy applied to %s", table)
        except Exception as e:
            # SQLite doesn't support RLS — skip silently
            if "syntax error" in str(e).lower() or "not supported" in str(e).lower():
                logger.debug("RLS not supported (SQLite?), skipping %s", table)
                return
            logger.warning("Failed to apply RLS to %s: %s", table, e)

    await session.commit()
    logger.info("RLS policies applied to %d tables", len(RLS_TABLES))


async def set_tenant_context(session: AsyncSession, tenant_id: str) -> None:
    """Set the current tenant context for RLS.

    Must be called on every database session before queries.
    This is integrated into the FastAPI dependency injection.
    """
    try:
        await session.execute(
            text("SET LOCAL app.current_tenant_id = :tid"),
            {"tid": tenant_id},
        )
    except Exception:
        # SQLite doesn't support SET — skip
        pass
