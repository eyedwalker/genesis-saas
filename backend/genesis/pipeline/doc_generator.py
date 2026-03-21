"""Doc generator — PRD, ADR, OpenAPI, runbooks, README. Uses Claude Agent SDK."""

from __future__ import annotations

import asyncio

from genesis.agents.claude_client import run_agent
from genesis.agents.model_resolver import resolve_model_tier
from genesis.types import (
    DesignResult, DocType, FactoryContext,
    ImplementationPlan, ModelConfig, RequirementsResult,
)

DOC_PROMPTS: dict[str, str] = {
    "prd": "Generate a Product Requirements Document (PRD) in markdown.",
    "adr": "Generate an Architecture Decision Record (ADR) in markdown.",
    "openapi": "Generate an OpenAPI 3.0 specification in YAML format.",
    "data_model": "Generate a data model document with a Mermaid ER diagram.",
    "runbook": "Generate an operations runbook in markdown.",
    "readme": "Generate a README.md for the project.",
    "user_stories": "Format the user stories as structured markdown.",
}

TITLE_MAP = {
    "prd": "Product Requirements Document", "adr": "Architecture Decision Record",
    "openapi": "OpenAPI Specification", "data_model": "Data Model",
    "runbook": "Operations Runbook", "readme": "README", "user_stories": "User Stories",
}


async def generate_document(
    doc_type: DocType, requirements: RequirementsResult,
    plan: ImplementationPlan | None = None, design: DesignResult | None = None,
    code: str | None = None, factory_context: FactoryContext | None = None,
    model_config: ModelConfig | None = None,
) -> dict[str, str]:
    parts = [f"Requirements summary: {requirements.summary}"]
    if factory_context:
        parts.insert(0, f"Project: {factory_context.name} ({factory_context.domain})")
    if plan:
        parts.append(f"\nFeature: {plan.feature_name}, {len(plan.steps)} steps")
    if code and doc_type in (DocType.OPENAPI, DocType.DATA_MODEL, DocType.RUNBOOK):
        parts.append(f"\nCode:\n{code[:8000]}")

    story_text = "\n".join(f"- {s.id}: {s.title} ({s.priority})" for s in requirements.stories)
    parts.append(f"\nUser stories:\n{story_text}")

    model = resolve_model_tier("docs", model_config)
    result = await run_agent(
        prompt="\n\n".join(parts),
        system_prompt=DOC_PROMPTS.get(doc_type.value, DOC_PROMPTS["readme"]),
        model=model,
        max_turns=3,
    )

    fmt = "yaml" if doc_type == DocType.OPENAPI else "markdown"
    return {"title": TITLE_MAP.get(doc_type.value, doc_type.value),
            "content": result.result or "", "format": fmt}


async def generate_all_documents(
    requirements: RequirementsResult, plan: ImplementationPlan | None = None,
    design: DesignResult | None = None, code: str | None = None,
    factory_context: FactoryContext | None = None,
    model_config: ModelConfig | None = None,
) -> list[dict[str, str]]:
    doc_types = [DocType.PRD, DocType.ADR, DocType.README, DocType.USER_STORIES]
    if plan:
        doc_types.extend([DocType.OPENAPI, DocType.DATA_MODEL, DocType.RUNBOOK])
    return await asyncio.gather(*[
        generate_document(dt, requirements, plan, design, code, factory_context, model_config)
        for dt in doc_types
    ])
