"""Assistants API — list catalog, create custom, edit, view, and manage assistants.

Two sources of assistants:
1. Catalog (built-in, read-only): 44 assistants from genesis/assistants/catalog.py
2. Custom (per-tenant, full CRUD): stored in DB, tenant can create/edit/delete
"""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from genesis.auth.middleware import CurrentUser, get_current_user
from genesis.db.models import Assistant
from genesis.db.session import get_session
from genesis.assistants.catalog import (
    ALL_ASSISTANTS,
    DOMAIN_LABELS,
    get_active_assistants,
    get_discovery_assistants,
    get_review_assistants,
)

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────


class AssistantSummary(BaseModel):
    id: str
    name: str
    domain: str
    domain_label: str
    description: str
    weight: float
    is_active: bool
    source: str = "catalog"  # "catalog" or "custom"


class AssistantListResponse(BaseModel):
    assistants: list[AssistantSummary]
    total: int
    domains: dict[str, str]


class AssistantDetailResponse(AssistantSummary):
    system_prompt: str


class AssistantCreate(BaseModel):
    name: str
    domain: str
    description: str
    system_prompt: str
    weight: float = 1.0
    is_active: bool = True


class AssistantUpdate(BaseModel):
    name: str | None = None
    domain: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    weight: float | None = None
    is_active: bool | None = None


# ── Helpers ────────────────────────────────────────────────────────────────────


def _catalog_to_summary(a) -> AssistantSummary:
    return AssistantSummary(
        id=a.id, name=a.name, domain=a.domain,
        domain_label=DOMAIN_LABELS.get(a.domain, a.domain),
        description=a.description, weight=a.weight,
        is_active=a.is_active, source="catalog",
    )


def _db_to_summary(a: Assistant) -> AssistantSummary:
    return AssistantSummary(
        id=a.id, name=a.name, domain=a.domain,
        domain_label=DOMAIN_LABELS.get(a.domain, a.domain),
        description=a.description, weight=a.weight,
        is_active=a.is_active, source="custom",
    )


def _db_to_detail(a: Assistant) -> AssistantDetailResponse:
    return AssistantDetailResponse(
        id=a.id, name=a.name, domain=a.domain,
        domain_label=DOMAIN_LABELS.get(a.domain, a.domain),
        description=a.description, weight=a.weight,
        is_active=a.is_active, system_prompt=a.system_prompt,
        source="custom",
    )


# ── List Endpoints ────────────────────────────────────────────────────────────


