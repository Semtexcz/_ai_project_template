"""Lifecycle policy: effective status, readiness, dependencies, transitions.

Decisions here are pure: they read task/state records and return status values,
flags, or human-readable blocker reasons. Persistence, Git subprocesses, and CLI
parsing stay out of this module, so a lifecycle-rule change is a local edit.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from project_tool.git import task_merge_completed
from project_tool.model import (
    GITHUB_MERGE_LEVELS,
    TASK_STATUSES,
    Task,
    is_github_pr_mode,
)

TRANSITIONS = {
    "backlog": {"ready", "cancelled"},
    "ready": {"in-progress", "cancelled"},
    "in-progress": {"review", "blocked", "cancelled"},
    "review": {"in-progress", "done", "cancelled"},
    "blocked": {"ready", "in-progress", "cancelled"},
}
DOR_SECTIONS = [
    "Goal",
    "Context",
    "Scope",
    "Out of Scope",
    "Acceptance Criteria",
    "Verification",
    "Documentation Impact",
]
DOD_SECTIONS = ["Verification", "Completion Notes", "Documentation Impact"]
CHECKBOX_RE = re.compile(r"^\s*-\s+\[( |x|X)\]\s+(.+)$")


def effective_status(state: dict[str, Any] | None, task: Task) -> str:
    """Status used for dashboards, planning, and dependency resolution."""
    if task_merge_completed(state, task):
        return "done"
    return task.status


def dependencies_done(
    task: Task,
    tasks_by_id: dict[str, Task],
    *,
    state: dict[str, Any] | None = None,
) -> bool:
    """Whether every declared dependency of ``task`` is complete."""

    def is_complete(dep: str) -> bool:
        dependency = tasks_by_id[dep]
        if dependency.status in {"done", "cancelled"}:
            return True
        return effective_status(state, dependency) in {"done", "cancelled"}

    return all(is_complete(dep) for dep in task.depends_on if dep in tasks_by_id)


def dependency_cycle(tasks: list[Task]) -> list[str] | None:
    """Return the first dependency cycle as a path, or None when acyclic."""
    graph = {task.id: list(task.depends_on) for task in tasks}
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(node: str) -> list[str] | None:
        if node in visiting:
            start = visiting.index(node)
            return visiting[start:] + [node]
        if node in visited:
            return None
        visiting.append(node)
        for dep in graph.get(node, []):
            cycle = visit(dep)
            if cycle:
                return cycle
        visiting.pop()
        visited.add(node)
        return None

    for task in tasks:
        cycle = visit(task.id)
        if cycle:
            return cycle
    return None


def section_content(body: str, title: str) -> str:
    """Return the content of one ``## <title>`` section of a task body."""
    pattern = re.compile(rf"^##\s+{re.escape(title)}\s*$", re.MULTILINE)
    match = pattern.search(body)
    if not match:
        return ""
    start = match.end()
    next_match = re.search(r"^##\s+", body[start:], re.MULTILINE)
    end = start + next_match.start() if next_match else len(body)
    return body[start:end].strip()


def has_real_content(body: str, title: str) -> bool:
    """Whether a task section holds content beyond comments and whitespace."""
    content = section_content(body, title)
    meaningful = [line.strip() for line in content.splitlines() if line.strip()]
    return any(not line.startswith("<!--") for line in meaningful)


def acceptance_checkboxes(task: Task) -> list[tuple[bool, str]]:
    """Return ``(checked, text)`` pairs from the Acceptance Criteria section."""
    content = section_content(task.body, "Acceptance Criteria")
    boxes: list[tuple[bool, str]] = []
    for line in content.splitlines():
        match = CHECKBOX_RE.match(line)
        if match:
            boxes.append((match.group(1).lower() == "x", match.group(2)))
    return boxes


def definition_of_ready(task: Task) -> list[str]:
    """Sections that must be filled before a task can be ready or started."""
    return [section for section in DOR_SECTIONS if not has_real_content(task.body, section)]


