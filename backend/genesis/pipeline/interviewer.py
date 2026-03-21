"""Interviewer agent — multi-turn discovery conversation.

Uses Claude Agent SDK for multi-turn conversation management.
"""

from __future__ import annotations

import logging
from typing import Any

from genesis.agents.claude_client import run_agent, parse_llm_json
from genesis.agents.model_resolver import resolve_model_tier
from genesis.types import FactoryContext, InterviewResult, ModelConfig

logger = logging.getLogger(__name__)

INTERVIEW_SYSTEM_PROMPT = """You are a discovery interviewer for a software factory. Your job is to understand what the user wants to build by asking smart, focused questions.

Interview methodology:
1. WHO — Who are the users/personas? What are their roles?
2. WHAT — What specific features/capabilities are needed?
3. WHY — What problem does this solve? What value does it create?
4. CONSTRAINTS — Technical requirements, compliance needs, integrations?
5. SUCCESS — How will we measure if the feature is successful?

Rules:
- Ask 5-8 questions total, ONE at a time
- Start broad, then drill into specifics
- When you have enough context (5+ good answers), wrap up

When the interview is complete, output your summary as JSON:
{
  "complete": true,
  "summary": "One paragraph summarizing what we learned",
  "questions": [{"question": "...", "category": "who|what|why|constraints|success", "answer": "..."}],
  "suggestedDomain": "business domain",
  "suggestedTechStack": "recommended tech stack",
  "suggestedAssistants": ["quality", "architecture"]
}

If NOT complete, respond with ONLY your next question as plain text."""


async def process_interview_turn(
    feature_request: str,
    conversation_history: list[dict[str, str]],
    factory_context: FactoryContext | None = None,
    model_config: ModelConfig | None = None,
) -> dict[str, Any]:
    """Process one turn of the interview conversation."""
    prompt = f"I want to build: {feature_request}"
    if conversation_history:
        # Build conversation context
        parts = [f"Original request: {feature_request}", ""]
        for msg in conversation_history:
            role = msg.get("role", "user")
            parts.append(f"{role}: {msg.get('content', '')}")
        prompt = "\n".join(parts)

    model = resolve_model_tier("interviewer", model_config)
    result = await run_agent(
        prompt=prompt,
        system_prompt=INTERVIEW_SYSTEM_PROMPT,
        model=model,
        max_turns=1,
    )

    response = result.result or ""

    # Check if JSON (interview complete)
    if '"complete"' in response and '"summary"' in response:
        try:
            data = parse_llm_json(response, "Interviewer")
            if data.get("complete"):
                return {
                    "reply": data.get("summary", response),
                    "complete": True,
                    "result": InterviewResult(**data),
                }
        except (ValueError, KeyError):
            pass

    return {"reply": response, "complete": False, "result": None}
