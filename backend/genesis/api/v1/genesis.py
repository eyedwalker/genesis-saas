"""Genesis Engine API — create factories from natural language descriptions."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from genesis.auth.middleware import CurrentUser, get_current_user
from genesis.db.models import Factory
from genesis.db.session import get_session
from genesis.meta.genesis_engine import create_blueprint, FactoryBlueprint

router = APIRouter()


class GenesisRequest(BaseModel):
    domain_description: str
    display_name: str | None = None


class GenesisResponse(BaseModel):
    factory_id: str
    factory_name: str
    domain_name: str
    mission_statement: str
    tech_stack: dict
    standards: list[str]
    vocabulary_count: int


@router.post("", response_model=GenesisResponse)
async def create_factory_from_description(
    body: GenesisRequest,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Create a new factory using the Genesis Engine's meta-prompting.

    Describe what domain you want to build software for, and the Genesis
    Engine (Claude Opus) will analyze the domain and create a complete
    factory blueprint with specialized agent prompts, domain vocabulary,
    compliance standards, and code templates.

    This is the key differentiator: AI that creates AI factories.
    """
    try:
        blueprint = await create_blueprint(
            domain_description=body.domain_description,
            tenant_id=current.tenant_id,
        )
    except Exception as e:
        raise HTTPException(500, f"Genesis Engine failed: {e}")

    # Create factory from blueprint
    factory = Factory(
        tenant_id=current.tenant_id,
        name=body.display_name or blueprint.factory_name,
        domain=blueprint.domain_name,
        description=blueprint.mission_statement,
        tech_stack=f"{blueprint.tech_stack.language}/{blueprint.tech_stack.framework}",
        status="active",
        guardrails={
            "blueprint": blueprint.model_dump(),
            "architect_prompt": blueprint.architect_spec.system_prompt,
            "builder_prompt": blueprint.builder_spec.system_prompt,
            "qa_prompt": blueprint.qa_spec.system_prompt,
        },
    )
    db.add(factory)
    await db.flush()

    return GenesisResponse(
        factory_id=factory.id,
        factory_name=blueprint.factory_name,
        domain_name=blueprint.domain_name,
        mission_statement=blueprint.mission_statement,
        tech_stack=blueprint.tech_stack.model_dump(),
        standards=blueprint.standards,
        vocabulary_count=len(blueprint.vocabulary.terms),
    )
