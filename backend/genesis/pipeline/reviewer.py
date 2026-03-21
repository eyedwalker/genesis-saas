"""Reviewer — multi-assistant code review with Vibe Score.

Uses Claude Agent SDK to run multiple review agents in parallel,
each with Read/Grep tools so they can explore the code themselves.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from claude_agent_sdk import AgentDefinition

from genesis.agents.claude_client import run_agent, parse_llm_json
from genesis.agents.model_resolver import resolve_model_tier
from genesis.types import (
    AssistantConfig,
    Finding,
    ModelConfig,
    ReviewRequest,
    ReviewResponse,
    ReviewSynthesis,
    Severity,
)

logger = logging.getLogger(__name__)

REVIEW_OUTPUT_INSTRUCTIONS = """
Return your findings as a JSON array. Each finding:
{"title": "...", "severity": "critical|high|medium|low", "pattern": "...", "description": "...", "location": "file:line", "recommendation": "...", "codeExample": "..."}
Return ONLY the JSON array. If no issues, return: []
"""

# ── Vibe Score calculation ─────────────────────────────────────────────────

SEVERITY_PENALTIES: dict[Severity, int] = {
    Severity.CRITICAL: 15, Severity.HIGH: 8,
    Severity.MEDIUM: 3, Severity.LOW: 1,
}

SEVERITY_ORDER = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]


def _score_to_grade(score: int) -> str:
    if score >= 95: return "A+"
    if score >= 90: return "A"
    if score >= 80: return "B"
    if score >= 70: return "C"
    if score >= 60: return "D"
    return "F"


def synthesize_findings(
    findings: list[Finding], assistants: list[AssistantConfig],
) -> ReviewSynthesis:
    """Calculate Vibe Score — starts at 100, weighted penalties normalized by assistant count."""
    weight_map = {a.id: a.weight for a in assistants}
    total_penalty = sum(
        SEVERITY_PENALTIES.get(Severity(f.severity), 1) * weight_map.get(f.assistant_id, 1.0)
        for f in findings
    )
    normalized = (total_penalty / max(1, len(assistants))) * 3
    vibe_score = max(0, round(100 - normalized))
    grade = _score_to_grade(vibe_score)

    by_severity: dict[str, int] = {s.value: 0 for s in Severity}
    for f in findings:
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1

    by_assistant: dict[str, int] = {}
    for f in findings:
        by_assistant[f.assistant_id] = by_assistant.get(f.assistant_id, 0) + 1

    top_issues = sorted(
        [f for f in findings if f.severity in ("critical", "high")],
        key=lambda f: SEVERITY_ORDER.index(Severity(f.severity)),
    )

    parts = [f"{by_severity.get(s.value, 0)} {s.value}" for s in SEVERITY_ORDER if by_severity.get(s.value, 0)]
    summary = (
        "No issues found. Code looks clean." if not findings
        else f"Found {len(findings)} issue{'s' if len(findings) > 1 else ''}: {', '.join(parts)}. Vibe Score: {vibe_score}/100 ({grade})."
    )

    return ReviewSynthesis(
        vibeScore=vibe_score, grade=grade, summary=summary,
        bySeverity=by_severity, byAssistant=by_assistant,
        topIssues=[f.title for f in top_issues[:10]],
        recommendations=[f.recommendation for f in top_issues[:5]],
    )


# ── Built-in assistants ───────────────────────────────────────────────────

BUILTIN_ASSISTANTS: list[AssistantConfig] = [
    AssistantConfig(id="quality", name="Code Quality", domain="quality",
        description="Code style, best practices, maintainability",
        systemPrompt="You are a code quality reviewer. Focus on: naming, DRY, error handling, type safety, readability.",
        weight=1.0, isActive=True),
    AssistantConfig(id="architecture", name="Architecture", domain="architecture",
        description="Architectural patterns, SOLID, layering",
        systemPrompt="You are an architecture reviewer. Focus on: layered architecture, separation of concerns, SOLID, dependency direction.",
        weight=1.5, isActive=True),
    AssistantConfig(id="compliance", name="Security & Compliance", domain="compliance",
        description="Security vulnerabilities and compliance",
        systemPrompt="You are a security reviewer. Focus on: input validation, injection, XSS, CSRF, auth, secrets, OWASP Top 10.",
        weight=2.0, isActive=True),
    AssistantConfig(id="infrastructure", name="Infrastructure", domain="infrastructure",
        description="DevOps, deployment patterns",
        systemPrompt="You are a DevOps reviewer. Focus on: Dockerfile best practices, env vars, health checks, logging.",
        weight=1.0, isActive=True),
    AssistantConfig(id="frontend", name="Frontend", domain="frontend",
        description="UI code, accessibility, UX",
        systemPrompt="You are a frontend reviewer. Focus on: component structure, accessibility, responsive design, performance.",
        weight=1.0, isActive=True),
    AssistantConfig(id="business", name="Business Logic", domain="business",
        description="Business rule implementation",
        systemPrompt="You are a business logic reviewer. Focus on: correct rules, edge cases, validation, race conditions.",
        weight=1.5, isActive=True),
    AssistantConfig(id="project", name="Project Methodology", domain="project",
        description="Project structure and practices",
        systemPrompt="You are a project reviewer. Focus on: file organization, naming, documentation, test coverage, config patterns.",
        weight=0.5, isActive=True),
    AssistantConfig(id="ba", name="Business Analysis", domain="ba",
        description="Requirements alignment",
        systemPrompt="You are a BA reviewer. Focus on: requirement coverage, AC alignment, missing features, user flow completeness.",
        weight=1.0, isActive=True),
]


def get_assistants_by_ids(ids: list[str] | None = None) -> list[AssistantConfig]:
    if not ids:
        return [a for a in BUILTIN_ASSISTANTS if a.is_active]
    return [a for a in BUILTIN_ASSISTANTS if a.id in ids]


async def _run_assistant_review(
    assistant: AssistantConfig, code: str, language: str,
    context: str | None = None, model_config: ModelConfig | None = None,
) -> list[Finding]:
    """Run a single assistant's review using the Claude Agent SDK."""
    prompt = f"Review this {language} code:\n\n```{language}\n{code}\n```\n{REVIEW_OUTPUT_INSTRUCTIONS}"
    if context:
        prompt = f"Context: {context}\n\n{prompt}"

    model = resolve_model_tier("reviewing", model_config)

    try:
        result = await run_agent(
            prompt=prompt,
            system_prompt=assistant.system_prompt,
            model=model,
            tools=["Read", "Grep"],  # Can explore code
            max_turns=3,
        )

        data = parse_llm_json(result.result or "[]", f"Reviewer ({assistant.id})")
        if not isinstance(data, list):
            return []

        return [
            Finding(
                title=f.get("title", ""), severity=f.get("severity", "low"),
                assistantId=assistant.id, pattern=f.get("pattern", ""),
                description=f.get("description", ""),
                location=f.get("location"), recommendation=f.get("recommendation", ""),
                codeExample=f.get("codeExample"),
            )
            for f in data
        ]
    except Exception as e:
        logger.error("Assistant %s review failed: %s", assistant.id, e)
        return []


async def review_code(request: ReviewRequest) -> ReviewResponse:
    """Run multi-assistant code review in parallel."""
    assistants = get_assistants_by_ids(request.assistant_ids or None)
    if not assistants:
        return ReviewResponse(
            findings=[], assistantsUsed=[],
            synthesis=ReviewSynthesis(vibeScore=100, grade="A+", summary="No assistants selected."),
        )

    results = await asyncio.gather(*[
        _run_assistant_review(a, request.code, request.language, request.context)
        for a in assistants
    ])
    findings = [f for result in results for f in result]
    synthesis = synthesize_findings(findings, assistants)

    return ReviewResponse(
        findings=findings, synthesis=synthesis,
        assistantsUsed=[a.id for a in assistants],
    )
