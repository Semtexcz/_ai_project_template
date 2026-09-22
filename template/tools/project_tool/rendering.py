"""User-visible derivation of project status: persisted and runtime views.

Two views are deliberately distinct (T-029 ownership):

* ``persisted_*`` blocks contain only content that is a deterministic function
  of the canonical task/state records, so committed Markdown never encodes a
  merge result that only the human merge can decide.
* ``runtime_*`` blocks are rendered at read time by ``make project-status`` and
  include Git-relative, merge-aware rows and board annotations.

Everything here derives strings; writing files is the mutation layer's job.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from project_tool.git import github_merge_completes, task_merge_completed
from project_tool.lifecycle import dependencies_done, effective_status
from project_tool.model import (
    GITHUB_MERGE_LEVELS,
    ROOT,
    Task,
    find_active,
    is_github_pr_mode,
    relative,
    task_by_id,
    task_sort_key,
)

COLUMNS = [
    ("Backlog", "backlog"),
    ("Ready", "ready"),
    ("In Progress", "in-progress"),
    ("Review", "review"),
    ("Blocked", "blocked"),
    ("Done", "done"),
    ("Cancelled", "cancelled"),
]
INDEX_LINKS = "\n\nLinks: [Board](board.md) | [Roadmap](roadmap.md)"

# Status rows whose truth depends on Git provenance when the project runs
# `workflow_mode: pr`. They are rendered at read time by `make project-status`
# and must never be committed: merge-derived completion cannot be known before
# the human merge lands, so persisting it would make committed Markdown stale by
# definition.
GIT_RELATIVE_STATUS_ROWS = (
    "Last completed task",
    "Waiting",
    "Recommended next action",
    "Next action command",
)
PERSISTED_BLOCK_ROWS = {
    "Project type",
    "Runtime level",
    "Phase",
    "Milestone",
    "Active task",
    "Approval",
    "Blocker",
    "Next gate",
}
PR_BOARD_SNAPSHOT_NOTE = (
    "_Persisted task records by status. Merge-derived completion is not persisted; "
    "run `make project-status` for the live merge-aware board._"
)


def markdown_table(rows: list[tuple[str, str]]) -> str:
    """Render ``rows`` as a two-column Markdown table."""
    lines = ["| Item | Value |", "|---|---|"]
    lines.extend(f"| {key} | {value} |" for key, value in rows)
    return "\n".join(lines)


def task_link(task: Task, base: Path) -> str:
    """Render a relative Markdown link to a task record."""
    return f"[{task.id}]({relative(task.path, base)})"


def approval_text(task: Task | None) -> str:
    """Render the approval level/status summary for ``task``."""
    if not task:
        return "None"
    return f"{task.approval_level} / {task.approval_status}"


def last_completed_task(tasks: list[Task], base: Path, state: dict[str, Any] | None = None) -> str:
    """Render the highest ordered task whose effective status is done."""
    done = sorted(
        (task for task in tasks if effective_status(state, task) == "done"),
        key=task_sort_key,
    )
    if not done:
        return "None"
    return task_link(done[-1], base)


def waiting_text(tasks: list[Task], state: dict[str, Any] | None = None) -> str:
    """Render what the project is waiting on: blocker, approval, or merge."""
    pr_mode = state is not None and is_github_pr_mode(state)
    blocked = sorted((task for task in tasks if task.status == "blocked"), key=task_sort_key)
    if blocked:
        return f"Blocked: {blocked[0].id}"
    review_waiting = sorted(
        (
            task
            for task in tasks
            if task.status == "review"
            and task.approval_level in {"A1", "A2"}
            and not github_merge_completes(state, task)
            and (pr_mode or task.approval_status != "approved")
        ),
        key=task_sort_key,
    )
    if review_waiting:
        task = review_waiting[0]
        if pr_mode:
            return f"Awaiting human GitHub merge: {task.id}"
        return f"{task.approval_level} approval pending: {task.id}"
    pending_a2 = sorted(
        (
            task
            for task in tasks
            if task.status == "ready"
            and task.approval_level == "A2"
            and task.approval_status != "approved"
        ),
        key=task_sort_key,
    )
    if pending_a2:
        return f"A2 approval required before start: {pending_a2[0].id}"
    return "None"


def blocker_text(tasks: list[Task]) -> str:
    """Render the first blocked task and its recorded reason."""
    blocked = sorted((task for task in tasks if task.status == "blocked"), key=task_sort_key)
    if not blocked:
        return "None"
    task = blocked[0]
    return f"{task.id}: {task.blocked_reason or 'blocked'}"


def recommended_next_action(
    state: dict[str, Any], tasks: list[Task], *, invalid: bool = False
) -> str:
    """Render the next lifecycle action implied by current records."""
    if invalid:
        return "Fix project validation errors, then run: make validate-project."
    tasks_by = task_by_id(tasks)
    pr_mode = is_github_pr_mode(state)
    blocked = sorted((task for task in tasks if task.status == "blocked"), key=task_sort_key)
    if blocked:
        task = blocked[0]
        return f"Unblock {task.id} by {task.unblock_action}."
    pending_a2 = sorted(
        (
            task
            for task in tasks
            if task.approval_level == "A2"
            and task.approval_status != "approved"
            and task.status == "ready"
        ),
        key=task_sort_key,
    )
    if pending_a2:
        return f"Human A2 approval is required for {pending_a2[0].id} before work starts."
    in_progress = [task for task in tasks if task.status == "in-progress"]
    if in_progress:
        return f"Complete {in_progress[0].id}."
    review_waiting = sorted(
        (
            task
            for task in tasks
            if task.status == "review"
            and task.approval_level in {"A1", "A2"}
            and not github_merge_completes(state, task)
            and (pr_mode or task.approval_status != "approved")
        ),
        key=task_sort_key,
    )
    if review_waiting:
        task = review_waiting[0]
        if pr_mode:
            return f"Await human GitHub merge for {task.id}; merge is the completion boundary."
        return f"Human {task.approval_level} approval is required for {task.id} before completion."
    ready = sorted(
        (
            task
            for task in tasks
            if task.status == "ready" and dependencies_done(task, tasks_by, state=state)
        ),
        key=task_sort_key,
    )
    if ready:
        return f"Start {ready[0].id}."
    gate = state.get("lifecycle", {}).get("next_gate", "current-gate")
    return f"No ready task exists. Create one task addressing gate {gate}."


def recommended_next_command(
    state: dict[str, Any], tasks: list[Task], *, invalid: bool = False
) -> str:
    """Render the next `make` command implied by current records."""
    if invalid:
        return "`make validate-project`"
    tasks_by = task_by_id(tasks)
    pr_mode = is_github_pr_mode(state)
    blocked = sorted((task for task in tasks if task.status == "blocked"), key=task_sort_key)
    if blocked:
        return f"`make task-unblock TASK={blocked[0].id}`"
    pending_a2 = sorted(
        (
            task
            for task in tasks
            if task.approval_level == "A2"
            and task.approval_status != "approved"
            and task.status == "ready"
        ),
        key=task_sort_key,
    )
    if pending_a2:
        return f'`make task-approve TASK={pending_a2[0].id} APPROVED_BY="<human>"`'
    in_progress = [task for task in tasks if task.status == "in-progress"]
    if in_progress:
        return f"`make task-review TASK={in_progress[0].id}`"
    review_waiting = sorted(
        (
            task
            for task in tasks
            if task.status == "review"
            and task.approval_level in {"A1", "A2"}
            and not github_merge_completes(state, task)
            and (pr_mode or task.approval_status != "approved")
        ),
        key=task_sort_key,
    )
    if review_waiting:
        task = review_waiting[0]
        if pr_mode:
            return f"`make project-status` (await human GitHub merge of {task.id})."
        return f'`make task-approve TASK={task.id} APPROVED_BY="<human>"`'
    ready = sorted(
        (
            task
            for task in tasks
            if task.status == "ready" and dependencies_done(task, tasks_by, state=state)
        ),
        key=task_sort_key,
    )
    if ready:
        return f"`make task-start TASK={ready[0].id}`"
    return "`make task-ready TASK=<new-task-id>`"


def status_rows(state: dict[str, Any], tasks: list[Task]) -> list[tuple[str, str]]:
    """All status rows, including the Git-relative ones."""
    project = state["project"]
    lifecycle = state["lifecycle"]
    active = find_active(tasks, state)
    active_value = task_link(active, ROOT) if active else "None"
    return [
        ("Project type", str(project["type"])),
        ("Runtime level", str(project["runtime_level"])),
        ("Phase", str(lifecycle["phase"])),
        ("Milestone", str(lifecycle["milestone"])),
        ("Last completed task", last_completed_task(tasks, ROOT, state)),
        ("Active task", active_value),
        ("Approval", approval_text(active)),
        ("Waiting", waiting_text(tasks, state)),
        ("Blocker", blocker_text(tasks)),
        ("Next gate", str(lifecycle["next_gate"])),
        ("Recommended next action", recommended_next_action(state, tasks)),
        ("Next action command", recommended_next_command(state, tasks)),
    ]


def persisted_rows(state: dict[str, Any], rows: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Drop Git-relative rows when completion is derived from a GitHub merge."""
    if not is_github_pr_mode(state):
        return rows
    return [(key, value) for key, value in rows if key not in GIT_RELATIVE_STATUS_ROWS]