@router.get("", response_model=AssistantListResponse)
async def list_assistants(
    domain: str | None = None,
    active_only: bool = False,
    source: str | None = None,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """List all assistants — both catalog (built-in) and custom (tenant-created)."""
    results: list[AssistantSummary] = []

    # Catalog assistants
    if source != "custom":
        catalog = ALL_ASSISTANTS
        if domain:
            catalog = [a for a in catalog if a.domain == domain]
        if active_only:
            catalog = [a for a in catalog if a.is_active]
        results.extend(_catalog_to_summary(a) for a in catalog)

    # Custom assistants (tenant-specific)
    if source != "catalog":
        query = select(Assistant).where(Assistant.tenant_id == current.tenant_id)
        if domain:
            query = query.where(Assistant.domain == domain)
        if active_only:
            query = query.where(Assistant.is_active == True)
        custom = (await db.execute(query)).scalars().all()
        results.extend(_db_to_summary(a) for a in custom)

    return AssistantListResponse(
        assistants=results, total=len(results), domains=DOMAIN_LABELS,
    )


@router.get("/discovery", response_model=AssistantListResponse)
async def list_discovery_assistants(
    current: CurrentUser = Depends(get_current_user),
):
    """List discovery-focused assistants."""
    assistants = get_discovery_assistants()
    return AssistantListResponse(
        assistants=[_catalog_to_summary(a) for a in assistants],
        total=len(assistants),
        domains={d: l for d, l in DOMAIN_LABELS.items() if d in ("project", "ba")},
    )


@router.get("/review", response_model=AssistantListResponse)
async def list_review_assistants(
    current: CurrentUser = Depends(get_current_user),
):
    """List code review assistants."""
    assistants = get_review_assistants()
    return AssistantListResponse(
        assistants=[_catalog_to_summary(a) for a in assistants],
        total=len(assistants),
        domains={d: l for d, l in DOMAIN_LABELS.items() if d not in ("project", "ba")},
    )


# ── Detail ────────────────────────────────────────────────────────────────────


@router.get("/{assistant_id}", response_model=AssistantDetailResponse)
async def get_assistant(
    assistant_id: str,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get full assistant details including system prompt."""
    # Check catalog first
    for a in ALL_ASSISTANTS:
        if a.id == assistant_id:
            return AssistantDetailResponse(
                id=a.id, name=a.name, domain=a.domain,
                domain_label=DOMAIN_LABELS.get(a.domain, a.domain),
                description=a.description, weight=a.weight,
                is_active=a.is_active, system_prompt=a.system_prompt,
                source="catalog",
            )

    # Check custom
    result = await db.execute(
        select(Assistant).where(
            Assistant.id == assistant_id,
            Assistant.tenant_id == current.tenant_id,
        )
    )
    custom = result.scalar_one_or_none()
    if custom:
        return _db_to_detail(custom)

    raise HTTPException(404, "Assistant not found")


# ── Create ────────────────────────────────────────────────────────────────────


@router.post("", response_model=AssistantDetailResponse, status_code=201)
async def create_assistant(
    body: AssistantCreate,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Create a custom assistant for your tenant."""
    assistant = Assistant(
        tenant_id=current.tenant_id,
        name=body.name,
        domain=body.domain,
        description=body.description,
        system_prompt=body.system_prompt,
        weight=body.weight,
        is_active=body.is_active,
        patterns={},
    )
    db.add(assistant)
    await db.flush()
    return _db_to_detail(assistant)


# ── Update ────────────────────────────────────────────────────────────────────


@router.patch("/{assistant_id}", response_model=AssistantDetailResponse)
async def update_assistant(
    assistant_id: str,
    body: AssistantUpdate,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Update a custom assistant. Catalog assistants cannot be edited directly."""
    # Check if it's a catalog assistant
    for a in ALL_ASSISTANTS:
        if a.id == assistant_id:
            raise HTTPException(
                400,
                "Cannot edit catalog assistants. Create a custom copy instead, "
                "or use POST /assistants/{id}/fork to clone and customize.",
            )

    result = await db.execute(
        select(Assistant).where(
            Assistant.id == assistant_id,
            Assistant.tenant_id == current.tenant_id,
        )
    )
    assistant = result.scalar_one_or_none()
    if not assistant:
        raise HTTPException(404, "Assistant not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(assistant, field, value)
    await db.flush()
    return _db_to_detail(assistant)


# ── Fork (copy catalog assistant to customize) ────────────────────────────────


@router.post("/{assistant_id}/fork", response_model=AssistantDetailResponse, status_code=201)
async def fork_assistant(
    assistant_id: str,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Fork a catalog assistant into a custom copy you can edit.

    Creates a tenant-owned copy with the same system prompt, which you
    can then customize via PATCH.
    """
    # Find in catalog
    source = None
    for a in ALL_ASSISTANTS:
        if a.id == assistant_id:
            source = a
            break

    if not source:
        raise HTTPException(404, "Catalog assistant not found")

    forked = Assistant(
        tenant_id=current.tenant_id,
        name=f"{source.name} (Custom)",
        domain=source.domain,
        description=source.description,
        system_prompt=source.system_prompt,
        weight=source.weight,
        is_active=True,
        patterns={},
    )
    db.add(forked)
    await db.flush()
    return _db_to_detail(forked)


# ── Delete ────────────────────────────────────────────────────────────────────


@router.delete("/{assistant_id}", status_code=204)
async def delete_assistant(
    assistant_id: str,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Delete a custom assistant. Catalog assistants cannot be deleted."""
    for a in ALL_ASSISTANTS:
        if a.id == assistant_id:
            raise HTTPException(400, "Cannot delete catalog assistants")

    result = await db.execute(
        select(Assistant).where(
            Assistant.id == assistant_id,
            Assistant.tenant_id == current.tenant_id,
        )
    )
    assistant = result.scalar_one_or_none()
    if not assistant:
        raise HTTPException(404, "Assistant not found")

    await db.delete(assistant)
    await db.flush()
