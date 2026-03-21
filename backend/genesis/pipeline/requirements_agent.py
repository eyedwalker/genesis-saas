"""Requirements agent — generates structured user stories.

Uses Claude Agent SDK with structured output for type-safe results.
"""

from __future__ import annotations

import logging

from genesis.agents.claude_client import run_agent_structured
from genesis.agents.compliance import get_compliance_prompt
from genesis.agents.model_resolver import resolve_model_tier
from genesis.types import (
    FactoryContext,
    InterviewResult,
    ModelConfig,
    RequirementsResult,
)

logger = logging.getLogger(__name__)

REQUIREMENTS_SYSTEM_PROMPT = """You are a senior business analyst generating structured requirements from a feature request and discovery interview.

Rules:
- Generate 8-15 user stories max
- Use MoSCoW prioritization (must/should/could/wont)
- Each story has 2-4 acceptance criteria in Given/When/Then format
- Story IDs: US-001, US-002, etc.
- AC IDs: AC-001-01 (story 001, criterion 01)
- Include non-functional requirements (performance, security, accessibility)
- Be specific and actionable, not vague"""


async def generate_requirements(
    feature_request: str,
    interview_result: InterviewResult | None = None,
    factory_context: FactoryContext | None = None,
    model_config: ModelConfig | None = None,
) -> RequirementsResult:
    """Generate structured requirements from feature request + interview data."""
    parts = [f"Feature request: {feature_request}"]

    if interview_result:
        parts.append(f"\nInterview summary: {interview_result.summary}")
        for q in interview_result.questions:
            if q.answer:
                parts.append(f"Q: {q.question}\nA: {q.answer}")

    if factory_context:
        parts.append(f"\nProject: {factory_context.name}")
        parts.append(f"Domain: {factory_context.domain}")
        parts.append(f"Tech stack: {factory_context.tech_stack}")

    system = REQUIREMENTS_SYSTEM_PROMPT
    if factory_context and factory_context.compliance_profile:
        system += get_compliance_prompt(
            "architecture", factory_context.compliance_profile
        )

    model = resolve_model_tier("requirements", model_config)

    data = await run_agent_structured(
        prompt="\n\n".join(parts),
        output_schema=RequirementsResult.model_json_schema(),
        system_prompt=system,
        model=model,
    )

    return RequirementsResult(**data) if isinstance(data, dict) else data
