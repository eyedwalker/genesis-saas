"""DevOps agent — generates Docker/deployment configs. Uses Claude Agent SDK."""

from __future__ import annotations

from genesis.agents.claude_client import run_agent_structured
from genesis.agents.model_resolver import resolve_model_tier
from genesis.types import DevOpsResult, FactoryContext, ImplementationPlan, ModelConfig

DEVOPS_SYSTEM_PROMPT = """You are a DevOps engineer generating deployment configurations.

Rules:
- Use multi-stage Docker builds when appropriate
- Include health checks
- Use .env.example (never commit real secrets)
- Use docker compose for local development
- Include database migration commands
- Use non-root user in Dockerfile"""


async def generate_devops(
    plan: ImplementationPlan, file_map: dict[str, str],
    factory_context: FactoryContext | None = None,
    model_config: ModelConfig | None = None,
) -> DevOpsResult:
    parts = [f"Feature: {plan.feature_name}", "",
             "Project files:", *[f"- {p}" for p in file_map], "",
             "API Endpoints:", *[f"- {e}" for e in plan.api_endpoints]]
    if factory_context:
        parts.insert(0, f"Tech stack: {factory_context.tech_stack}")

    data = await run_agent_structured(
        prompt="\n".join(parts),
        output_schema=DevOpsResult.model_json_schema(),
        system_prompt=DEVOPS_SYSTEM_PROMPT,
        model=resolve_model_tier("devops", model_config),
    )
    return DevOpsResult(**data) if isinstance(data, dict) else data
