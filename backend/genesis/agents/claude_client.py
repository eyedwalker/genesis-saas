"""Claude Agent SDK client for pipeline agents.

Uses claude-agent-sdk (claude_agent_sdk) for:
- Built-in tools (Read, Write, Bash, Grep, etc.)
- Subagent orchestration
- Structured output via Pydantic models
- Session persistence and resumption
- Cost tracking per build
"""

from __future__ import annotations

import json
import logging
import re
import tempfile
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AgentDefinition,
    ClaudeAgentOptions,
    ResultMessage,
    query,
)

logger = logging.getLogger(__name__)


async def run_agent(
    prompt: str,
    system_prompt: str | None = None,
    model: str = "sonnet",
    tools: list[str] | None = None,
    max_turns: int | None = None,
    max_budget_usd: float | None = None,
    cwd: str | Path | None = None,
    output_format: dict[str, Any] | None = None,
    agents: dict[str, AgentDefinition] | None = None,
) -> ResultMessage:
    """Run a Claude agent and return the result.

    This is the primary interface for all pipeline agents.
    Uses the Claude Agent SDK instead of raw API calls.
    """
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        model=model,
        allowed_tools=tools or [],
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        cwd=str(cwd) if cwd else None,
        output_format=output_format,
        permission_mode="bypassPermissions",
        agents=agents,
    )

    result: ResultMessage | None = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            result = message

    if result is None:
        raise RuntimeError("Agent returned no result")

    if result.is_error:
        raise RuntimeError(f"Agent error: {result.result}")

    return result


async def run_agent_structured(
    prompt: str,
    output_schema: dict[str, Any],
    system_prompt: str | None = None,
    model: str = "sonnet",
    tools: list[str] | None = None,
    max_turns: int | None = None,
    cwd: str | Path | None = None,
) -> Any:
    """Run an agent and return structured (JSON) output validated against a schema."""
    result = await run_agent(
        prompt=prompt,
        system_prompt=system_prompt,
        model=model,
        tools=tools,
        max_turns=max_turns,
        cwd=cwd,
        output_format={"type": "json_schema", "schema": output_schema},
    )

    if result.structured_output is not None:
        return result.structured_output

    # Fallback: parse from text result
    if result.result:
        return parse_llm_json(result.result, "agent")

    raise RuntimeError("Agent returned no structured output")


async def run_builder_agent(
    prompt: str,
    system_prompt: str | None = None,
    model: str = "sonnet",
    workspace_dir: str | Path | None = None,
    max_turns: int = 20,
    max_budget_usd: float = 5.0,
) -> ResultMessage:
    """Run a builder agent with full file system access.

    The builder gets Read, Write, Edit, Bash, Glob, Grep tools
    so it can actually create files, run tests, and self-heal.
    """
    # Create a temp workspace if none provided
    if workspace_dir is None:
        workspace_dir = Path(tempfile.mkdtemp(prefix="genesis-build-"))

    workspace = Path(workspace_dir)
    workspace.mkdir(parents=True, exist_ok=True)

    return await run_agent(
        prompt=prompt,
        system_prompt=system_prompt,
        model=model,
        tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        cwd=workspace,
    )


def parse_llm_json(text: str, agent_name: str = "agent") -> Any:
    """Parse JSON from LLM response, handling common issues."""
    # Strip markdown fences
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```\s*$", "", text)
    text = text.strip()

    # Find JSON start
    for start_char in ("{", "["):
        idx = text.find(start_char)
        if idx != -1:
            json_str = text[idx:]
            break
    else:
        raise ValueError(f"{agent_name}: no JSON found in response")

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # Repair truncated JSON
    if json_str.count('"') % 2 != 0:
        json_str += '"'
    open_braces = json_str.count("{") - json_str.count("}")
    open_brackets = json_str.count("[") - json_str.count("]")
    json_str = re.sub(r",\s*$", "", json_str)
    json_str += "}" * max(0, open_braces)
    json_str += "]" * max(0, open_brackets)
    json_str = re.sub(r",(\s*[}\]])", r"\1", json_str)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        last_close = json_str.rfind("}")
        if last_close > 0 and json_str.lstrip().startswith("["):
            repaired = json_str[: last_close + 1] + "]"
            repaired = re.sub(r",(\s*\])", r"\1", repaired)
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass
        raise ValueError(f"{agent_name}: could not parse JSON from response")
