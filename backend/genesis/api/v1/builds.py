"""Build lifecycle endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from genesis.auth.middleware import CurrentUser, get_current_user
from genesis.db.models import Activity, Approval, Build, Factory
from genesis.db.session import get_session
from genesis.pipeline.orchestrator import advance_pipeline, run_full_pipeline
from genesis.types import FactoryContext, PipelineStage

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────


class BuildCreate(BaseModel):
    factory_id: str
    feature_request: str
    build_mode: str = "feature"
    fast_track: bool = False


class BuildResponse(BaseModel):
    id: str
    factory_id: str
    feature_request: str
    status: str
    vibe_score: int | None = None
    vibe_grade: str | None = None
    iterations: int = 0
    build_mode: str = "feature"
    file_map: dict[str, Any] | None = None
    findings: dict[str, Any] | None = None
    requirements_data: dict[str, Any] | None = None
    design_data: dict[str, Any] | None = None
    plan: dict[str, Any] | None = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class BuildListResponse(BaseModel):
    builds: list[BuildResponse]
    total: int


class AdvanceRequest(BaseModel):
    fast_track: bool = False


class ApprovalRequest(BaseModel):
    type: str  # requirements, design, plan, code, qa, deliverable
    decision: str  # approved, rejected, changes_requested
    comment: str | None = None


class ActivityResponse(BaseModel):
    id: str
    type: str
    stage: str | None
    summary: str
    created_at: str


class ReviewStandaloneRequest(BaseModel):
    code: str
    language: str = "python"
    assistant_ids: list[str] | None = None
    context: str = ""


# ── Helpers ────────────────────────────────────────────────────────────────────


def _build_response(b: Build, detail: bool = False) -> BuildResponse:
    return BuildResponse(
        id=b.id,
        factory_id=b.factory_id,
        feature_request=b.feature_request,
        status=b.status,
        vibe_score=b.vibe_score,
        vibe_grade=b.vibe_grade,
        iterations=b.iterations,
        build_mode=b.build_mode,
        file_map=b.file_map if detail else None,
        findings=b.findings if detail else None,
        requirements_data=b.requirements_data if detail else None,
        design_data=b.design_data if detail else None,
        plan=b.plan if detail else None,
        created_at=b.created_at.isoformat(),
        updated_at=b.updated_at.isoformat(),
    )


def _factory_context(factory: Factory) -> FactoryContext:
    return FactoryContext(
        domain=factory.domain,
        techStack=factory.tech_stack or "",
        name=factory.name,
    )


async def _get_build_with_tenant_check(
    build_id: str,
    tenant_id: str,
    db: AsyncSession,
) -> tuple[Build, Factory]:
    build = await db.get(Build, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    factory = await db.get(Factory, build.factory_id)
    if not factory or factory.tenant_id != tenant_id:
        raise HTTPException(404, "Build not found")
    return build, factory


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.get("", response_model=BuildListResponse)
async def list_builds(
    factory_id: str | None = None,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """List builds, optionally filtered by factory."""
    query = (
        select(Build)
        .join(Factory)
        .where(Factory.tenant_id == current.tenant_id)
        .order_by(Build.created_at.desc())
    )
    if factory_id:
        query = query.where(Build.factory_id == factory_id)

    result = await db.execute(query)
    builds = result.scalars().all()

    return BuildListResponse(
        builds=[_build_response(b) for b in builds],
        total=len(builds),
    )


@router.post("", response_model=BuildResponse, status_code=201)
async def create_build(
    body: BuildCreate,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Create a new build and start the pipeline."""
    factory = await db.get(Factory, body.factory_id)
    if not factory or factory.tenant_id != current.tenant_id:
        raise HTTPException(404, "Factory not found")

    build = Build(
        tenant_id=current.tenant_id,
        factory_id=body.factory_id,
        requested_by_id=current.user_id,
        feature_request=body.feature_request,
        build_mode=body.build_mode,
        status="requirements",
    )
    db.add(build)
    await db.flush()

    activity = Activity(
        tenant_id=current.tenant_id,
        build_id=build.id,
        user_id=current.user_id,
        type="build_created",
        summary=f"Build created: {body.feature_request[:100]}",
    )
    db.add(activity)
    await db.flush()

    return _build_response(build)


