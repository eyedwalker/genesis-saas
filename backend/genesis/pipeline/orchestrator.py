"""Pipeline Orchestrator — 16-stage build state machine.

Port of wabah/src/lib/genesis/factory-pipeline.ts.
This is the heart of the system. Each call to advance_pipeline()
moves a build through one stage, calling the appropriate AI agent.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from genesis.db.models import Activity, Build
from genesis.pipeline import (
    architect_agent,
    builder_agent,
    design_agent,
    doc_generator,
    requirements_agent,
    reviewer,
    testing_agent,
    work_item_generator,
)
from genesis.types import (
    BuildResult,
    DesignResult,
    FactoryContext,
    ImplementationPlan,
    ModelConfig,
    PipelineStage,
    RequirementsResult,
    ReviewRequest,
)

logger = logging.getLogger(__name__)

# Stage transition map
STAGE_TRANSITIONS: dict[PipelineStage, PipelineStage] = {
    PipelineStage.REQUIREMENTS: PipelineStage.REQUIREMENTS_REVIEW,
    PipelineStage.REQUIREMENTS_REVIEW: PipelineStage.DESIGN,
    PipelineStage.DESIGN: PipelineStage.DESIGN_REVIEW,
    PipelineStage.DESIGN_REVIEW: PipelineStage.PLANNING,
    PipelineStage.INTERVIEWING: PipelineStage.REQUIREMENTS,
    PipelineStage.PLANNING: PipelineStage.PLAN_REVIEW,
    PipelineStage.PLAN_REVIEW: PipelineStage.BUILDING,
    PipelineStage.BUILDING: PipelineStage.REVIEWING,
    PipelineStage.REVIEWING: PipelineStage.CODE_REVIEW,
    PipelineStage.CODE_REVIEW: PipelineStage.QA_REVIEW,
    PipelineStage.QA_REVIEW: PipelineStage.DELIVERABLE_REVIEW,
    PipelineStage.DELIVERABLE_REVIEW: PipelineStage.APPROVED,
    PipelineStage.APPROVED: PipelineStage.EXPORTED,
}

APPROVAL_GATES: set[PipelineStage] = {
    PipelineStage.REQUIREMENTS_REVIEW,
    PipelineStage.DESIGN_REVIEW,
    PipelineStage.PLAN_REVIEW,
    PipelineStage.CODE_REVIEW,
    PipelineStage.QA_REVIEW,
    PipelineStage.DELIVERABLE_REVIEW,
}

AGENT_STAGES: set[PipelineStage] = {
    PipelineStage.REQUIREMENTS,
    PipelineStage.DESIGN,
    PipelineStage.PLANNING,
    PipelineStage.BUILDING,
    PipelineStage.REVIEWING,
}

# Max review-fix iterations before giving up
MAX_REVIEW_FIX_ITERATIONS = 3
VIBE_SCORE_THRESHOLD = 80


async def advance_pipeline(
    build: Build,
    db: AsyncSession,
    factory_context: FactoryContext | None = None,
    model_config: ModelConfig | None = None,
    fast_track: bool = False,
) -> dict[str, Any]:
    """Advance a build through the pipeline.

    For agent stages: runs the AI agent, stores results in the build, advances.
    For approval gates: pauses unless fast_track is enabled.

    Returns dict with 'next_stage', 'result', 'should_continue'.
    """
    current_stage = PipelineStage(build.status)
    logger.info("Advancing build %s from stage %s", build.id, current_stage.value)

    if current_stage in (PipelineStage.EXPORTED, PipelineStage.FAILED):
        return {
            "next_stage": current_stage.value,
            "result": None,
            "should_continue": False,
            "error": "Build is in terminal state",
        }

    next_stage = STAGE_TRANSITIONS.get(current_stage)
    if not next_stage:
        build.status = PipelineStage.FAILED.value
        return {
            "next_stage": PipelineStage.FAILED.value,
            "result": None,
            "should_continue": False,
            "error": f"No transition from {current_stage.value}",
        }

    result: dict[str, Any] = {}

    try:
        if current_stage in AGENT_STAGES:
            result = await _run_agent_stage(
                build, current_stage, factory_context, model_config
            )

        elif current_stage in APPROVAL_GATES:
            if fast_track:
                result = {"gate": current_stage.value, "auto_approved": True}
            else:
                # Don't advance — wait for human approval
                return {
                    "next_stage": current_stage.value,
                    "result": {"gate": current_stage.value, "awaiting": True},
                    "should_continue": False,
                }

        # Update build status
        build.status = next_stage.value
        await db.flush()

        # Log activity
        activity = Activity(
            tenant_id=build.tenant_id,
            build_id=build.id,
            type="stage_completed",
            stage=current_stage.value,
            summary=f"Completed: {current_stage.value} → {next_stage.value}",
        )
        db.add(activity)
        await db.flush()

    except Exception as e:
        logger.error("Pipeline error at %s: %s", current_stage.value, e)
        build.status = PipelineStage.FAILED.value
        await db.flush()
        return {
            "next_stage": PipelineStage.FAILED.value,
            "result": None,
            "should_continue": False,
            "error": str(e),
        }

    return {
        "next_stage": next_stage.value,
        "result": result,
        "should_continue": current_stage in AGENT_STAGES,
    }


async def _run_agent_stage(
    build: Build,
    stage: PipelineStage,
    factory_context: FactoryContext | None,
    model_config: ModelConfig | None,
) -> dict[str, Any]:
    """Run the appropriate AI agent for a pipeline stage."""

    if stage == PipelineStage.REQUIREMENTS:
        # Generate requirements from feature request + interview data
        interview_data = build.interview_log or {}
        from genesis.types import InterviewResult

        interview = (
            InterviewResult(**interview_data) if interview_data else None
        )

        req_result = await requirements_agent.generate_requirements(
            feature_request=build.feature_request,
            interview_result=interview,
            factory_context=factory_context,
            model_config=model_config,
        )
        build.requirements_data = req_result.model_dump(by_alias=True)
        return {"requirements": req_result.model_dump(by_alias=True)}

    elif stage == PipelineStage.DESIGN:
        # Generate design from requirements
        req_data = build.requirements_data or {}
        requirements = RequirementsResult(**req_data)

        design_result = await design_agent.generate_design(
            requirements=requirements,
            factory_context=factory_context,
            design_brief=build.design_brief,
            model_config=model_config,
        )
        build.design_data = design_result.model_dump(by_alias=True)
        return {"design": design_result.model_dump(by_alias=True)}

    elif stage == PipelineStage.PLANNING:
        # Generate plan from requirements + design
        req_data = build.requirements_data or {}
        requirements = RequirementsResult(**req_data)
        design_data = build.design_data
        design = DesignResult(**design_data) if design_data else None

        plan_result = await architect_agent.generate_plan(
            feature_request=build.feature_request,
            requirements=requirements,
            design=design,
            factory_context=factory_context,
            model_config=model_config,
        )
        build.plan = plan_result.model_dump(by_alias=True)

        # Generate work items
        plan_steps = [s.model_dump(by_alias=True) for s in plan_result.steps]
        items = work_item_generator.generate_work_items(
            requirements, plan_steps
        )
        # Store work items in build metadata
        return {
            "plan": plan_result.model_dump(by_alias=True),
            "work_items": items,
        }

    elif stage == PipelineStage.BUILDING:
        # Generate code with self-healing
        req_data = build.requirements_data or {}
        requirements = RequirementsResult(**req_data)
        plan_data = build.plan or {}
        plan = ImplementationPlan(**plan_data)
        design_data = build.design_data
        design = DesignResult(**design_data) if design_data else None

        build_output = await builder_agent.build_with_self_healing(
            plan=plan,
            requirements=requirements,
            design=design,
            factory_context=factory_context,
            model_config=model_config,
        )

        build_result: BuildResult = build_output["result"]
        build.code = build_result.code
        build.file_map = build_result.file_map
        build.original_file_map = build_result.file_map.copy()
        build.iterations = build_output["iterations"]
        return {
            "files_created": build_result.files_created,
            "iterations": build_output["iterations"],
            "success": build_output["success"],
        }

    elif stage == PipelineStage.REVIEWING:
        # Run multi-assistant code review
        if not build.code:
            return {"error": "No code to review"}

        review_request = ReviewRequest(
            code=build.code,
            language="python",
        )
        review_response = await reviewer.review_code(review_request)

        build.vibe_score = review_response.synthesis.vibe_score
        build.vibe_grade = review_response.synthesis.grade
        build.findings = {
            "findings": [f.model_dump(by_alias=True) for f in review_response.findings],
            "synthesis": review_response.synthesis.model_dump(by_alias=True),
        }

        # Auto-fix if Vibe Score is below threshold
        if (
            review_response.synthesis.vibe_score < VIBE_SCORE_THRESHOLD
            and build.iterations < MAX_REVIEW_FIX_ITERATIONS
        ):
            logger.info(
                "Vibe Score %d < %d, auto-fixing (iteration %d)...",
                review_response.synthesis.vibe_score,
                VIBE_SCORE_THRESHOLD,
                build.iterations + 1,
            )
            fixed = await builder_agent.fix_code_from_findings(
                code=build.code,
                file_map=build.file_map or {},
                findings=review_response.findings,
                factory_context=factory_context,
                model_config=model_config,
            )
            # Merge fixed files
            if build.file_map and fixed.file_map:
                build.file_map = {**build.file_map, **fixed.file_map}
            build.code = fixed.code
            build.iterations += 1

        return {
            "vibe_score": review_response.synthesis.vibe_score,
            "grade": review_response.synthesis.grade,
            "findings_count": len(review_response.findings),
        }

    return {}


async def run_full_pipeline(
    build: Build,
    db: AsyncSession,
    factory_context: FactoryContext | None = None,
    model_config: ModelConfig | None = None,
    fast_track: bool = False,
) -> Build:
    """Run the full pipeline from current stage to completion or gate.

    Keeps advancing until hitting an approval gate or terminal state.
    """
    max_steps = 20  # Safety limit
    steps = 0

    while steps < max_steps:
        steps += 1
        result = await advance_pipeline(
            build, db, factory_context, model_config, fast_track
        )

        if not result.get("should_continue"):
            break

    return build