def definition_of_done(task: Task) -> list[str]:
    """Sections and checks that must be satisfied before a task can be done."""
    missing = [section for section in DOD_SECTIONS if not has_real_content(task.body, section)]
    boxes = acceptance_checkboxes(task)
    if boxes and any(not checked for checked, _ in boxes):
        missing.append("all Acceptance Criteria checkboxes checked")
    if "TBD" in section_content(task.body, "Documentation Impact").upper():
        missing.append("Documentation Impact resolved")
    return missing


def valid_datetime(value: str | None) -> bool:
    """Whether ``value`` is an ISO datetime accepted for approval metadata."""
    if not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def transition_blocker(
    task: Task,
    new_status: str,
    *,
    tasks: list[Task],
    tasks_by: dict[str, Task],
    state: dict[str, Any],
    reason: str | None = None,
    unblock: str | None = None,
) -> str | None:
    """Return the first reason a controlled transition must be rejected.

    Returns ``None`` when the transition is allowed. The checks and their order
    are the controlled lifecycle boundary: target status, allowed transition,
    block metadata, start gate (A2 approval, single active task, Definition of
    Ready, dependencies), ready gate, and done gate (PR-mode merge boundary,
    A1/A2 approval, Definition of Done).
    """
    if new_status not in TASK_STATUSES:
        return f"Invalid target status {new_status}. Use a supported task status."
    if new_status not in TRANSITIONS.get(task.status, set()) and not (
        task.approval_level == "A0" and task.status == "in-progress" and new_status == "done"
    ):
        return (
            f"Invalid transition: {task.status} -> {new_status}. "
            "Task must pass through the allowed lifecycle."
        )
    if new_status == "blocked" and (not reason or not unblock):
        return (
            "Blocking requires REASON and UNBLOCK. Run: "
            'make task-block TASK=... REASON="..." UNBLOCK="..."'
        )
    if new_status == "in-progress":
        if task.approval_level == "A2" and task.approval_status != "approved":
            return f"Human A2 approval is required for {task.id} before work starts."
        if any(other.status == "in-progress" and other.id != task.id for other in tasks):
            return (
                "Another task is already in-progress. "
                "Move it to review, blocked, done, or cancelled first."
            )
        missing = definition_of_ready(task)
        if missing:
            return f"{task.id} is not ready: {', '.join(missing)}."
        if not dependencies_done(task, tasks_by, state=state):
            return f"{task.id} cannot start until all dependencies are done."
    if new_status == "ready":
        missing = definition_of_ready(task)
        if missing:
            return f"{task.id} is not ready: {', '.join(missing)}."
        if not dependencies_done(task, tasks_by, state=state):
            return f"{task.id} cannot become ready until dependencies are done."
    if new_status == "done":
        if is_github_pr_mode(state) and task.approval_level in GITHUB_MERGE_LEVELS:
            return (
                f"Task {task.id} is {task.approval_level} in workflow_mode=pr. "
                "The human GitHub merge of its pull request is the completion boundary; "
                "make task-complete is not used for A1/A2 tasks in pr mode."
            )
        if task.approval_level in {"A1", "A2"} and task.approval_status != "approved":
            return f"Human {task.approval_level} approval is required for {task.id} before done."
        missing = definition_of_done(task)
        if missing:
            return f"{task.id} cannot be done: {', '.join(missing)}."
    return None


def approval_blocker(task: Task, state: dict[str, Any]) -> str | None:
    """Return the first reason a human approval cannot be recorded, if any."""
    if task.approval_level == "A0":
        return f"{task.id} is A0 and does not require approval."
    if is_github_pr_mode(state) and task.approval_level == "A1":
        return (
            f"{task.id} is A1 in workflow_mode=pr. The human GitHub merge is the only A1 "
            "approval boundary; do not record a local A1 approval."
        )
    return None
