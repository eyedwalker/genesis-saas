"""Claude Agent SDK client for pipeline agents.

Uses claude-agent-sdk (claude_agent_sdk) with per-tenant API key auth.
Every call passes the tenant's ANTHROPIC_API_KEY via env.
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

from genesis.config import settings

logger = logging.getLogger(__name__)

# Thread-local tenant API key (set per-request)
_current_api_key: str | None = None


def set_tenant_api_key(key: str | None) -> None:
    """Set the API key for the current tenant's request."""
    global _current_api_key
    _current_api_key = key


def _get_env() -> dict[str, str]:
    """Get env vars for the Claude SDK process, including the API key."""
    env: dict[str, str] = {}
    # Priority: tenant key > server-level key > config key
    key = _current_api_key or settings.anthropic_api_key
    if key:
        env["ANTHROPIC_API_KEY"] = key
    return env


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
    api_key: str | None = None,
) -> ResultMessage:
    """Run a Claude agent and return the result.

    Uses the tenant's API key if available, falls back to server config.
    """
    env = _get_env()
    if api_key:
        env["ANTHROPIC_API_KEY"] = api_key

    # If no API key, that's OK — SDK will use Claude Max/Pro auth from CLI login

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
        env=env,
    )

    result: ResultMessage | None = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            result = message

    if result is None:
        raise RuntimeError("Agent returned no result")

    if result.is_error:
        raise RuntimeError(f"Agent error: {result.result}")

    logger.info(
        "Agent completed: %d turns, $%.4f",
        result.num_turns,
        result.total_cost_usd or 0,
    )
    return result


async def run_conversation(
    messages: list[dict[str, str]],
    new_message: str,
    system_prompt: str | None = None,
    model: str = "sonnet",
    max_turns: int | None = 1,
    api_key: str | None = None,
) -> ResultMessage:
    """Run a conversation turn with full message history.

    Instead of fragile session resume, we send the complete conversation
    history + the new message as a single prompt. Claude sees everything
    and responds naturally. This survives container restarts.
    """
    env = _get_env()
    if api_key:
        env["ANTHROPIC_API_KEY"] = api_key

    # Build conversation history as natural dialogue
    history_parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user":
            history_parts.append(f"User: {content}")
        elif role == "assistant":
            history_parts.append(f"You: {content}")
        elif role == "system":
            history_parts.append(f"[Context: {content}]")

    if history_parts:
        prompt = (
            "Here is our conversation so far:\n\n"
            + "\n\n".join(history_parts)
            + f"\n\nUser: {new_message}"
            + "\n\nContinue the conversation naturally. Reference everything discussed. Don't repeat what you already know."
        )
    else:
        prompt = new_message

    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        model=model,
        max_turns=max_turns,
        permission_mode="bypassPermissions",
        env=env,
    )

    result: ResultMessage | None = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            result = message

    if result is None:
        raise RuntimeError("Agent returned no result")

    if result.is_error:
        raise RuntimeError(f"Agent error: {result.result}")

    logger.info(
        "Conversation: %d turns, $%.4f",
        result.num_turns,
        result.total_cost_usd or 0,
    )
    return result


async def run_agent_structured(
    prompt: str,
    output_schema: dict[str, Any],
    system_prompt: str | None = None,
    model: str = "sonnet",
    tools: list[str] | None = None,
    max_turns: int | None = None,
    cwd: str | Path | None = None,
    api_key: str | None = None,
) -> Any:
    """Run an agent and return structured (JSON) output."""
    result = await run_agent(
        prompt=prompt,
        system_prompt=system_prompt,
        model=model,
        tools=tools,
        max_turns=max_turns,
        cwd=cwd,
        output_format={"type": "json_schema", "schema": output_schema},
        api_key=api_key,
    )

    if result.structured_output is not None:
        return result.structured_output

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
    api_key: str | None = None,
) -> ResultMessage:
    """Run a builder agent with full file system access."""
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
        api_key=api_key,
    )


def parse_llm_json(text: str, agent_name: str = "agent") -> Any:
    """Parse JSON from LLM response, handling common issues."""
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```\s*$", "", text)
    text = text.strip()

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
