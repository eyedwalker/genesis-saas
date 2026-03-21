"""Builder agent — code generation with self-healing.

Uses Claude Agent SDK with full file system tools (Read, Write, Edit, Bash)
so the builder can actually create files, run linters/tests, and fix errors
autonomously — no more manual file parsing or subprocess validation.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any

from claude_agent_sdk import ResultMessage

from genesis.agents.claude_client import run_builder_agent, run_agent, parse_llm_json
from genesis.agents.compliance import get_compliance_prompt
from genesis.agents.model_resolver import resolve_model_tier
from genesis.types import (
    BuildResult,
    DesignResult,
    FactoryContext,
    Finding,
    ImplementationPlan,
    ModelConfig,
    RequirementsResult,
)

logger = logging.getLogger(__name__)

BUILDER_SYSTEM_PROMPT = """You are a senior software engineer implementing a feature from an approved plan. Generate production-quality, deployable code.

Architecture rules (CRITICAL):
- LAYERED ARCHITECTURE: Route handlers → Manager (business logic) → Accessor (data access)
- Route handlers: validate input, call managers, return responses. NO direct DB queries.
- Managers: contain all business logic, call accessors for data.
- Accessors: ONLY data access. NO business logic.
- Validate ALL input at API boundaries.
- Include proper error handling and type safety.
- Write clean, well-structured code.

You have access to Write, Edit, Read, Bash, Glob, and Grep tools.
Create all files in the current working directory.
After writing all files, run any available linter or type checker to validate.
If validation fails, fix the errors and re-run until clean."""

FIXER_SYSTEM_PROMPT = """You are a senior software engineer fixing code based on AI review findings.

Rules:
- Fix ONLY the issues listed — do not refactor unrelated code
- Use the Edit tool to modify files in place
- Prioritize critical and high severity fixes
- After fixing, run the linter/type checker to verify

