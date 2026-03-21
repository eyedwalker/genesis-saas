"""Assistants API — list, configure, and select assistants for builds."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends

from genesis.auth.middleware import CurrentUser, get_current_user
from genesis.assistants.catalog import (
    ALL_ASSISTANTS,
    DOMAIN_LABELS,
    get_active_assistants,
    get_discovery_assistants,
    get_review_assistants,
)

router = APIRouter()


class AssistantSummary(BaseModel):
    id: str
    name: str
    domain: str
    domain_label: str
    description: str
    weight: float
    is_active: bool


class AssistantListResponse(BaseModel):
    assistants: list[AssistantSummary]
    total: int
    domains: dict[str, str]


class AssistantDetailResponse(AssistantSummary):
    system_prompt: str


@router.get("", response_model=AssistantListResponse)
async def list_assistants(
    domain: str | None = None,
    active_only: bool = False,
    current: CurrentUser = Depends(get_current_user),
):
    """List all available assistants, optionally filtered by domain."""
    source = ALL_ASSISTANTS
    if domain:
        source = [a for a in source if a.domain == domain]
    if active_only:
        source = [a for a in source if a.is_active]

    return AssistantListResponse(
        assistants=[
            AssistantSummary(
                id=a.id,
                name=a.name,
                domain=a.domain,
                domain_label=DOMAIN_LABELS.get(a.domain, a.domain),
                description=a.description,
                weight=a.weight,
                is_active=a.is_active,
            )
            for a in source
        ],
        total=len(source),
        domains=DOMAIN_LABELS,
    )


@router.get("/discovery", response_model=AssistantListResponse)
async def list_discovery_assistants(
    current: CurrentUser = Depends(get_current_user),
):
    """List discovery-focused assistants (project + BA domains)."""
    assistants = get_discovery_assistants()
    return AssistantListResponse(
        assistants=[
            AssistantSummary(
                id=a.id, name=a.name, domain=a.domain,
                domain_label=DOMAIN_LABELS.get(a.domain, a.domain),
                description=a.description, weight=a.weight, is_active=a.is_active,
            )
            for a in assistants
        ],
        total=len(assistants),
        domains={d: l for d, l in DOMAIN_LABELS.items() if d in ("project", "ba")},
    )


@router.get("/review", response_model=AssistantListResponse)
async def list_review_assistants(
    current: CurrentUser = Depends(get_current_user),
):
    """List code review assistants (all domains except discovery)."""
    assistants = get_review_assistants()
    return AssistantListResponse(
        assistants=[
            AssistantSummary(
                id=a.id, name=a.name, domain=a.domain,
                domain_label=DOMAIN_LABELS.get(a.domain, a.domain),
                description=a.description, weight=a.weight, is_active=a.is_active,
            )
            for a in assistants
        ],
        total=len(assistants),
        domains={d: l for d, l in DOMAIN_LABELS.items() if d not in ("project", "ba")},
    )


@router.get("/{assistant_id}", response_model=AssistantDetailResponse)
async def get_assistant(
    assistant_id: str,
    current: CurrentUser = Depends(get_current_user),
):
    """Get full assistant details including system prompt."""
    for a in ALL_ASSISTANTS:
        if a.id == assistant_id:
            return AssistantDetailResponse(
                id=a.id, name=a.name, domain=a.domain,
                domain_label=DOMAIN_LABELS.get(a.domain, a.domain),
                description=a.description, weight=a.weight,
                is_active=a.is_active, system_prompt=a.system_prompt,
            )
    from fastapi import HTTPException
    raise HTTPException(404, "Assistant not found")
