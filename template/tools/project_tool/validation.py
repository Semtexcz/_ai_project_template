"""Project and task validation: state schema, records, graph, drift, approval.

Composed from cohesive validators that each return deterministic, actionable
error strings. Documentation validation lives in :mod:`project_tool.docs`; this
module validates the managed lifecycle records and their persisted views.
"""

from __future__ import annotations

from typing import Any, cast

from project_tool.docs import validate_docs, validate_markdown_links
from project_tool.git import task_merge_completed
from project_tool.lifecycle import (
    definition_of_done,
    definition_of_ready,
    dependencies_done,
    dependency_cycle,
    effective_status,
    valid_datetime,
)
from project_tool.model import (
    APPROVAL_LEVELS,
    APPROVAL_STATUSES,
    GOVERNANCE_MODES,
    LIFECYCLE_PHASES,
    PROJECT_STATUSES,
    PROJECT_TYPES,
    RISKS,
    ROOT,
    RUNTIME_LEVELS,
    TASK_ID_RE,
    TASK_STATUSES,
    WORKFLOW_MODES,
    ProjectError,
    Task,
    is_github_pr_mode,
    nonempty,
    relative,
    task_by_id,
)
from project_tool.rendering import (
    persisted_board_block,
    persisted_status_block,
    project_index_block,
)
from project_tool.storage import (
    INDEX_END,
    INDEX_START,
    KANBAN_END,
    KANBAN_START,
    STATE_END,
    STATE_START,
    extract_block,
    load_tasks,
    normalize_block,
    read_state,
)


def validate_all(*, check_drift: bool = True) -> list[str]:
    """Validate the managed project state end to end."""
    errors: list[str] = []
    try:
        state = read_state()
        tasks = load_tasks()
    except ProjectError as exc:
        return [str(exc)]
    tasks_by = task_by_id(tasks)

    errors.extend(validate_state_schema(state, tasks_by))
    errors.extend(validate_tasks(tasks, state))
    errors.extend(validate_task_graph(tasks, tasks_by, state))
    errors.extend(validate_active_task(state, tasks, tasks_by))
    if check_drift:
        errors.extend(validate_drift(state, tasks))
    errors.extend(validate_markdown_links())
    errors.extend(validate_docs(state, tasks, check_drift=check_drift))
    return errors


def validate_candidate(state: dict[str, Any], tasks: list[Task]) -> list[str]:
    """Validate a candidate state/task set before it is persisted."""
    errors: list[str] = []
    tasks_by = task_by_id(tasks)
    errors.extend(validate_state_schema(state, tasks_by))
    errors.extend(validate_tasks(tasks, state))
    errors.extend(validate_task_graph(tasks, tasks_by, state))
    errors.extend(validate_active_task(state, tasks, tasks_by))
    errors.extend(validate_markdown_links())
    errors.extend(validate_docs(state, tasks, check_drift=False))
    return errors


