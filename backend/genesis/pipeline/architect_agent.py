"""Architect agent — creates implementation plans.

Uses Claude Agent SDK with Grep/Glob/Read tools so the architect
can explore existing code when planning modifications.
"""

from __future__ import annotations

import logging

from genesis.agents.claude_client import run_agent_structured
from genesis.agents.compliance import get_compliance_prompt
from genesis.agents.model_resolver import resolve_model_tier
from genesis.types import (
    DesignResult,
    FactoryContext,
    ImplementationPlan,
    ModelConfig,
    RequirementsResult,
)

logger = logging.getLogger(__name__)

ARCHITECT_SYSTEM_PROMPT = """You are a senior software architect creating an implementation plan from requirements and design specifications. Produce a detailed, actionable plan that a developer (or AI builder) can follow step by step.

Rules:
- List every file that needs to be created or modified with full paths
- Order steps by dependency (what must be built first)
- Include database schema changes
- Include API endpoint specifications with methods, paths, and request/response types
- Estimate complexity per step
- Suggest which AI review assistants should check this code
- Consider the tech stack and follow its conventions
- Include business rules that the code must enforce
- Keep output COMPACT — limit to 15-20 steps max"""


async def generate_plan(
    feature_request: str,
    requirements: RequirementsResult,
    design: DesignResult | None = None,
    factory_context: FactoryContext | None = None,
    existing_code: str | None = None,
    model_config: ModelConfig | None = None,
) -> ImplementationPlan:
    """Generate an implementation plan from requirements and design."""
    story_list = "\n".join(
        f"{s.id}: {s.title} — ACs: {len(s.acceptance_criteria)}"
        for s in requirements.stories
    )

    page_list = "No design specs provided"
    if design:
        page_list = "\n".join(
            f"{p.route} — {p.name} ({p.layout})" for p in design.pages
        )

    parts = [f"Feature: {feature_request}"]
    if factory_context:
        parts.extend([
            f"Project: {factory_context.name}",
            f"Domain: {factory_context.domain}",
            f"Tech stack: {factory_context.tech_stack}",
        ])

    parts.extend([
        "", f"Requirements summary:\n{requirements.summary}",
        f"\nUser stories:\n{story_list}",
        f"\nNon-functional:\n" + "\n".join(requirements.non_functional),
        f"\nPages:\n{page_list}",
    ])
    if existing_code:
        parts.append(f"\nExisting code context:\n{existing_code}")

    system = ARCHITECT_SYSTEM_PROMPT
    if factory_context and factory_context.compliance_profile:
        system += get_compliance_prompt(
            "architecture", factory_context.compliance_profile
        )

    model = resolve_model_tier("planning", model_config)

    data = await run_agent_structured(
        prompt="\n".join(parts),
        output_schema=ImplementationPlan.model_json_schema(),
        system_prompt=system,
        model=model,
        tools=["Read", "Glob", "Grep"],  # Can explore existing code
    )

    result = ImplementationPlan(**data) if isinstance(data, dict) else data
    if not result.steps:
        raise ValueError("Architect agent returned no steps")
    return result
