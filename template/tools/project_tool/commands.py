"""Public command implementations: reporting, validation, and transitions.

This is the composition layer below the CLI. It turns lifecycle decisions,
validation, and rendering into the exact user-visible behavior of every command,
and it is the only place that decides when to mutate control files.
"""

from __future__ import annotations

import copy
import os
from datetime import datetime
from typing import Any

from project_tool.docs import validate_docs, validate_markdown_links
from project_tool.lifecycle import approval_blocker, transition_blocker
from project_tool.model import (
    TASK_TOKEN_RE,
    ProjectError,
    is_github_pr_mode,
    task_by_id,
)
from project_tool.mutations import transactional_task_mutation
from project_tool.rendering import (
    print_errors,
    recommended_next_action,
    runtime_board_block,
    runtime_status_block,
)
from project_tool.storage import (
    dump_task_text,
    load_tasks,
    load_tasks_with_overrides,
    read_state,
    split_frontmatter,
    task_path,
)
from project_tool.validation import validate_all


def status() -> None:
    """Render the live, merge-aware project view at read time.

    This is the authoritative presentation of Git-derived status; committed
    Markdown only carries the deterministic subset produced by `sync`.
    """
    state = read_state()
    tasks = load_tasks()
    errors = validate_all(check_drift=False)
    print(runtime_status_block(state, tasks))
    print()
    print(runtime_board_block(tasks, state))
    print()
    print(f"Next action: {recommended_next_action(state, tasks, invalid=bool(errors))}")
    if errors:
        print()
        print_errors(errors)


def validate() -> None:
    """Validate the managed project state and report deterministic errors."""
    errors = validate_all(check_drift=True)
    if errors:
        print_errors(errors)
        raise SystemExit(1)
    print("Project state is valid.")


def validate_docs_command() -> None:
    """Validate documentation only, including persisted-dashboard drift."""
    state = read_state()
    tasks = load_tasks()
    errors: list[str] = []
    errors.extend(validate_markdown_links())
    errors.extend(validate_docs(state, tasks, check_drift=True))
    if errors:
        print_errors(errors)
        raise SystemExit(1)
    print("Project documentation is valid.")


def controlled_transition(
    task_id: str,
    new_status: str,
    *,
    reason: str | None = None,
    unblock: str | None = None,
) -> None:
    """Move a task through the controlled lifecycle and persist the result."""
    state = read_state()
    candidate_state = copy.deepcopy(state)
    tasks = load_tasks()
    tasks_by = task_by_id(tasks)
    task = tasks_by.get(task_id)
    if task is None:
        raise ProjectError(f"Task {task_id} does not exist. Create it before transitioning.")
    blocker = transition_blocker(
        task,
        new_status,
        tasks=tasks,
        tasks_by=tasks_by,
        state=state,
        reason=reason,
        unblock=unblock,
    )
    if blocker is not None:
        raise ProjectError(blocker)
    candidate: dict[str, Any] = dict(status=new_status)
    if new_status == "blocked":
        candidate.update(blocked_reason=reason, unblock_action=unblock)
    else:
        candidate.update(blocked_reason=None, unblock_action=None)
    if new_status == "in-progress":
        candidate_state["work"]["active_task"] = task.id
    if task.status == "in-progress" and new_status != "in-progress":
        candidate_state["work"]["active_task"] = None
    if new_status == "blocked":
        candidate_state["work"]["active_task"] = None
    path = task_path(task_id)
    data, body = split_frontmatter(path)
    data.update(candidate)
    refreshed = load_tasks_with_overrides({path: dump_task_text(data, body)})
    candidate_state["work"]["blocked"] = any(item.status == "blocked" for item in refreshed)
    if not any(item.status == "in-progress" for item in refreshed):
        candidate_state["work"]["active_task"] = None
    transactional_task_mutation(task_id, candidate, candidate_state)
    print(f"Task {task_id} moved to {new_status}.")


def approve(task_id: str, approved_by: str) -> None:
    """Record a human approval required by an A1/A2 task."""
    if not approved_by.strip():
        raise ProjectError("APPROVED_BY is required and must be a human identity.")
    task = task_by_id(load_tasks()).get(task_id)
    if task is None:
        raise ProjectError(f"Task {task_id} does not exist.")
    state = read_state()
    blocker = approval_blocker(task, state)
    if blocker is not None:
        raise ProjectError(blocker)
    transactional_task_mutation(
        task_id,
        {
            "approval_status": "approved",
            "approved_by": approved_by.strip(),
            "approved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        },
        state,
    )
    print(f"Task {task_id} approved by {approved_by.strip()}.")


def pr_validate() -> None:
    """Pre-merge structural validation for a governed GitHub pull request.

    Deterministic association: exactly one task id (T-###) must appear across
    the PR branch name, title, and body. The task must already be in review
    (A1/A2) or done (A0) so that merging the pull request is a pure human
    decision. A1 tasks must not carry locally recorded approval: the human
    GitHub merge is the only A1 approval boundary.
    """
    state = read_state()
    if not is_github_pr_mode(state):
        raise ProjectError(
            "pr-validate is only meaningful for managed projects with project.workflow_mode: pr."
        )
    tasks = load_tasks()
    tasks_by = task_by_id(tasks)
    sources = [
        os.environ.get("PR_HEAD_REF", ""),
        os.environ.get("PR_TITLE", ""),
        os.environ.get("PR_BODY", ""),
    ]
    referenced = {match for source in sources for match in TASK_TOKEN_RE.findall(source or "")}
    if not referenced:
        raise ProjectError(
            "PR association is missing. Put exactly one task id (T-###) in the PR branch "
            "name or the PR title, for example feat/T-002-... or 'T-002: title'."
        )
    if len(referenced) > 1:
        ordered = ", ".join(sorted(referenced))
        raise ProjectError(
            f"PR references multiple task ids: {ordered}. Open one pull request per task."
        )
    task_id = next(iter(referenced))
    task = tasks_by.get(task_id)
    if task is None:
        raise ProjectError(f"PR references {task_id} but no such task exists.")
    if task.approval_level == "A0":
        if task.status != "done":
            raise ProjectError(
                f"{task_id} is A0 and must be done before its pull request is merged. "
                "Run: make task-complete TASK={task_id}"
            )
    elif task.status != "review":
        raise ProjectError(
            f"{task_id} must be in review before its pull request is merged. "
            "Move it there first: make task-review TASK={task_id}"
        )
    elif task.approval_level == "A1":
        if task.approval_status != "pending" or task.approved_by or task.approved_at:
            raise ProjectError(
                f"{task_id} must not record local A1 approval. In workflow_mode=pr the human "
                "GitHub merge is the only A1 approval boundary."
            )
    elif task.approval_level == "A2":
        if task.approval_status != "approved" or not task.approved_by:
            raise ProjectError(
                f"{task_id} is A2 and requires a human-recorded approval before work starts. "
                "A2 keeps its stronger pre-start approval boundary in workflow_mode=pr."
            )
    errors = validate_all(check_drift=True)
    if errors:
        print_errors(errors)
        raise SystemExit(1)
    print(f"Pull request for {task_id} is structurally valid for a human GitHub merge.")
