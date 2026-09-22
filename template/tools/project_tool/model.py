"""Durable project-governance model: root layout, task records, vocabulary.

This is the lowest layer of :mod:`project_tool`. It owns the governed project
root, the task record shape, the status/workflow vocabulary, and pure task
ordering/lookup helpers. It performs no Git access, no YAML parsing, and no
rendering.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

TASK_ID_RE = re.compile(r"^T-\d{3}$")
TASK_TOKEN_RE = re.compile(r"T-\d{3}")

PROJECT_TYPES = {"script", "library", "backend", "frontend", "fullstack", "template"}
RUNTIME_LEVELS = {"local", "shared", "production"}
GOVERNANCE_MODES = {"lightweight", "managed"}
WORKFLOW_MODES = {"local", "branch", "pr"}
RISKS = {"low", "medium", "high"}
PROJECT_STATUSES = {"active", "paused", "done", "retired"}
LIFECYCLE_PHASES = {
    "inception",
    "discovery",
    "definition",
    "architecture",
    "bootstrap",
    "delivery",
    "production-readiness",
    "operation",
    "evolution",
    "retirement",
}
TASK_STATUSES = {
    "backlog",
    "ready",
    "in-progress",
    "review",
    "blocked",
    "done",
    "cancelled",
}
APPROVAL_LEVELS = {"A0", "A1", "A2"}
APPROVAL_STATUSES = {"not-required", "pending", "approved", "rejected"}
# Levels whose A1/A2 approval boundary is the human GitHub merge when the
# project runs the `pr` workflow mode.
GITHUB_MERGE_LEVELS = {"A1", "A2"}


def discover_root() -> Path:
    """Return the governed project root for this invocation."""
    cwd = Path.cwd()
    if (cwd / "project" / "state.yaml").exists():
        return cwd
    # <root>/tools/project_tool/model.py -> <root>
    return Path(__file__).resolve().parents[2]


ROOT = discover_root()
STATE_PATH = ROOT / "project" / "state.yaml"
TASKS_DIR = ROOT / "project" / "tasks"


class ProjectError(Exception):
    """A governance problem that must be reported to the user as an error."""


@dataclass(frozen=True)
class Task:
    """A durable task record loaded from ``project/tasks/*.md``."""

    id: str
    title: str
    status: str
    priority: int
    milestone: str
    depends_on: tuple[str, ...]
    approval_level: str
    approval_status: str
    approved_by: str | None
    approved_at: str | None
    blocked_reason: str | None
    unblock_action: str | None
    path: Path
    body: str


def state_workflow_mode(state: dict[str, Any]) -> str:
    """Return the project workflow mode, defaulting to local for legacy state."""
    return str(state.get("project", {}).get("workflow_mode", "local"))


def is_github_pr_mode(state: dict[str, Any]) -> bool:
    """Whether completion is derived from a human GitHub merge."""
    return state_workflow_mode(state) == "pr"


def relative(path: Path, base: Path = ROOT) -> str:
    """Return ``path`` relative to ``base`` in POSIX form when possible."""
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def nonempty(value: Any) -> str | None:
    """Return ``value`` as stripped text, or ``None`` when it is empty."""
    if value is None:
        return None
    if isinstance(value, (dict, list)) and not value:
        return None
    # Containers are handled above, so the remainder is an untyped YAML scalar.
    scalar_value = cast("str | int | float | bool", value)
    return str(scalar_value).strip() or None


def task_by_id(tasks: list[Task]) -> dict[str, Task]:
    """Index task records by id."""
    return {task.id: task for task in tasks}


def task_sort_key(task: Task) -> tuple[int, int, str]:
    """Order tasks by priority, then numeric id, then title."""
    number = int(task.id.split("-")[1]) if TASK_ID_RE.match(task.id) else 999999
    return (task.priority, number, task.title)


def find_active(tasks: list[Task], state: dict[str, Any]) -> Task | None:
    """Return the task referenced by ``work.active_task``, when it exists."""
    active = nonempty(state.get("work", {}).get("active_task"))
    return task_by_id(tasks).get(active) if active else None
