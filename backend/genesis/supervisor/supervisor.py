"""Factory Supervisor — orchestrates multiple parallel build sessions.

Each build gets its own ClaudeSDKClient session with full tool access.
The Supervisor manages a pool of concurrent sessions, priority queuing,
cost governance, and cross-project awareness.

This is the key enterprise differentiator: run N builds simultaneously,
each in an isolated Claude session with its own workspace.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AgentDefinition,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
)

logger = logging.getLogger(__name__)


class BuildPriority(str, Enum):
    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


PRIORITY_WEIGHTS = {
    BuildPriority.URGENT: 0,
    BuildPriority.HIGH: 1,
    BuildPriority.NORMAL: 2,
    BuildPriority.LOW: 3,
}


@dataclass
class BuildJob:
    """A build request queued for execution."""

    build_id: str
    factory_id: str
    tenant_id: str
    feature_request: str
    system_prompt: str = ""
    model: str = "sonnet"
    workspace_dir: str | None = None
    priority: BuildPriority = BuildPriority.NORMAL
    fast_track: bool = False
    queued_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cost_usd: float = 0.0
    error: str | None = None
    session_id: str | None = None

    @property
    def sort_key(self) -> tuple[int, datetime]:
        return (PRIORITY_WEIGHTS[self.priority], self.queued_at)


@dataclass
class SessionSlot:
    """A Claude SDK session slot running a build."""

    slot_id: int
    build_job: BuildJob | None = None
    client: ClaudeSDKClient | None = None
    task: asyncio.Task[Any] | None = None

    @property
    def is_available(self) -> bool:
        return self.build_job is None


class Supervisor:
    """Manages concurrent ClaudeSDKClient sessions for parallel builds.

    Features:
    - Configurable concurrency (max_concurrent sessions)
    - Priority queue (urgent > high > normal > low)
    - Cost governor (refuses new builds if credits exhausted)
    - Each build gets an isolated workspace + Claude session
    - Session persistence for resumable builds
    """

    def __init__(
        self,
        tenant_id: str,
        max_concurrent: int = 3,
        cost_limit_usd: float = 50.0,
    ) -> None:
        self.tenant_id = tenant_id
        self.max_concurrent = max_concurrent
        self.cost_limit_usd = cost_limit_usd
        self.cost_used_usd: float = 0.0

        self.slots: list[SessionSlot] = [
            SessionSlot(slot_id=i) for i in range(max_concurrent)
        ]
        self._queue: list[BuildJob] = []
        self._queue_lock = asyncio.Lock()

        # Completed build tracking
        self.builds_completed: int = 0
        self.builds_failed: int = 0
        self._results: dict[str, dict[str, Any]] = {}

    @property
    def active_count(self) -> int:
        return sum(1 for s in self.slots if not s.is_available)

    @property
    def available_count(self) -> int:
        return sum(1 for s in self.slots if s.is_available)

    @property
    def queue_depth(self) -> int:
        return len(self._queue)

    @property
    def has_budget(self) -> bool:
        return self.cost_used_usd < self.cost_limit_usd

    async def submit(self, job: BuildJob) -> dict[str, Any]:
        """Submit a build job. Starts immediately if slot available, else queues.

        Returns dict with 'status' ('running' or 'queued') and 'position'.
        """
        if not self.has_budget:
            return {
                "status": "rejected",
                "reason": f"Cost limit reached: ${self.cost_used_usd:.2f} / ${self.cost_limit_usd:.2f}",
            }

        # Try to assign to an available slot
        for slot in self.slots:
            if slot.is_available:
                await self._start_job(slot, job)
                return {"status": "running", "slot_id": slot.slot_id}

        # Queue it
        async with self._queue_lock:
            self._queue.append(job)
            self._queue.sort(key=lambda j: j.sort_key)
            position = self._queue.index(job)
            logger.info(
                "Build %s queued at position %d (priority: %s)",
                job.build_id, position, job.priority,
            )
            return {"status": "queued", "position": position}

    async def _start_job(self, slot: SessionSlot, job: BuildJob) -> None:
        """Start a build job in a Claude SDK session slot."""
        job.started_at = datetime.utcnow()
        slot.build_job = job

        # Create isolated workspace
        if not job.workspace_dir:
            job.workspace_dir = tempfile.mkdtemp(
                prefix=f"genesis-{job.build_id[:8]}-"
            )

        # Create Claude SDK client with full tool access
        options = ClaudeAgentOptions(
            system_prompt=job.system_prompt or self._default_system_prompt(job),
            model=job.model,
            allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
            permission_mode="bypassPermissions",
            cwd=job.workspace_dir,
            max_turns=30,
            max_budget_usd=min(10.0, self.cost_limit_usd - self.cost_used_usd),
        )

        client = ClaudeSDKClient(options=options)
        slot.client = client
        slot.task = asyncio.create_task(self._run_build(slot, job, client))

        logger.info(
            "Build %s started in slot %d (workspace: %s)",
            job.build_id, slot.slot_id, job.workspace_dir,
        )

    def _default_system_prompt(self, job: BuildJob) -> str:
        return f"""You are a software engineer working on a build for the Genesis Software Factory.

