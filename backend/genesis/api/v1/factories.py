"""Factory CRUD endpoints."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from genesis.auth.middleware import CurrentUser, get_current_user
from genesis.db.models import Build, Factory, FactoryMember
from genesis.db.session import get_session

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────


class FactoryCreate(BaseModel):
    name: str
    domain: str
    description: str | None = None
    tech_stack: str | None = None
    fast_track: bool = False


class FactoryUpdate(BaseModel):
    name: str | None = None
    domain: str | None = None
    description: str | None = None
    tech_stack: str | None = None
    status: str | None = None
    fast_track: bool | None = None
    github_repo: str | None = None


class FactoryResponse(BaseModel):
    id: str
    name: str
    domain: str
    description: str | None
    tech_stack: str | None
    status: str
    fast_track: bool
    github_repo: str | None
    build_count: int = 0
    avg_vibe_score: float | None = None
    created_at: str

    model_config = {"from_attributes": True}


class FactoryListResponse(BaseModel):
    factories: list[FactoryResponse]
    total: int


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.get("", response_model=FactoryListResponse)
async def list_factories(
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """List all factories for the current tenant."""
    result = await db.execute(
        select(Factory)
        .where(Factory.tenant_id == current.tenant_id)
        .order_by(Factory.created_at.desc())
    )
    factories = result.scalars().all()

    responses = []
    for f in factories:
        # Get build stats
        build_count_result = await db.execute(
            select(func.count()).select_from(Build).where(Build.factory_id == f.id)
        )
        build_count = build_count_result.scalar() or 0

        avg_vibe_result = await db.execute(
            select(func.avg(Build.vibe_score))
            .where(Build.factory_id == f.id)
            .where(Build.vibe_score.isnot(None))
        )
        avg_vibe = avg_vibe_result.scalar()

        responses.append(
            FactoryResponse(
                id=f.id,
                name=f.name,
                domain=f.domain,
                description=f.description,
                tech_stack=f.tech_stack,
                status=f.status,
                fast_track=f.fast_track,
                github_repo=f.github_repo,
                build_count=build_count,
                avg_vibe_score=round(avg_vibe, 1) if avg_vibe else None,
                created_at=f.created_at.isoformat(),
            )
        )

    return FactoryListResponse(factories=responses, total=len(responses))


@router.post("", response_model=FactoryResponse, status_code=201)
async def create_factory(
    body: FactoryCreate,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Create a new factory."""
    factory = Factory(
        tenant_id=current.tenant_id,
        name=body.name,
        domain=body.domain,
        description=body.description,
        tech_stack=body.tech_stack,
        fast_track=body.fast_track,
        status="active",
    )
    db.add(factory)
    await db.flush()

    # Add creator as OWNER
    member = FactoryMember(
        tenant_id=current.tenant_id,
        factory_id=factory.id,
        user_id=current.user_id,
        role="owner",
    )
    db.add(member)
    await db.flush()

    return FactoryResponse(
        id=factory.id,
        name=factory.name,
        domain=factory.domain,
        description=factory.description,
        tech_stack=factory.tech_stack,
        status=factory.status,
        fast_track=factory.fast_track,
        github_repo=factory.github_repo,
        created_at=factory.created_at.isoformat(),
    )


@router.get("/{factory_id}", response_model=FactoryResponse)
async def get_factory(
    factory_id: str,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get a single factory by ID."""
    factory = await db.get(Factory, factory_id)
    if not factory or factory.tenant_id != current.tenant_id:
        raise HTTPException(404, "Factory not found")

    build_count_result = await db.execute(
        select(func.count()).select_from(Build).where(Build.factory_id == factory.id)
    )
    build_count = build_count_result.scalar() or 0

    return FactoryResponse(
        id=factory.id,
        name=factory.name,
        domain=factory.domain,
        description=factory.description,
        tech_stack=factory.tech_stack,
        status=factory.status,
        fast_track=factory.fast_track,
        github_repo=factory.github_repo,
        build_count=build_count,
        created_at=factory.created_at.isoformat(),
    )


@router.patch("/{factory_id}", response_model=FactoryResponse)
async def update_factory(
    factory_id: str,
    body: FactoryUpdate,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Update a factory."""
    factory = await db.get(Factory, factory_id)
    if not factory or factory.tenant_id != current.tenant_id:
        raise HTTPException(404, "Factory not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(factory, field, value)
    await db.flush()

    return FactoryResponse(
        id=factory.id,
        name=factory.name,
        domain=factory.domain,
        description=factory.description,
        tech_stack=factory.tech_stack,
        status=factory.status,
        fast_track=factory.fast_track,
        github_repo=factory.github_repo,
        created_at=factory.created_at.isoformat(),
    )


@router.delete("/{factory_id}", status_code=204)
async def delete_factory(
    factory_id: str,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Archive a factory (soft delete)."""
    factory = await db.get(Factory, factory_id)
    if not factory or factory.tenant_id != current.tenant_id:
        raise HTTPException(404, "Factory not found")
    factory.status = "archived"
    await db.flush()
