"""Testing agent — generates test suites. Uses Claude Agent SDK."""

from __future__ import annotations

from genesis.agents.claude_client import run_agent_structured
from genesis.agents.model_resolver import resolve_model_tier
from genesis.types import FactoryContext, ImplementationPlan, ModelConfig, TestSuiteResult

TESTING_SYSTEM_PROMPT = """You are a senior QA engineer generating comprehensive test suites.

Rules:
- Use pytest for Python, vitest/jest for TypeScript
- Include unit, integration, and edge case tests
- Mock external dependencies
- Test error paths, not just happy paths
- Aim for 80%+ coverage"""


async def generate_tests(
    plan: ImplementationPlan, code: str, file_map: dict[str, str],
    factory_context: FactoryContext | None = None,
    model_config: ModelConfig | None = None,
) -> TestSuiteResult:
    parts = [f"Feature: {plan.feature_name}", "",
             "Files to test:", *[f"- {p}" for p in file_map], "",
             "Generated code:", code[:12000]]
    if factory_context:
        parts.insert(0, f"Tech stack: {factory_context.tech_stack}")

    data = await run_agent_structured(
        prompt="\n".join(parts),
        output_schema=TestSuiteResult.model_json_schema(),
        system_prompt=TESTING_SYSTEM_PROMPT,
        model=resolve_model_tier("testing", model_config),
    )
    return TestSuiteResult(**data) if isinstance(data, dict) else data
