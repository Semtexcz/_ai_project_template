"""Public command implementations: reporting, validation, and transitions.

This is the composition layer below the CLI. It turns lifecycle decisions,
validation, and rendering into the exact user-visible behavior of every command,
and it is the only place that decides when to mutate control files.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from project_tool.claims import (
    WorktreeCreation,
    WorktreeRemoval,
    WorktreeState,
    already_claimed_message,
    claim_dicts,
    create_claim,
    inspect_claims,
    ownership_errors,
    read_claim,
    release_claim,
    worktree_state,
    worktree_states,
)
from project_tool.docs import validate_docs, validate_markdown_links
from project_tool.git import task_merge_completed
from project_tool.lifecycle import (
    approval_blocker,
    available_tasks,
    dependencies_done,
    transition_blocker,
)
from project_tool.model import (
    ROOT,
    TASK_TOKEN_RE,
    ProjectError,
    is_github_pr_mode,
    task_by_id,
)
from project_tool.mutations import transactional_task_mutation
from project_tool.rendering import (
    print_errors,
    recommended_next_action,
    runtime_available_block,
    runtime_board_block,
    runtime_status_block,
    runtime_worktree_table,
)
from project_tool.storage import load_tasks, read_state
from project_tool.validation import validate_active_claims, validate_all
from project_tool.worktrees import (
    add_worktree,
    delete_branch,
    ensure_root_is_outside_project,
    remove_worktree,
    task_branch_name,
    worktree_for_task,
    worktree_path,
    worktree_root,
)


def status() -> None:
    """Render the live, merge-aware project view at read time.

    This is the authoritative presentation of Git-derived status; committed
    Markdown only carries the deterministic subset produced by `sync`. The live
    view also lists every locally claimed task worktree, because claim and
    worktree paths are local runtime state that must never be committed.
    """
    state = read_state()
    tasks = load_tasks()
    errors = validate_all(check_drift=False)
    print(runtime_status_block(state, tasks))
    print()
    print(runtime_board_block(tasks, state))
    print()
    print(runtime_available_block(available_tasks(tasks, state)))
    claim_errors = validate_active_claims(tasks, claim_dicts())
    rows = worktree_status_rows()
    if rows:
        print()
        print(runtime_worktree_table(rows))
    errors = [*errors, *claim_errors]
    print()
    print(f"Next action: {recommended_next_action(state, tasks, invalid=bool(errors))}")
    if errors:
        print()
        print_errors(errors)


def worktree_status_rows() -> list[tuple[str, str, str, str]]:
    """Return the live task/branch/worktree/state rows for local inspection."""
    rows: list[tuple[str, str, str, str]] = []
    for record in worktree_states():
        state_word = record.state
        if record.unique_commits and not record.merged:
            state_word = f"{state_word}, {record.unique_commits} unmerged"
        rows.append(
            (
                record.task_id,
                record.branch or "(no branch)",
                record.path or "(no worktree)",
                state_word,
            )
        )
    return rows


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
    """Move a task through the controlled lifecycle and persist the result.

    Only the task record and the deterministic dashboards change: project-global
    state carries no task ownership, so parallel branches never rewrite a shared
    ``active_task`` field. Starting work additionally respects worktree ownership,
    so one worktree cannot own two active tasks.
    """
    state = read_state()
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
    if new_status == "in-progress":
        conflicts = ownership_errors(task_id)
        if conflicts:
            raise ProjectError(" ".join(conflicts))
    candidate: dict[str, Any] = dict(status=new_status)
    if new_status == "blocked":
        candidate.update(blocked_reason=reason, unblock_action=unblock)
    else:
        candidate.update(blocked_reason=None, unblock_action=None)
    transactional_task_mutation(task_id, candidate)
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


def available_command() -> None:
    """Print every task that can start now, for humans and future schedulers."""
    state = read_state()
    tasks = available_tasks(load_tasks(), state)
    if not tasks:
        print("No task is available to start.")
        return
    print("Available tasks:")
    for task in tasks:
        print(f"- {task.id} - {task.title}")


def create_worktree(task_id: str) -> None:
    """Create one isolated task worktree: validate, claim, then branch.

    This is the single high-level entry point for parallel agent work. Policy
    checks come first (task exists and can be worked, dependencies satisfied, A2
    approval recorded), then the atomic local claim, then the Git worktree.
    """
    state = read_state()
    tasks = load_tasks()
    tasks_by = task_by_id(tasks)
    task = tasks_by.get(task_id)
    if task is None:
        raise ProjectError(f"Task {task_id} does not exist. Create the task record first.")
    if task.status in {"done", "cancelled"}:
        raise ProjectError(f"Task {task_id} is {task.status}; no worktree is needed.")
    if task.status == "blocked":
        raise ProjectError(f"Task {task_id} is blocked: {task.blocked_reason or 'blocked'}.")
    if task.approval_level == "A2" and task.approval_status != "approved":
        raise ProjectError(f"Human A2 approval is required for {task_id} before work starts.")
    if not dependencies_done(task, tasks_by, state=state):
        missing = [
            dep
            for dep in task.depends_on
            if dep in tasks_by and tasks_by[dep].status not in {"done", "cancelled"}
        ]
        raise ProjectError(
            f"{task_id} cannot start until dependencies are done: {', '.join(missing)}."
        )
    creation = create_task_worktree(task_id, task.title)
    print_worktree_creation(creation)


def print_worktree_creation(creation: WorktreeCreation) -> None:
    """Report a created worktree with the deterministic next step."""
    print(f"Task {creation.task_id} has an isolated worktree and a local claim.")
    print(f"Branch:   {creation.branch}")
    print(f"Worktree: {creation.path}")
    print(f"Base:     {creation.base}")
    print(f"Next:     {creation.next_command}")


def worktrees_command() -> None:
    """Report every local task worktree, claim state, and release guidance."""
    rows = worktree_status_rows()
    if not rows:
        print("No local task worktree or claim exists.")
        print("Create one with: make agent-worktree TASK=<id>")
        return
    print(runtime_worktree_table(rows))
    print()
    print("Claims (local only, never committed):")
    for claim in inspect_claims():
        liveness = "running" if claim.as_dict()["process_alive"] else "not running"
        print(
            f"- {claim.task_id}: {claim.branch} at {claim.worktree} (pid {claim.pid}, {liveness})"
        )
    errors = validate_active_claims(load_tasks(), claim_dicts())
    if errors:
        print()
        print_errors(errors)


def remove_worktree_command(task_id: str, *, force: bool = False) -> None:
    """Remove one task worktree, refusing destructive defaults."""
    state = read_state()
    task = task_by_id(load_tasks()).get(task_id)
    merged = bool(task) and (task_merge_completed(state, task) or task.status == "done")
    removal: WorktreeRemoval = remove_task_worktree(
        task_id,
        merged_into_base=merged,
        force=force,
    )
    print(f"Worktree for {task_id} removed.")
    if removal.branch:
        print(f"Branch:   {removal.branch}")
    print(f"Worktree: {removal.path}")
    if removal.claim_released:
        print("Local claim released.")
    if removal.forced:
        print("Forced removal was requested explicitly; unmerged work may have been discarded.")


def release_claim_command(task_id: str) -> None:
    """Release a local task claim explicitly, for stale-claim recovery."""
    claim = release_claim(task_id)
    print(f"Local claim for {task_id} released (was {claim.branch} at {claim.worktree}).")


def create_task_worktree(task_id: str, title: str) -> WorktreeCreation:
    """Claim ``task_id`` and add its isolated branch and worktree.

    The claim is written first with an exclusive create, so two racing callers
    cannot both proceed; a failed worktree creation rolls the claim back instead
    of leaving a claim without a worktree. Git mechanics stay in
    :mod:`project_tool.worktrees`.
    """
    root = worktree_root()
    ensure_root_is_outside_project(root)
    if read_claim(task_id) is not None:
        raise ProjectError(already_claimed_message(task_id))
    branch = task_branch_name(task_id, title)
    claim = create_claim(task_id, branch, worktree_path(task_id))
    try:
        added = add_worktree(task_id, title)
    except ProjectError:
        release_claim(task_id)
        raise
    if added.branch != claim.branch:  # pragma: no cover - defensive invariant
        release_claim(task_id)
        raise ProjectError(
            f"Claim branch {claim.branch} does not match created branch {added.branch}."
        )
    return WorktreeCreation(
        task_id=task_id,
        branch=added.branch,
        path=added.path,
        base=added.base,
        reused_branch=added.reused_branch,
        claim=claim,
    )


def worktree_removal_blockers(state_record: WorktreeState, *, merged_into_base: bool) -> list[str]:
    """Return reasons a worktree must not be removed by default."""
    blockers: list[str] = []
    if state_record.exists and state_record.dirty:
        blockers.append("the worktree has uncommitted changes")
    if state_record.unique_commits and not merged_into_base:
        blockers.append(
            f"branch {state_record.branch} has {state_record.unique_commits} unique "
            "commit(s) that are not merged into the base branch"
        )
    return blockers


def remove_task_worktree(
    task_id: str,
    *,
    merged_into_base: bool = False,
    force: bool = False,
) -> WorktreeRemoval:
    """Remove a task worktree, refusing destructive defaults.

    Refuses by default when the worktree is dirty or when its branch still holds
    unique unmerged commits. ``force=True`` is the explicit human override and is
    the only way to discard unmerged work.
    """
    entry = worktree_for_task(task_id)
    claim = read_claim(task_id)
    if entry is None and claim is None:
        raise ProjectError(
            f"Task {task_id} has no worktree and no local claim. "
            "Inspect local worktrees with `make agent-worktrees`."
        )
    if entry is not None:
        path = Path(entry.path)
    elif claim is not None:
        path = Path(claim.worktree)
    else:  # pragma: no cover - unreachable: both-None was handled above
        raise ProjectError(f"Task {task_id} has no removable worktree.")
    branch = entry.branch if entry is not None else (claim.branch if claim is not None else None)
    if entry is not None and claim is not None and str(path.resolve()) != claim.worktree:
        raise ProjectError(
            f"Claim for {task_id} points at {claim.worktree} but its branch worktree is "
            f"{path}. Refusing to remove inconsistent worktree/claim state."
        )
    if path.resolve() == ROOT.resolve():
        raise ProjectError(
            f"{task_id} is checked out in the control checkout. "
            "Switch to the control branch before removing a task worktree."
        )
    state_record = worktree_state(task_id, entry=entry, claim=claim)
    merged = merged_into_base or state_record.merged
    blockers = worktree_removal_blockers(state_record, merged_into_base=merged)
    if blockers and not force:
        raise ProjectError(
            f"Refusing to remove worktree {path}: {'; '.join(blockers)}. Merge the work "
            f"first, or override explicitly with `make agent-worktree-remove "
            f"TASK={task_id} FORCE=1`."
        )
    if state_record.exists:
        remove_worktree(path)
    if branch is not None:
        delete_branch(branch, forced=force or merged)
    claim_released = False
    if claim is not None:
        release_claim(task_id)
        claim_released = True
    return WorktreeRemoval(
        task_id=task_id,
        branch=branch,
        path=str(path),
        claim_released=claim_released,
        forced=force,
        merged_into_base=merged,
    )