Build ID: {job.build_id}
Feature Request: {job.feature_request}

Your workspace is the current directory. Create all files here.
Follow best practices: layered architecture, input validation, error handling, type safety.
After writing code, run any available linter or type checker.
If validation fails, fix the errors and re-run until clean."""

    async def _run_build(
        self,
        slot: SessionSlot,
        job: BuildJob,
        client: ClaudeSDKClient,
    ) -> None:
        """Execute a build pipeline in a Claude SDK session."""
        try:
            async with client:
                # Send the build prompt
                await client.query(
                    f"Build this feature:\n\n{job.feature_request}",
                )

                # Collect result
                result: ResultMessage | None = None
                async for message in client.receive_response():
                    if isinstance(message, ResultMessage):
                        result = message

                if result:
                    job.cost_usd = result.total_cost_usd or 0.0
                    self.cost_used_usd += job.cost_usd
                    job.session_id = result.session_id

                    # Collect generated files
                    workspace = Path(job.workspace_dir) if job.workspace_dir else None
                    file_map: dict[str, str] = {}
                    if workspace and workspace.exists():
                        for f in workspace.rglob("*"):
                            if f.is_file() and not any(
                                p.startswith(".") or p in ("__pycache__", "node_modules")
                                for p in f.relative_to(workspace).parts
                            ):
                                try:
                                    file_map[str(f.relative_to(workspace))] = f.read_text(errors="replace")
                                except Exception:
                                    pass

                    self._results[job.build_id] = {
                        "success": not result.is_error,
                        "file_map": file_map,
                        "explanation": result.result or "",
                        "cost_usd": job.cost_usd,
                        "session_id": result.session_id,
                        "num_turns": result.num_turns,
                    }

                job.completed_at = datetime.utcnow()
                self.builds_completed += 1
                logger.info(
                    "Build %s completed in slot %d ($%.4f, %d files)",
                    job.build_id, slot.slot_id, job.cost_usd, len(file_map),
                )

        except Exception as e:
            job.error = str(e)
            job.completed_at = datetime.utcnow()
            self.builds_failed += 1
            self._results[job.build_id] = {
                "success": False,
                "error": str(e),
                "file_map": {},
            }
            logger.error("Build %s failed in slot %d: %s", job.build_id, slot.slot_id, e)

        finally:
            # Release slot and clean up
            slot.build_job = None
            slot.client = None
            slot.task = None

            # Clean up workspace
            if job.workspace_dir:
                shutil.rmtree(job.workspace_dir, ignore_errors=True)

            # Pick up next queued job
            await self._process_queue()

    async def _process_queue(self) -> None:
        """Check queue and start next job if a slot is available."""
        async with self._queue_lock:
            if not self._queue:
                return
            for slot in self.slots:
                if slot.is_available and self._queue:
                    next_job = self._queue.pop(0)
                    await self._start_job(slot, next_job)

    def get_result(self, build_id: str) -> dict[str, Any] | None:
        """Get the result of a completed build."""
        return self._results.get(build_id)

    async def cancel(self, build_id: str) -> bool:
        """Cancel a queued or running build."""
        # Check queue first
        async with self._queue_lock:
            for i, job in enumerate(self._queue):
                if job.build_id == build_id:
                    self._queue.pop(i)
                    return True

        # Check running slots
        for slot in self.slots:
            if slot.build_job and slot.build_job.build_id == build_id:
                if slot.client:
                    slot.client.interrupt()
                if slot.task:
                    slot.task.cancel()
                return True

        return False

    def get_status(self) -> dict[str, Any]:
        """Return supervisor status summary."""
        return {
            "tenant_id": self.tenant_id,
            "active_builds": self.active_count,
            "available_slots": self.available_count,
            "max_concurrent": self.max_concurrent,
            "queue_depth": self.queue_depth,
            "cost_used_usd": round(self.cost_used_usd, 4),
            "cost_limit_usd": self.cost_limit_usd,
            "has_budget": self.has_budget,
            "builds_completed": self.builds_completed,
            "builds_failed": self.builds_failed,
            "slots": [
                {
                    "slot_id": s.slot_id,
                    "available": s.is_available,
                    "build_id": s.build_job.build_id if s.build_job else None,
                    "priority": s.build_job.priority.value if s.build_job else None,
                    "started_at": s.build_job.started_at.isoformat() if s.build_job and s.build_job.started_at else None,
                }
                for s in self.slots
            ],
            "queue": [
                {
                    "build_id": j.build_id,
                    "priority": j.priority.value,
                    "queued_at": j.queued_at.isoformat(),
                }
                for j in self._queue
            ],
        }