def runtime_status_block(state: dict[str, Any], tasks: list[Task]) -> str:
    """Merge-aware status table rendered at read time by `make project-status`."""
    return markdown_table(status_rows(state, tasks))


def persisted_status_block(state: dict[str, Any], tasks: list[Task]) -> str:
    """Status rows that are deterministic functions of the canonical records.

    In `workflow_mode: pr` the Git-relative rows are omitted, so committed
    Markdown never encodes a lifecycle result that only the human merge decides
    and never needs a post-merge reconciliation commit.
    """
    return markdown_table(persisted_rows(state, status_rows(state, tasks)))


def project_index_block(state: dict[str, Any], tasks: list[Task]) -> str:
    """Persisted project index rows; commit-safe in every workflow mode."""
    project = state["project"]
    lifecycle = state["lifecycle"]
    active = find_active(tasks, state)
    blocker = active.blocked_reason if active and active.blocked_reason else "None"
    active_value = task_link(active, ROOT / "project") if active else "None"
    rows = [
        ("Project", str(project.get("name", project.get("type", "project")))),
        ("Phase", str(lifecycle["phase"])),
        ("Milestone", str(lifecycle["milestone"])),
        ("Next gate", str(lifecycle["next_gate"])),
        ("Active task", active_value),
        ("Approval", approval_text(active)),
        ("Blocker", blocker),
        ("Recommended next action", recommended_next_action(state, tasks)),
    ]
    return markdown_table(persisted_rows(state, rows)) + INDEX_LINKS


