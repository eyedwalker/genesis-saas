"""Build conversation API — guided discovery-to-delivery experience.

Instead of "type feature → build", this creates an interactive conversation
where Claude helps the user think through what to build:

1. User starts a build with a rough idea
2. Claude interviews them (multi-turn)
3. User can upload documents, images, mockups at any time
4. User can paste website URLs for Claude to scan and learn from
5. Claude synthesizes everything into requirements
6. User reviews and refines before any code is generated
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from genesis.auth.middleware import CurrentUser, get_current_user
from genesis.db.models import Activity, Build, Factory
from genesis.db.session import get_session

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────


class StartConversationRequest(BaseModel):
    factory_id: str
    initial_idea: str
    assistant_ids: list[str] | None = None  # Which assistants guide this build


class SendMessageRequest(BaseModel):
    message: str
    attachments: list[dict[str, str]] | None = None  # [{type, name, content}]


class ScanWebsiteRequest(BaseModel):
    url: str
    scan_type: str = "full"  # full, design_only, content_only


class ConversationMessage(BaseModel):
    role: str  # user, assistant, system
    content: str
    attachments: list[dict[str, str]] | None = None
    timestamp: str


class ConversationState(BaseModel):
    build_id: str
    factory_id: str
    phase: str  # discovery, requirements, design, planning, building, reviewing
    messages: list[ConversationMessage]
    context: dict[str, Any]  # uploaded docs, scanned sites, etc.
    artifacts: dict[str, Any] | None = None  # synthesized personas, features, etc.
    ready_to_build: bool


# ── Helpers ────────────────────────────────────────────────────────────────────


def _get_conversation_log(build: Build) -> list[dict]:
    """Get or initialize the conversation log from build's interview_log."""
    return (build.interview_log or {}).get("messages", [])


def _save_conversation(build: Build, messages: list[dict], context: dict | None = None):
    """Save conversation state to build."""
    log = build.interview_log or {}
    log["messages"] = messages
    if context:
        log["context"] = {**log.get("context", {}), **context}
    build.interview_log = log


def _get_context(build: Build) -> dict:
    """Get accumulated context (uploads, scans, etc.)."""
    return (build.interview_log or {}).get("context", {})


def _build_conversation_state(build: Build, ready: bool = False) -> ConversationState:
    """Build a ConversationState with synthesized artifacts."""
    messages = _get_conversation_log(build)
    ctx = _get_context(build)

    # Run synthesis on every response
    from genesis.pipeline.discovery_engine import synthesize_discovery
    artifacts = synthesize_discovery(messages, ctx)

    phase = "discovery"
    if build.status == "requirements_review":
        phase = "requirements"
    elif build.status in ("design", "design_review"):
        phase = "design"
    elif build.status in ("planning", "plan_review"):
        phase = "planning"
    elif build.status == "building":
        phase = "building"
    elif build.status in ("reviewing", "code_review", "qa_review"):
        phase = "reviewing"

    return ConversationState(
        build_id=build.id,
        factory_id=build.factory_id,
        phase=phase,
        messages=[ConversationMessage(**m) for m in messages],
        context=ctx,
        artifacts=artifacts,
        ready_to_build=ready or build.status != "interviewing",
    )


def _get_discovery_assistants() -> str:
    """Get discovery-focused assistant methodologies to guide the interview."""
    try:
        from genesis.assistants.catalog import ALL_ASSISTANTS
        discovery_domains = {"project", "ba"}
        discovery_assistants = [a for a in ALL_ASSISTANTS if a.domain in discovery_domains and a.is_active]
        if discovery_assistants:
            parts = ["\n\nYou are guided by these discovery methodologies:\n"]
            for a in discovery_assistants:
                parts.append(f"### {a.name}\n{a.system_prompt}\n")
            return "\n".join(parts)
    except ImportError:
        pass
    return ""


