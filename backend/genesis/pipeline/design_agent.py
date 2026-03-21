"""Design agent — generates UI/UX specifications.

Uses Claude Agent SDK with structured output.
"""

from __future__ import annotations

import logging

from genesis.agents.claude_client import run_agent_structured
from genesis.agents.compliance import get_compliance_prompt
from genesis.agents.model_resolver import resolve_model_tier
from genesis.types import (
    DesignResult,
    FactoryContext,
    ModelConfig,
    RequirementsResult,
)

logger = logging.getLogger(__name__)

DESIGN_SYSTEM_PROMPT = """You are a senior UI/UX designer generating specifications from requirements. Create a complete UI design specification.

Rules:
- Max 8-12 pages, 15-20 components
- Layout types: sidebar-detail, full-width, split, dashboard-grid, form-wizard, list-detail
- Include a Mermaid flowchart for navigation
- Components should be reusable and well-defined
- Map components to user story IDs"""


async def generate_design(
    requirements: RequirementsResult,
    factory_context: FactoryContext | None = None,
    design_brief: dict | None = None,
    model_config: ModelConfig | None = None,
) -> DesignResult:
    """Generate UI/UX design specifications from requirements."""
    story_list = "\n".join(
        f"{s.id}: {s.title} — {s.persona}, {s.capability}"
        for s in requirements.stories
    )

    parts = [
        f"Requirements summary: {requirements.summary}",
        f"\nUser stories:\n{story_list}",
        f"\nEpics: {', '.join(requirements.epics)}",
    ]

    if factory_context:
        parts.append(f"\nProject: {factory_context.name}")
        parts.append(f"Domain: {factory_context.domain}")
        parts.append(f"Tech stack: {factory_context.tech_stack}")

    if design_brief and design_brief.get("uiPreferences"):
        parts.append(f"\nUI Preferences: {design_brief['uiPreferences']}")

    system = DESIGN_SYSTEM_PROMPT
    if factory_context and factory_context.compliance_profile:
        system += get_compliance_prompt("architecture", factory_context.compliance_profile)

    model = resolve_model_tier("design", model_config)

    data = await run_agent_structured(
        prompt="\n\n".join(parts),
        output_schema=DesignResult.model_json_schema(),
        system_prompt=system,
        model=model,
    )

    return DesignResult(**data) if isinstance(data, dict) else data