def persisted_board_block(tasks: list[Task], state: dict[str, Any] | None = None) -> str:
    """Commit-safe Kanban block built only from persisted task records.

    In `workflow_mode: pr` the columns follow persisted statuses and the block
    points at the merge-aware runtime board, because a merged review record
    cannot be committed as Done before the merge exists.
    """
    pr_mode = state is not None and is_github_pr_mode(state)
    lines: list[str] = []
    if pr_mode:
        lines.extend([PR_BOARD_SNAPSHOT_NOTE, ""])
    for title, status in COLUMNS:
        lines.extend([f"## {title}", ""])
        matching = sorted(
            (task for task in tasks if task.status == status),
            key=task_sort_key,
        )
        if matching:
            for task in matching:
                lines.append(f"- {board_task_line(task, state=None)}")
        else:
            lines.append("_None_")
        lines.append("")
    return "\n".join(lines).rstrip()


def runtime_board_block(tasks: list[Task], state: dict[str, Any] | None = None) -> str:
    """Merge-aware Kanban block rendered at read time by `make project-status`."""
    pr_mode = state is not None and is_github_pr_mode(state)
    lines: list[str] = []
    for title, status in COLUMNS:
        lines.extend([f"## {title}", ""])
        matching = sorted(
            (task for task in tasks if effective_status(state, task) == status),
            key=task_sort_key,
        )
        if matching:
            for task in matching:
                lines.append(f"- {board_task_line(task, state=state, pr_mode=pr_mode)}")
        else:
            lines.append("_None_")
        lines.append("")
    return "\n".join(lines).rstrip()


def board_task_line(
    task: Task,
    *,
    state: dict[str, Any] | None = None,
    pr_mode: bool = False,
) -> str:
    """Render one board entry for either board view."""
    rel = relative(task.path, ROOT / "project")
    if task.status == "blocked" and task.blocked_reason:
        suffix = f" - blocked: {task.blocked_reason}"
    elif task_merge_completed(state, task):
        suffix = " - completed by merged Git provenance"
    elif pr_mode and task.status == "review" and task.approval_level in GITHUB_MERGE_LEVELS:
        suffix = " - awaiting human GitHub merge"
    else:
        suffix = ""
    return f"[{task.id}]({rel}) - P{task.priority} - {task.title}{suffix}"


def print_errors(errors: list[str]) -> None:
    """Report deterministic validation errors and the recommended next command."""
    for error in errors:
        print(f"ERROR: {error}")
    print("Recommended fix: apply the specific correction above, then run: make validate-project")
