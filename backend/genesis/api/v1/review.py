"""Standalone code review endpoint — Vibe Score without a full build."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends

from genesis.auth.middleware import CurrentUser, get_current_user
from genesis.pipeline.reviewer import review_code
from genesis.types import ReviewRequest, ReviewResponse

router = APIRouter()


class StandaloneReviewRequest(BaseModel):
    code: str
    language: str = "python"
    assistant_ids: list[str] | None = None
    context: str = ""


class StandaloneReviewResponse(BaseModel):
    vibe_score: int
    grade: str
    summary: str
    findings_count: int
    findings: list[dict]
    recommendations: list[str]
    assistants_used: list[str]


@router.post("", response_model=StandaloneReviewResponse)
async def standalone_review(
    body: StandaloneReviewRequest,
    current: CurrentUser = Depends(get_current_user),
):
    """Run a standalone code review and get a Vibe Score.

    This doesn't require a factory or build — just paste code and get scored.
    """
    request = ReviewRequest(
        code=body.code,
        language=body.language,
        assistantIds=body.assistant_ids or [],
        context=body.context,
    )
    response = await review_code(request)

    return StandaloneReviewResponse(
        vibe_score=response.synthesis.vibe_score,
        grade=response.synthesis.grade,
        summary=response.synthesis.summary,
        findings_count=len(response.findings),
        findings=[f.model_dump(by_alias=True) for f in response.findings],
        recommendations=response.synthesis.recommendations,
        assistants_used=response.assistants_used,
    )
