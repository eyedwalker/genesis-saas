"""Work item generator — creates epics, stories, tasks from requirements.

Port of wabah/src/lib/genesis/work-item-generator.ts.
Deterministic (no LLM) — converts RequirementsResult into hierarchical work items.
"""

from __future__ import annotations

from genesis.types import RequirementsResult


def generate_work_items(
    requirements: RequirementsResult,
    plan_steps: list[dict[str, str]] | None = None,
) -> list[dict]:
    """Generate hierarchical work items from requirements.

    Returns list of dicts with: type, title, description, priority, parent_id, children.
    """
    items: list[dict] = []
    epic_map: dict[str, str] = {}  # epic name -> epic work item id

    # Create epics
    for i, epic_name in enumerate(requirements.epics):
        epic_id = f"E-{i+1:03d}"
        epic_map[epic_name] = epic_id
        items.append({
            "id": epic_id,
            "type": "epic",
            "title": epic_name,
            "description": f"Epic: {epic_name}",
            "priority": "high",
            "parent_id": None,
            "sort_order": i,
        })

    # Create stories from requirements
    for story in requirements.stories:
        parent_id = epic_map.get(story.epic)
        items.append({
            "id": story.id,
            "type": "story",
            "title": story.title or f"{story.persona}, {story.capability}",
            "description": f"{story.persona}, {story.capability}, {story.benefit}",
            "priority": _normalize_priority(story.priority),
            "parent_id": parent_id,
            "sort_order": 0,
        })

        # Create acceptance criteria as subtasks
        for ac in story.acceptance_criteria:
            items.append({
                "id": ac.id,
                "type": "acceptance_criteria",
                "title": f"AC: {ac.then}",
                "description": f"Given {ac.given}, When {ac.when_}, Then {ac.then}",
                "priority": _normalize_priority(story.priority),
                "parent_id": story.id,
                "sort_order": 0,
            })

    # Create tasks from plan steps
    if plan_steps:
        for i, step in enumerate(plan_steps):
            items.append({
                "id": f"T-{i+1:03d}",
                "type": "task",
                "title": f"Implement: {step.get('filePath', step.get('file_path', ''))}",
                "description": step.get("description", ""),
                "priority": "medium",
                "parent_id": None,
                "sort_order": i,
            })

    return items


def _normalize_priority(priority: str) -> str:
    """Normalize MoSCoW priority to standard priority."""
    mapping = {
        "must": "critical",
        "should": "high",
        "could": "medium",
        "wont": "low",
        "won't": "low",
    }
    return mapping.get(priority.lower(), priority.lower())
