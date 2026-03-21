"""Factory Supervisor API — manages multiple concurrent builds."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from genesis.auth.middleware import CurrentUser, get_current_user
from genesis.db.models import Build, Factory
from genesis.db.session import get_session

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────


class SupervisorStatus(BaseModel):
    tenant_id: str
    active_builds: int
    max_concurrent: int
    queued_builds: int
    total_factories: int
    total_builds: int
    credits_used: float
    credits_limit: float
    builds_by_status: dict[str, int]


class ActiveBuildInfo(BaseModel):
    build_id: str
    factory_id: str
    factory_name: str
    feature_request: str
    status: str
    vibe_score: int | None
    created_at: str


class QueueBuildRequest(BaseModel):
    factory_id: str
    feature_request: str
    priority: str = "normal"  # normal, high, urgent


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.get("/status", response_model=SupervisorStatus)
async def get_supervisor_status(
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get supervisor status for the current tenant — active builds, capacity, costs."""
    tenant = current.tenant

    # Count active builds (in-progress pipeline stages)
    active_statuses = [
        "requirements", "design", "interviewing", "planning",
        "building", "reviewing",
    ]
    active_result = await db.execute(
        select(func.count())
        .select_from(Build)
        .join(Factory)
        .where(Factory.tenant_id == tenant.id)
        .where(Build.status.in_(active_statuses))
    )
    active_builds = active_result.scalar() or 0

    # Count queued (at review gates)
    gate_statuses = [
        "requirements_review", "design_review", "plan_review",
        "code_review", "qa_review", "deliverable_review",
    ]
    queued_result = await db.execute(
        select(func.count())
        .select_from(Build)
        .join(Factory)
        .where(Factory.tenant_id == tenant.id)
        .where(Build.status.in_(gate_statuses))
    )
    queued_builds = queued_result.scalar() or 0

    # Total counts
    factory_count = (
        await db.execute(
            select(func.count())
            .select_from(Factory)
            .where(Factory.tenant_id == tenant.id)
            .where(Factory.status != "archived")
        )
    ).scalar() or 0

    total_builds = (
        await db.execute(
            select(func.count())
            .select_from(Build)
            .join(Factory)
            .where(Factory.tenant_id == tenant.id)
        )
    ).scalar() or 0

    # Builds by status
    status_counts_result = await db.execute(
        select(Build.status, func.count())
        .join(Factory)
        .where(Factory.tenant_id == tenant.id)
        .group_by(Build.status)
    )
    builds_by_status = {row[0]: row[1] for row in status_counts_result.all()}

    return SupervisorStatus(
        tenant_id=tenant.id,
        active_builds=active_builds,
        max_concurrent=tenant.max_concurrent_builds,
        queued_builds=queued_builds,
        total_factories=factory_count,
        total_builds=total_builds,
        credits_used=tenant.credits_used,
        credits_limit=tenant.credits_limit,
        builds_by_status=builds_by_status,
    )


@router.get("/active", response_model=list[ActiveBuildInfo])
async def get_active_builds(
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """List all currently active builds across all factories."""
    active_statuses = [
        "requirements", "design", "interviewing", "planning",
        "building", "reviewing",
        "requirements_review", "design_review", "plan_review",
        "code_review", "qa_review", "deliverable_review",
    ]

    result = await db.execute(
        select(Build, Factory.name)
        .join(Factory)
        .where(Factory.tenant_id == current.tenant_id)
        .where(Build.status.in_(active_statuses))
        .order_by(Build.created_at.desc())
    )

    return [
        ActiveBuildInfo(
            build_id=build.id,
            factory_id=build.factory_id,
            factory_name=factory_name,
            feature_request=build.feature_request[:200],
            status=build.status,
            vibe_score=build.vibe_score,
            created_at=build.created_at.isoformat(),
        )
        for build, factory_name in result.all()
    ]