def validate_state_schema(state: dict[str, Any], tasks_by: dict[str, Task]) -> list[str]:
    """Validate the ``project/state.yaml`` schema and cross-references."""
    errors: list[str] = []
    if state.get("schema_version") != 1:
        errors.append("project/state.yaml schema_version must be 1. Fix schema_version.")
    project = state.get("project")
    lifecycle = state.get("lifecycle")
    work = state.get("work")
    template = state.get("template")
    for key, section in [
        ("project", project),
        ("lifecycle", lifecycle),
        ("work", work),
        ("template", template),
    ]:
        if not isinstance(section, dict):
            errors.append(f"project/state.yaml is missing mapping '{key}'. Add the {key} section.")
    if errors:
        return errors
    # The guard above proves every section is a mapping; cast keeps the rest of
    # this validator precisely typed instead of ``Unknown``-typed.
    project = cast("dict[str, Any]", project)
    lifecycle = cast("dict[str, Any]", lifecycle)
    work = cast("dict[str, Any]", work)
    template = cast("dict[str, Any]", template)
    if project.get("type") not in PROJECT_TYPES:
        errors.append(
            f"project.type '{project.get('type')}' is invalid. "
            f"Use one of: {', '.join(sorted(PROJECT_TYPES))}."
        )
    if project.get("runtime_level") not in RUNTIME_LEVELS:
        errors.append("project.runtime_level is invalid. Use local, shared, or production.")
    if "governance" in project and project.get("governance") not in GOVERNANCE_MODES:
        errors.append("project.governance is invalid. Use lightweight or managed.")
    if "workflow_mode" in project and project.get("workflow_mode") not in WORKFLOW_MODES:
        errors.append("project.workflow_mode is invalid. Use local, branch, or pr.")
    if project.get("risk") not in RISKS:
        errors.append("project.risk is invalid. Use low, medium, or high.")
    if project.get("status") not in PROJECT_STATUSES:
        errors.append("project.status is invalid. Use active, paused, done, or retired.")
    if lifecycle.get("phase") not in LIFECYCLE_PHASES:
        errors.append("lifecycle.phase is invalid. Use a documented lifecycle phase.")
    if project.get("status") == "active":
        if not nonempty(lifecycle.get("milestone")):
            errors.append("Active project requires lifecycle.milestone. Set the current milestone.")
        if not nonempty(lifecycle.get("next_gate")):
            errors.append("Active project requires lifecycle.next_gate. Set the next gate.")
    active = nonempty(work.get("active_task"))
    if active and not TASK_ID_RE.match(active):
        errors.append(
            f"work.active_task '{active}' is invalid. Use format T-001 or leave it empty."
        )
    if active and active not in tasks_by:
        errors.append(
            f"work.active_task '{active}' does not exist. Create the task or clear active_task."
        )
    if not nonempty(template.get("version")):
        errors.append("template.version is required. Set the template version.")
    return errors


def validate_tasks(tasks: list[Task], state: dict[str, Any]) -> list[str]:
    """Validate individual task records, readiness, and completion metadata."""
    errors: list[str] = []
    seen: set[str] = set()
    current_milestone = str(state.get("lifecycle", {}).get("milestone", ""))
    for task in tasks:
        prefix = f"{task.id or relative(task.path)}:"
        if not TASK_ID_RE.match(task.id):
            errors.append(f"{prefix} invalid task id. Use format T-001.")
        if task.id in seen:
            errors.append(f"Duplicate task id {task.id}. Keep task IDs unique.")
        seen.add(task.id)
        if not task.title:
            errors.append(f"{prefix} title is required.")
        if task.status not in TASK_STATUSES:
            errors.append(
                f"{prefix} invalid status '{task.status}'. "
                f"Use one of: {', '.join(sorted(TASK_STATUSES))}."
            )
        # Defensive guard for task records built from untyped frontmatter.
        if not isinstance(task.priority, int) or task.priority < 1:  # pyright: ignore[reportUnnecessaryIsInstance]
            errors.append(f"{prefix} priority must be a positive integer.")
        if not task.milestone:
            errors.append(f"{prefix} milestone is required.")
        if (
            effective_status(state, task) in {"ready", "in-progress", "review"}
            and task.milestone != current_milestone
        ):
            errors.append(
                f"{prefix} milestone '{task.milestone}' is not the current milestone "
                f"'{current_milestone}'. Move it or update project/state.yaml."
            )
        if task.approval_level not in APPROVAL_LEVELS:
            errors.append(
                f"{prefix} invalid approval_level '{task.approval_level}'. Use A0, A1, or A2."
            )
        if task.approval_status not in APPROVAL_STATUSES:
            errors.append(
                f"{prefix} invalid approval_status '{task.approval_status}'. "
                "Use not-required, pending, approved, or rejected."
            )
        errors.extend(validate_approval(task, state))
        errors.extend(validate_blocker(task))
        if effective_status(state, task) in {"ready", "in-progress", "review"}:
            missing = definition_of_ready(task)
            if missing:
                errors.append(
                    f"{prefix} Definition of Ready is incomplete: {', '.join(missing)}. "
                    "Fill the required sections before ready/start."
                )
        if task.status == "done":
            missing = definition_of_done(task)
            if missing:
                errors.append(
                    f"{prefix} Definition of Done is incomplete: {', '.join(missing)}. "
                    "Complete verification, notes, docs impact, and checked criteria."
                )
    return errors