You have access to Read, Edit, Bash, Glob, and Grep tools."""


def _collect_workspace_files(workspace: Path) -> dict[str, str]:
    """Collect all generated files from a workspace directory into a file map."""
    file_map: dict[str, str] = {}
    for f in workspace.rglob("*"):
        if f.is_file() and not any(
            part.startswith(".") or part == "__pycache__" or part == "node_modules"
            for part in f.relative_to(workspace).parts
        ):
            try:
                rel = str(f.relative_to(workspace))
                file_map[rel] = f.read_text(errors="replace")
            except Exception:
                pass
    return file_map


async def generate_code(
    plan: ImplementationPlan,
    requirements: RequirementsResult,
    design: DesignResult | None = None,
    factory_context: FactoryContext | None = None,
    previous_code: str | None = None,
    feedback: str | None = None,
    model_config: ModelConfig | None = None,
    workspace_dir: Path | None = None,
) -> BuildResult:
    """Generate code from an approved implementation plan.

    Uses Claude Agent SDK with Write/Edit/Bash tools to create real files
    in a workspace directory. The agent can run linters and fix issues.
    """
    story_list = "\n".join(
        f"{s.id}: {s.persona}, {s.capability}, {s.benefit}"
        for s in requirements.stories
    )

    parts = []
    if factory_context:
        parts.append(f"Project: {factory_context.name} ({factory_context.domain})")
        parts.append(f"Tech stack: {factory_context.tech_stack}")

    parts.extend([
        "",
        "Implementation Plan:",
        f"Feature: {plan.feature_name}",
        f"Description: {plan.description}",
        "",
        "Steps:",
        *[f"{i+1}. {s.file_path} — {s.description}" for i, s in enumerate(plan.steps)],
        "",
        "Business Rules:",
        *[f"- {r}" for r in plan.business_rules],
        "",
        "API Endpoints:",
        *[f"- {e}" for e in plan.api_endpoints],
        "",
        f"User Stories:\n{story_list}",
    ])

    if feedback:
        parts.append(f"\nFeedback to address:\n{feedback}")

    system = BUILDER_SYSTEM_PROMPT
    if factory_context and factory_context.compliance_profile:
        system += get_compliance_prompt("building", factory_context.compliance_profile)

    model = resolve_model_tier("building", model_config)

    # Create workspace
    workspace = workspace_dir or Path(tempfile.mkdtemp(prefix="genesis-build-"))
    workspace.mkdir(parents=True, exist_ok=True)

    result = await run_builder_agent(
        prompt="\n".join(parts),
        system_prompt=system,
        model=model,
        workspace_dir=workspace,
        max_turns=20,
        max_budget_usd=5.0,
    )

    # Collect files the agent created
    file_map = _collect_workspace_files(workspace)

    code = "\n\n".join(
        f"# === {path} ===\n{content}" for path, content in file_map.items()
    )

    return BuildResult(
        code=code,
        fileMap=file_map,
        filesCreated=list(file_map.keys()),
        explanation=result.result or "",
    )


async def build_with_self_healing(
    plan: ImplementationPlan,
    requirements: RequirementsResult,
    design: DesignResult | None = None,
    factory_context: FactoryContext | None = None,
    model_config: ModelConfig | None = None,
) -> dict[str, Any]:
    """Build with the Claude Agent SDK's built-in self-healing.

    The SDK agent has Bash tool access, so it can run linters/tests
    and fix errors in a loop — no manual iteration needed.
    """
    workspace = Path(tempfile.mkdtemp(prefix="genesis-build-"))

    try:
        result = await generate_code(
            plan=plan,
            requirements=requirements,
            design=design,
            factory_context=factory_context,
            model_config=model_config,
            workspace_dir=workspace,
        )

        return {"result": result, "iterations": 1, "success": True}
    except Exception as e:
        logger.error("Build failed: %s", e)
        # Collect whatever was generated
        file_map = _collect_workspace_files(workspace)
        fallback = BuildResult(
            code="",
            fileMap=file_map,
            filesCreated=list(file_map.keys()),
            explanation=f"Build failed: {e}",
        )
        return {"result": fallback, "iterations": 1, "success": False}
    finally:
        # Clean up workspace
        shutil.rmtree(workspace, ignore_errors=True)


async def fix_code_from_findings(
    code: str,
    file_map: dict[str, str],
    findings: list[Finding],
    factory_context: FactoryContext | None = None,
    model_config: ModelConfig | None = None,
) -> BuildResult:
    """Fix code based on AI review findings using the agent's Edit tool."""
    non_low = [f for f in findings if f.severity != "low"]
    findings_text = "\n\n".join(
        "\n".join(filter(None, [
            f"{i+1}. [{f.severity.upper()}] {f.title}",
            f"   Issue: {f.description}",
            f"   Fix: {f.recommendation}",
        ]))
        for i, f in enumerate(non_low)
    )

    # Write files to temp workspace for the agent to edit
    workspace = Path(tempfile.mkdtemp(prefix="genesis-fix-"))
    for path, content in file_map.items():
        fp = workspace / path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)

    prompt = f"Fix these {len(non_low)} issues in the code:\n\n{findings_text}"

    system = FIXER_SYSTEM_PROMPT
    if factory_context and factory_context.compliance_profile:
        system += get_compliance_prompt("building", factory_context.compliance_profile)

    model = resolve_model_tier("building", model_config)

    try:
        await run_builder_agent(
            prompt=prompt,
            system_prompt=system,
            model=model,
            workspace_dir=workspace,
            max_turns=15,
            max_budget_usd=3.0,
        )

        fixed_map = _collect_workspace_files(workspace)
        fixed_code = "\n\n".join(
            f"# === {p} ===\n{c}" for p, c in fixed_map.items()
        )

        return BuildResult(
            code=fixed_code,
            fileMap=fixed_map,
            filesCreated=list(fixed_map.keys()),
            explanation="Fixed review findings",
        )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