def _build_system_prompt(factory: Factory, build: Build) -> str:
    """Build the system prompt for the discovery conversation.

    Incorporates methodologies from discovery assistants (Product Discovery/Cagan,
    Shape Up, JTBD, Lean Requirements) to guide the interview.
    """
    ctx = _get_context(build)
    uploads = ctx.get("uploads", [])
    scans = ctx.get("scans", [])

    prompt = f"""You are a senior product consultant helping a user design a software application. You work for Genesis, an AI Software Factory.

Project Context:
- Factory: {factory.name}
- Domain: {factory.domain}
- Tech Stack: {factory.tech_stack or 'To be determined'}

Your role in this conversation:
1. UNDERSTAND the real problem — not just what the user says they want to build, but WHY
2. EXPLORE who the users are, what they're struggling with, what outcomes matter
3. CHALLENGE assumptions — ask for evidence, push back on vague answers
4. SHAPE the scope — help define what's in and what's out for v1
5. DO NOT start building code — help them think through the product first

You blend multiple discovery frameworks:
- PRODUCT DISCOVERY (Cagan): Focus on the problem space, assess value/usability/feasibility/viability risks
- JOBS-TO-BE-DONE (Christensen/Moesta): Uncover the real job customers are hiring this product to do
- SHAPE UP (Singer): Define appetite (time boundary), identify rabbit holes, establish no-gos
- LEAN STARTUP (Ries): Frame as testable hypothesis, find riskiest assumption, define minimum viable scope

Rules:
- Ask ONE question at a time (don't overwhelm)
- When a user describes a solution, redirect to the underlying problem
- Reference any documents, images, or websites they've shared
- Be Socratic — help them think, don't interrogate
- Push back gently on vague answers: "Can you give me a specific example?"
- When you have enough context (problem validated, persona clear, scope bounded), tell them you're ready to generate requirements
- Be opinionated — suggest best practices, warn about common pitfalls"""

    # Add discovery assistant methodologies
    prompt += _get_discovery_assistants()

    if uploads:
        prompt += f"\n\nThe user has shared {len(uploads)} document(s)/image(s):"
        for u in uploads:
            prompt += f"\n- {u['name']} ({u['type']})"
            if u.get("summary"):
                prompt += f": {u['summary']}"

    if scans:
        prompt += f"\n\nThe user has shared {len(scans)} website(s) for reference:"
        for s in scans:
            prompt += f"\n- {s['url']}"
            if s.get("summary"):
                prompt += f": {s['summary']}"

    return prompt


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.post("/start", response_model=ConversationState)
async def start_conversation(
    body: StartConversationRequest,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Start a new guided build conversation.

    Creates a build in 'interviewing' state and begins the discovery process.
    Claude will ask questions to understand what the user wants to build.
    """
    factory = await db.get(Factory, body.factory_id)
    if not factory or factory.tenant_id != current.tenant_id:
        raise HTTPException(404, "Factory not found")

    # Resolve selected assistants
    selected_assistants = body.assistant_ids
    if not selected_assistants:
        # Default: all active assistants
        try:
            from genesis.assistants.catalog import get_active_assistants
            selected_assistants = [a.id for a in get_active_assistants()]
        except ImportError:
            selected_assistants = []

    # Create build in interviewing state
    build = Build(
        tenant_id=current.tenant_id,
        factory_id=body.factory_id,
        requested_by_id=current.user_id,
        feature_request=body.initial_idea,
        build_mode="guided",
        status="interviewing",
        interview_log={"context": {"selected_assistants": selected_assistants}},
    )
    db.add(build)
    await db.flush()

    # Initialize conversation with Claude's first response
    system_prompt = _build_system_prompt(factory, build)
    initial_messages = [
        {
            "role": "user",
            "content": body.initial_idea,
            "timestamp": datetime.utcnow().isoformat(),
        }
    ]

    # Get Claude's first response
    try:
        from genesis.agents.claude_client import run_agent

        result = await run_agent(
            prompt=f"A user wants to build: {body.initial_idea}\n\nThis is a {factory.domain} project using {factory.tech_stack or 'Python/FastAPI'}.\n\nStart by acknowledging their idea, then ask your first discovery question.",
            system_prompt=system_prompt,
            model="sonnet",
            max_turns=1,
        )
        assistant_reply = result.result or "I'd love to help you build this! Let me ask a few questions to make sure we build exactly what you need. Who are the primary users of this application?"
    except Exception as e:
        logger.warning("Claude not available for interview, using fallback: %s", e)
        assistant_reply = (
            f"Great idea! I'd love to help you build this {factory.domain} application. "
            f"Let me ask a few questions to make sure we design it right.\n\n"
            f"First — who are the primary users of this application, and what's their main goal?"
        )

    initial_messages.append({
        "role": "assistant",
        "content": assistant_reply,
        "timestamp": datetime.utcnow().isoformat(),
    })

    _save_conversation(build, initial_messages)
    await db.flush()

    # Log activity
    db.add(Activity(
        tenant_id=current.tenant_id,
        build_id=build.id, user_id=current.user_id,
        type="build_created", stage="interviewing",
        summary=f"Started guided build: {body.initial_idea[:100]}",
    ))
    await db.flush()

    return _build_conversation_state(build)


@router.post("/{build_id}/message", response_model=ConversationState)
async def send_message(
    build_id: str,
    body: SendMessageRequest,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Send a message in the build conversation.

    Claude will respond with follow-up questions, suggestions, or
    indicate readiness to generate requirements.
    """
    build = await db.get(Build, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    factory = await db.get(Factory, build.factory_id)
    if not factory or factory.tenant_id != current.tenant_id:
        raise HTTPException(404, "Build not found")

    messages = _get_conversation_log(build)

    # Add user message
    user_msg = {
        "role": "user",
        "content": body.message,
        "timestamp": datetime.utcnow().isoformat(),
    }
    if body.attachments:
        user_msg["attachments"] = body.attachments
        # Add attachment summaries to context
        ctx = _get_context(build)
        uploads = ctx.get("uploads", [])
        for att in body.attachments:
            uploads.append({
                "name": att.get("name", "unnamed"),
                "type": att.get("type", "document"),
                "summary": att.get("content", "")[:500],
            })
        _save_conversation(build, messages, {"uploads": uploads})

    messages.append(user_msg)

    # Build conversation for Claude
    system_prompt = _build_system_prompt(factory, build)
    claude_messages = []
    for m in messages:
        role = m["role"]
        if role in ("user", "assistant"):
            claude_messages.append({"role": role, "content": m["content"]})

    # Get Claude's response
    try:
        from genesis.agents.claude_client import run_agent

        # Build the full conversation context
        convo_text = "\n\n".join(
            f"{'User' if m['role'] == 'user' else 'You'}: {m['content']}"
            for m in claude_messages
        )

        result = await run_agent(
            prompt=f"Continue this discovery conversation:\n\n{convo_text}\n\nRespond to the user's latest message. Ask follow-up questions if needed, or if you have enough context, say you're ready to generate requirements.",
            system_prompt=system_prompt,
            model="sonnet",
            max_turns=1,
        )
        assistant_reply = result.result or "Could you tell me more about that?"
    except Exception as e:
        logger.warning("Claude not available: %s", e)
        assistant_reply = "Thanks for sharing that! Could you tell me more about the user workflow you're envisioning?"

    messages.append({
        "role": "assistant",
        "content": assistant_reply,
        "timestamp": datetime.utcnow().isoformat(),
    })

    _save_conversation(build, messages)
    await db.flush()

    # Check if Claude thinks we're ready
    ready = any(
        phrase in assistant_reply.lower()
        for phrase in [
            "ready to generate", "enough context", "ready to create requirements",
            "shall i generate", "let me draft", "ready to proceed",
        ]
    )

    return _build_conversation_state(build, ready=ready)


@router.post("/{build_id}/scan-website")
async def scan_website(
    build_id: str,
    body: ScanWebsiteRequest,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Scan a website URL and add it as context for the build.

    Claude will analyze the site's design, structure, and content
    to inform the build. SSRF-protected: blocks private/internal IPs.
    """
    # SSRF protection
    from genesis.auth.ssrf import validate_url
    validate_url(body.url)

    build = await db.get(Build, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    factory = await db.get(Factory, build.factory_id)
    if not factory or factory.tenant_id != current.tenant_id:
        raise HTTPException(404, "Build not found")

    # Fetch and analyze the website (real HTTP fetch, no Claude needed)
    from genesis.pipeline.discovery_engine import scan_website

    scan_result = await scan_website(body.url)

    # Build rich summary for the conversation
    scan_summary_parts = []
    if scan_result.get("title"):
        scan_summary_parts.append(f"**{scan_result['title']}**")
    if scan_result.get("description"):
        scan_summary_parts.append(scan_result["description"])
    if scan_result.get("tech_stack"):
        scan_summary_parts.append(f"Tech stack: {', '.join(scan_result['tech_stack'])}")
    if scan_result.get("headings"):
        scan_summary_parts.append(f"Key messages: {'; '.join(scan_result['headings'][:3])}")
    if scan_result.get("navigation"):
        nav_labels = [n["label"] for n in scan_result["navigation"][:8]]
        scan_summary_parts.append(f"Navigation: {', '.join(nav_labels)}")
    if scan_result.get("has_login"):
        scan_summary_parts.append("Has authentication/login")
    if scan_result.get("has_pricing"):
        scan_summary_parts.append("Has pricing page")
    if scan_result.get("colors"):
        scan_summary_parts.append(f"Colors: {', '.join(scan_result['colors'][:5])}")

    scan_summary = " | ".join(scan_summary_parts) if scan_summary_parts else scan_result.get("summary", f"Scanned {body.url}")

    # Add full scan data to context
    ctx = _get_context(build)
    scans = ctx.get("scans", [])
    scans.append({
        **scan_result,
        "scan_type": body.scan_type,
        "scanned_at": datetime.utcnow().isoformat(),
    })

    messages = _get_conversation_log(build)
    messages.append({
        "role": "system",
        "content": f"🌐 Website scanned: {body.url}\n\n{scan_summary}",
        "timestamp": datetime.utcnow().isoformat(),
    })

    _save_conversation(build, messages, {"scans": scans})
    await db.flush()

    return {
        "url": body.url,
        "summary": scan_summary,
        "build_id": build.id,
    }


@router.post("/{build_id}/upload")
async def upload_attachment(
    build_id: str,
    file: UploadFile = File(...),
    description: str = Form(""),
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Upload a document, image, or mockup to inform the build.

    Supported: images (png, jpg, gif), documents (pdf, txt, md, docx),
    design files, spreadsheets, etc.
    """
    build = await db.get(Build, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    factory = await db.get(Factory, build.factory_id)
    if not factory or factory.tenant_id != current.tenant_id:
        raise HTTPException(404, "Build not found")

    # Read file content
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(400, "File too large (max 10MB)")

    file_type = file.content_type or "application/octet-stream"
    is_image = file_type.startswith("image/")

    # Analyze the file content
    from genesis.pipeline.discovery_engine import analyze_file

    text_content = content.decode("utf-8", errors="replace") if not is_image else ""
    analysis = analyze_file(text_content, file.filename or "unnamed", file_type)

    if is_image:
        analysis["summary"] = f"Image: {file.filename} ({file_type}, {len(content):,} bytes)"
        analysis["format"] = "image"

    if description:
        analysis["description"] = description
        analysis["summary"] = f"{description} — {analysis.get('summary', '')}"

    # Add to context with full analysis
    ctx = _get_context(build)
    uploads = ctx.get("uploads", [])
    uploads.append({
        **analysis,
        "name": file.filename or "unnamed",
        "type": file_type,
        "size": len(content),
        "uploaded_at": datetime.utcnow().isoformat(),
    })

    messages = _get_conversation_log(build)
    messages.append({
        "role": "system",
        "content": f"📎 File analyzed: {file.filename}\n{analysis.get('summary', '')}",
        "timestamp": datetime.utcnow().isoformat(),
    })

    _save_conversation(build, messages, {"uploads": uploads})
    await db.flush()

    return {
        "filename": file.filename,
        "type": file_type,
        "size": len(content),
        "build_id": build.id,
    }


@router.post("/{build_id}/generate-requirements")
async def generate_requirements(
    build_id: str,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Generate requirements from the conversation.

    Called when user approves moving from discovery to requirements.
    Synthesizes all conversation + uploads + scans into structured requirements.
    """
    build = await db.get(Build, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    factory = await db.get(Factory, build.factory_id)
    if not factory or factory.tenant_id != current.tenant_id:
        raise HTTPException(404, "Build not found")

    messages = _get_conversation_log(build)
    ctx = _get_context(build)

    # Build full context for requirements generation
    convo_text = "\n\n".join(
        f"{'User' if m['role'] == 'user' else 'Claude' if m['role'] == 'assistant' else 'System'}: {m['content']}"
        for m in messages
    )

    uploads_text = ""
    for u in ctx.get("uploads", []):
        uploads_text += f"\n- {u['name']}: {u.get('summary', '')[:500]}"

    scans_text = ""
    for s in ctx.get("scans", []):
        scans_text += f"\n- {s['url']}: {s.get('summary', '')[:500]}"

    full_context = f"""Discovery Conversation:
{convo_text}

Uploaded Documents:{uploads_text or ' None'}

Reference Websites:{scans_text or ' None'}

Original Idea: {build.feature_request}"""

    # Generate requirements
    from genesis.pipeline.requirements_agent import generate_requirements as gen_reqs
    from genesis.types import FactoryContext

    factory_ctx = FactoryContext(
        domain=factory.domain,
        techStack=factory.tech_stack or "",
        name=factory.name,
    )

    try:
        reqs = await gen_reqs(
            feature_request=full_context,
            factory_context=factory_ctx,
        )
        build.requirements_data = reqs.model_dump(by_alias=True)
        build.status = "requirements_review"
    except Exception as e:
        logger.error("Requirements generation failed: %s", e)
        # Store what we have and let user retry
        build.requirements_data = {
            "summary": f"Generated from {len(messages)} conversation messages",
            "stories": [],
            "error": str(e),
        }
        build.status = "requirements_review"

    await db.flush()

    db.add(Activity(
        tenant_id=current.tenant_id,
        build_id=build.id, user_id=current.user_id,
        type="stage_completed", stage="interviewing",
        summary=f"Requirements generated from {len(messages)} messages, {len(ctx.get('uploads', []))} uploads, {len(ctx.get('scans', []))} scans",
    ))
    await db.flush()

    return {
        "build_id": build.id,
        "status": build.status,
        "requirements": build.requirements_data,
        "message_count": len(messages),
        "upload_count": len(ctx.get("uploads", [])),
        "scan_count": len(ctx.get("scans", [])),
    }


@router.get("/{build_id}", response_model=ConversationState)
async def get_conversation(
    build_id: str,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get the current state of a build conversation."""
    build = await db.get(Build, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    factory = await db.get(Factory, build.factory_id)
    if not factory or factory.tenant_id != current.tenant_id:
        raise HTTPException(404, "Build not found")

    messages = _get_conversation_log(build)
    ctx = _get_context(build)

    phase = "discovery"
    if build.status == "requirements_review":
        phase = "requirements"
    elif build.status in ("design", "design_review"):
        phase = "design"
    elif build.status in ("planning", "plan_review"):
        phase = "planning"
    elif build.status == "building":
        phase = "building"
    elif build.status in ("reviewing", "code_review", "qa_review"):
        phase = "reviewing"

    return _build_conversation_state(build)