def validate_approval(task: Task, state: dict[str, Any] | None = None) -> list[str]:
    """Validate approval metadata and the mode-specific approval boundary."""
    errors: list[str] = []
    prefix = f"{task.id}:"
    pr_mode = state is not None and is_github_pr_mode(state)
    merged = bool(state) and task_merge_completed(state, task)
    if task.approval_level == "A0":
        if task.approval_status != "not-required":
            errors.append(f"{prefix} A0 tasks must use approval_status not-required.")
        if task.approved_by or task.approved_at:
            errors.append(f"{prefix} A0 tasks must not carry human approval metadata.")
    if task.approval_level in {"A1", "A2"}:
        if task.approval_status == "approved":
            if not task.approved_by:
                errors.append(
                    f"{prefix} approved task requires approved_by. Record the human approver."
                )
            if not valid_datetime(task.approved_at):
                errors.append(
                    f"{prefix} approved_at is invalid. Use ISO datetime, "
                    "for example 2026-07-31T10:00:00+02:00."
                )
        if task.approval_status != "approved" and (task.approved_by or task.approved_at):
            errors.append(
                f"{prefix} approval metadata is present but approval_status is not approved. "
                "Clear it or approve explicitly."
            )
    if pr_mode and not merged and task.approval_level == "A1" and task.status != "done":
        if task.approval_status == "approved" or task.approved_by or task.approved_at:
            errors.append(
                f"{prefix} A1 approval cannot be recorded locally in workflow_mode=pr. "
                "The human GitHub merge is the only A1 approval boundary. "
                "Clear the local approval fields."
            )
        if task.status == "review" and task.approval_status != "pending":
            errors.append(
                f"{prefix} A1 review tasks in workflow_mode=pr must keep approval_status pending. "
                "Completion is derived from the human GitHub merge, never recorded by the agent."
            )
    if task.approval_level == "A1" and task.status == "done" and task.approval_status != "approved":
        if pr_mode:
            errors.append(
                f"{prefix} A1 task cannot be done without approval. In workflow_mode=pr the "
                "human GitHub merge of the review pull request is the only A1 approval."
            )
        else:
            errors.append(
                f"{prefix} A1 task cannot be done without human approval. "
                f'Run: make task-approve TASK={task.id} APPROVED_BY="<human>".'
            )
    if (
        task.approval_level == "A2"
        and task.status in {"in-progress", "review", "done"}
        and task.approval_status != "approved"
    ):
        errors.append(
            f"{prefix} A2 task cannot start or finish without prior human approval. "
            f'Human must run: make task-approve TASK={task.id} APPROVED_BY="<human>".'
        )
    return errors


def validate_blocker(task: Task) -> list[str]:
    """Validate blocker metadata is present exactly when a task is blocked."""
    errors: list[str] = []
    prefix = f"{task.id}:"
    if task.status == "blocked":
        if not task.blocked_reason:
            errors.append(
                f"{prefix} blocked task requires blocked_reason. "
                f'Use make task-block TASK={task.id} REASON="..." UNBLOCK="...".'
            )
        if not task.unblock_action:
            errors.append(
                f"{prefix} blocked task requires unblock_action. "
                f'Use make task-block TASK={task.id} REASON="..." UNBLOCK="...".'
            )
    elif task.blocked_reason or task.unblock_action:
        errors.append(
            f"{prefix} blocker metadata is only allowed when status is blocked. "
            "Clear blocked_reason and unblock_action."
        )
    return errors