@router.get("/{build_id}", response_model=BuildResponse)
async def get_build(
    build_id: str,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get full build details including artifacts."""
    build, _ = await _get_build_with_tenant_check(
        build_id, current.tenant_id, db
    )
    return _build_response(build, detail=True)


@router.delete("/{build_id}", status_code=204)
async def delete_build(
    build_id: str,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Delete a build and all associated data (activities, comments, etc.)."""
    build, factory = await _get_build_with_tenant_check(
        build_id, current.tenant_id, db
    )

    # Delete associated records first
    from genesis.db.models import Activity, Approval, BuildComment, WorkItem, Document
    from sqlalchemy import delete

    for model in [Activity, Approval, BuildComment, WorkItem, Document]:
        await db.execute(
            delete(model).where(model.build_id == build_id)
        )

    await db.delete(build)
    await db.flush()


@router.post("/{build_id}/advance", response_model=BuildResponse)
async def advance_build(
    build_id: str,
    body: AdvanceRequest | None = None,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Advance build to the next pipeline stage.

    Runs the appropriate AI agent for agent stages.
    For approval gates, use POST /approve instead.
    """
    build, factory = await _get_build_with_tenant_check(
        build_id, current.tenant_id, db
    )

    if build.status in ("exported", "failed"):
        raise HTTPException(400, f"Build is in terminal state: {build.status}")

    fast_track = body.fast_track if body else False
    ctx = _factory_context(factory)

    result = await advance_pipeline(
        build=build,
        db=db,
        factory_context=ctx,
        fast_track=fast_track or factory.fast_track,
    )

    if result.get("error"):
        raise HTTPException(400, result["error"])

    return _build_response(build, detail=True)


@router.post("/{build_id}/run")
async def run_build_pipeline(
    build_id: str,
    body: AdvanceRequest | None = None,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Run the full pipeline from current stage until it hits a gate or completes.

    This is the main endpoint for fast-track builds that auto-advance through all stages.
    """
    build, factory = await _get_build_with_tenant_check(
        build_id, current.tenant_id, db
    )

    if build.status in ("exported", "failed"):
        raise HTTPException(400, f"Build is in terminal state: {build.status}")

    fast_track = body.fast_track if body else False
    ctx = _factory_context(factory)

    build = await run_full_pipeline(
        build=build,
        db=db,
        factory_context=ctx,
        fast_track=fast_track or factory.fast_track,
    )

    return _build_response(build, detail=True)


@router.post("/{build_id}/approve", response_model=BuildResponse)
async def approve_build(
    build_id: str,
    body: ApprovalRequest,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Submit approval at a review gate, then advance to next stage."""
    build, factory = await _get_build_with_tenant_check(
        build_id, current.tenant_id, db
    )

    # Verify build is at an approval gate
    gate_stages = {
        "requirements_review", "design_review", "plan_review",
        "code_review", "qa_review", "deliverable_review",
    }
    if build.status not in gate_stages:
        raise HTTPException(
            400, f"Build is not at an approval gate (current: {build.status})"
        )

    # Record approval
    approval = Approval(
        tenant_id=current.tenant_id,
        build_id=build.id,
        user_id=current.user_id,
        type=body.type,
        decision=body.decision,
        comment=body.comment,
    )
    db.add(approval)

    activity = Activity(
        tenant_id=current.tenant_id,
        build_id=build.id,
        user_id=current.user_id,
        type="approval_submitted",
        stage=build.status,
        summary=f"{body.decision}: {body.comment or 'No comment'}",
    )
    db.add(activity)

    if body.decision == "approved":
        # Advance past the gate
        ctx = _factory_context(factory)
        await advance_pipeline(
            build=build,
            db=db,
            factory_context=ctx,
            fast_track=True,  # Force past gate since approved
        )
    elif body.decision == "rejected":
        build.status = "failed"

    await db.flush()
    return _build_response(build, detail=True)


@router.get("/{build_id}/stream")
async def stream_build(
    build_id: str,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """SSE stream for real-time build progress."""
    build, factory = await _get_build_with_tenant_check(
        build_id, current.tenant_id, db
    )

    async def event_generator():
        """Yield SSE events as the build progresses."""
        last_status = build.status
        yield f"data: {json.dumps({'type': 'status', 'stage': last_status, 'build_id': build.id})}\n\n"

        # Poll for changes (in production, use Redis pub/sub)
        for _ in range(300):  # 5 min max
            await asyncio.sleep(1)
            await db.refresh(build)
            if build.status != last_status:
                last_status = build.status
                event = {
                    "type": "stage_change",
                    "stage": last_status,
                    "build_id": build.id,
                    "vibe_score": build.vibe_score,
                }
                yield f"data: {json.dumps(event)}\n\n"

                if last_status in ("exported", "failed", "approved"):
                    yield f"data: {json.dumps({'type': 'complete', 'stage': last_status})}\n\n"
                    return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{build_id}/activities", response_model=list[ActivityResponse])
async def list_activities(
    build_id: str,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """List activity log for a build."""
    build, _ = await _get_build_with_tenant_check(
        build_id, current.tenant_id, db
    )

    result = await db.execute(
        select(Activity)
        .where(Activity.build_id == build_id)
        .order_by(Activity.created_at.desc())
    )
    activities = result.scalars().all()

    return [
        ActivityResponse(
            id=a.id,
            type=a.type,
            stage=a.stage,
            summary=a.summary,
            created_at=a.created_at.isoformat(),
        )
        for a in activities
    ]


@router.get("/{build_id}/filemap")
async def get_filemap(
    build_id: str,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Get generated file map for a build."""
    build, _ = await _get_build_with_tenant_check(
        build_id, current.tenant_id, db
    )
    return {"file_map": build.file_map or {}, "build_id": build.id}