def validate_task_graph(
    tasks: list[Task], tasks_by: dict[str, Task], state: dict[str, Any] | None = None
) -> list[str]:
    """Validate dependency declarations, cycles, and dependency availability."""
    errors: list[str] = []
    for task in tasks:
        if len(set(task.depends_on)) != len(task.depends_on):
            errors.append(
                f"{task.id}: duplicate dependencies are not allowed. "
                "Remove duplicates from depends_on."
            )
        if task.id in task.depends_on:
            errors.append(
                f"{task.id}: task cannot depend on itself. Remove {task.id} from depends_on."
            )
        for dep in task.depends_on:
            if dep not in tasks_by:
                errors.append(
                    f"{task.id}: dependency {dep} does not exist. "
                    "Create it or remove the dependency."
                )
    cycle = dependency_cycle(tasks)
    if cycle:
        errors.append(
            f"Task dependency cycle detected: {' -> '.join(cycle)}. "
            "Break the cycle before continuing."
        )
    for task in tasks:
        if task.status in {"ready", "in-progress"} and not dependencies_done(
            task, tasks_by, state=state
        ):
            missing = [
                dep
                for dep in task.depends_on
                if dep in tasks_by
                and effective_status(state, tasks_by[dep]) not in {"done", "cancelled"}
            ]
            errors.append(
                f"{task.id}: cannot be {task.status}; dependencies are not done: "
                f"{', '.join(missing)}. Complete dependencies first."
            )
    return errors


def validate_active_task(
    state: dict[str, Any], tasks: list[Task], tasks_by: dict[str, Task]
) -> list[str]:
    """Validate the single-active-task invariant and blocker flag consistency."""
    errors: list[str] = []
    active = nonempty(state.get("work", {}).get("active_task"))
    in_progress = [task for task in tasks if task.status == "in-progress"]
    blocked_flag = bool(state.get("work", {}).get("blocked"))
    any_blocked = any(task.status == "blocked" for task in tasks)
    if len(in_progress) > 1:
        errors.append(
            "More than one task is in-progress. Finish, review, block, or cancel one task."
        )
    if len(in_progress) == 1 and active != in_progress[0].id:
        errors.append(
            f"work.active_task must be {in_progress[0].id}. "
            "Run the controlled task transition or update state consistently."
        )
    if not in_progress and active:
        errors.append(
            "work.active_task is set but no task is in-progress. "
            "Clear work.active_task or start the task through make task-start."
        )
    if active and active in tasks_by and tasks_by[active].status == "blocked":
        errors.append(
            f"Active task {active} is blocked. "
            "Active task cannot be blocked; unblock it or clear active_task."
        )
    if blocked_flag != any_blocked:
        errors.append(
            "work.blocked does not match blocked tasks. "
            "Run: make sync-project-docs after fixing blocker state."
        )
    return errors


def validate_drift(state: dict[str, Any], tasks: list[Task]) -> list[str]:
    """Validate that committed generated blocks are the persisted view."""
    errors: list[str] = []
    # Only content that is a deterministic function of canonical files is
    # persisted, so drift here always means real drift. Git-relative status is
    # rendered at read time by `make project-status` and is never committed.
    expected = {
        ROOT / "README.md": (STATE_START, STATE_END, persisted_status_block(state, tasks)),
        ROOT / "project" / "index.md": (
            INDEX_START,
            INDEX_END,
            project_index_block(state, tasks),
        ),
        ROOT / "project" / "board.md": (
            KANBAN_START,
            KANBAN_END,
            persisted_board_block(tasks, state),
        ),
    }
    for path, (start, end, content) in expected.items():
        try:
            current = extract_block(path, start, end)
        except ProjectError as exc:
            errors.append(str(exc))
            continue
        if normalize_block(current) != normalize_block(content):
            errors.append(f"{relative(path)} generated block is stale. Run: make sync-project-docs")
    return errors
