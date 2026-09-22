"""Local task claims and worktree ownership resolution.

A claim means "this worktree and branch currently own implementation of T-101".
It never means the task is approved, complete, or exempt from dependencies:
lifecycle policy in :mod:`project_tool.lifecycle` stays canonical, and claims
only control concurrency.

Claims are local-only. They live in this repository's Git directory, which every
worktree shares, and are never committed, so a parallel branch never has to
rewrite a shared ownership field. Records are created with an atomic exclusive
create, which means exactly one of two racing agents can win a claim. Process
lifetime is not a claim boundary: a claim left behind by a crashed agent stays
observable and must be released explicitly.

Git mechanics live in :mod:`project_tool.worktrees`; this module composes them
into task ownership: which task a worktree owns, how a task is claimed,
inspected, created, and safely removed.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from project_tool.model import ROOT, ProjectError, relative
from project_tool.worktrees import (
    CONTROL_BRANCHES,
    WorktreeEntry,
    branch_merged,
    current_branch,
    git_repository_available,
    list_worktrees,
    optional_git_text,
    task_id_from_branch,
    unique_commit_count,
    worktree_is_dirty,
)

CLAIMS_DIRNAME = "agent-claims"
CLAIM_FIELDS = ("task_id", "branch", "worktree", "pid", "created_at")


def claims_directory() -> Path | None:
    """Return the shared claims directory, or ``None`` outside a Git repository.

    Claims live in this repository's Git directory, which every worktree shares.
    A project without Git simply has no claims: reading them is empty and writing
    one fails with a clear message, so non-Git usage never breaks status output.
    """
    text = optional_git_text(["rev-parse", "--git-common-dir"])
    if not text or not text.strip():
        return None
    git_dir = Path(text.strip())
    if not git_dir.is_absolute():
        git_dir = ROOT / git_dir
    return git_dir.resolve() / CLAIMS_DIRNAME


def claims_dir() -> Path:
    """Return the claims directory, failing when this is not a Git repository."""
    directory = claims_directory()
    if directory is None:
        raise ProjectError(
            "Local task claims need a Git repository. Run `git init` in the project "
            "root, or work without claims in a single checkout."
        )
    return directory


def claim_path(task_id: str) -> Path:
    """Return the local claim file path for ``task_id``."""
    return claims_dir() / f"{task_id}.json"


def timestamp() -> str:
    """Return the local timestamp recorded on a new claim."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def process_alive(pid: int) -> bool:
    """Advisory liveness probe for inspection only. Never a claim boundary."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except (OSError, ValueError):
        return False
    return True


@dataclass(frozen=True)
class TaskClaim:
    """One local record of which worktree currently owns a task."""

    task_id: str
    branch: str
    worktree: str
    pid: int
    created_at: str

    def as_dict(self) -> dict[str, Any]:
        """Return the claim as a plain mapping for rendering and validation."""
        return {
            "task_id": self.task_id,
            "branch": self.branch,
            "worktree": self.worktree,
            "pid": self.pid,
            "created_at": self.created_at,
            "process_alive": process_alive(self.pid),
        }


def claim_from_payload(payload: Any, path: Path) -> TaskClaim:
    """Build a claim from parsed JSON, failing loudly on a corrupt record."""
    if not isinstance(payload, dict):
        raise ProjectError(f"{relative(path)} is not a valid claim record. Release it explicitly.")
    record = cast("dict[str, Any]", payload)
    missing = [field for field in CLAIM_FIELDS if field not in record]
    if missing:
        raise ProjectError(
            f"{relative(path)} is missing claim fields {', '.join(missing)}. "
            "Release the claim explicitly with make agent-claim-release."
        )
    raw_pid: Any = record["pid"]
    try:
        pid = int(raw_pid)
    except (TypeError, ValueError) as exc:
        raise ProjectError(f"{relative(path)} has a non-numeric pid. Release the claim.") from exc
    return TaskClaim(
        task_id=str(record["task_id"]),
        branch=str(record["branch"]),
        worktree=str(record["worktree"]),
        pid=pid,
        created_at=str(record["created_at"]),
    )


def read_claim(task_id: str) -> TaskClaim | None:
    """Return the local claim for ``task_id``, or ``None`` when unclaimed."""
    directory = claims_directory()
    if directory is None:
        return None
    path = directory / f"{task_id}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectError(
            f"{relative(path)} is unreadable ({exc}). Release the claim explicitly."
        ) from exc
    return claim_from_payload(payload, path)


def inspect_claims() -> list[TaskClaim]:
    """Return every local claim, ordered by task id. Empty without Git."""
    directory = claims_directory()
    if directory is None or not directory.exists():
        return []
    claims: list[TaskClaim] = []
    for path in sorted(directory.glob("T-*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        claims.append(claim_from_payload(payload, path))
    return sorted(claims, key=lambda claim: claim.task_id)


def claim_dicts() -> list[dict[str, Any]]:
    """Return local claims as plain mappings for validation and orchestration."""
    return [claim.as_dict() for claim in inspect_claims()]


def already_claimed_message(task_id: str) -> str:
    """Describe who owns ``task_id`` and how a stale claim is recovered."""
    existing = read_claim(task_id)
    if existing is None:
        return f"Task {task_id} is already claimed."
    state = "process running" if process_alive(existing.pid) else "process not running"
    return (
        f"Task {task_id} is already claimed by {existing.worktree} "
        f"(branch {existing.branch}, pid {existing.pid}, {state}, since "
        f"{existing.created_at}). Inspect local claims with `make agent-worktrees`; "
        f"release a stale claim explicitly with `make agent-claim-release TASK={task_id}`."
    )


def create_claim(task_id: str, branch: str, worktree: Path) -> TaskClaim:
    """Create the local claim for ``task_id`` atomically.

    Exactly one of two racing agents can win: the record is created with an
    exclusive create, so the loser observes ``FileExistsError`` instead of
    silently overwriting the winner's claim.
    """
    directory = claims_dir()
    directory.mkdir(parents=True, exist_ok=True)
    resolved = str(worktree.resolve())
    for other in inspect_claims():
        if other.task_id != task_id and other.worktree == resolved:
            raise ProjectError(
                f"Worktree {resolved} already owns {other.task_id}. "
                "One worktree owns at most one task."
            )
    claim = TaskClaim(
        task_id=task_id,
        branch=branch,
        worktree=resolved,
        pid=os.getpid(),
        created_at=timestamp(),
    )
    payload = json.dumps(claim.as_dict(), sort_keys=True) + "\n"
    try:
        handle_fd = os.open(claim_path(task_id), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError as exc:
        raise ProjectError(already_claimed_message(task_id)) from exc
    with os.fdopen(handle_fd, "w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    return claim


def release_claim(task_id: str) -> TaskClaim:
    """Release the local claim for ``task_id``. Explicit, never automatic."""
    claim = read_claim(task_id)
    if claim is None:
        raise ProjectError(
            f"Task {task_id} has no local claim to release. "
            "Inspect local claims with `make agent-worktrees`."
        )
    claim_path(task_id).unlink()
    return claim


@dataclass(frozen=True)
class WorktreeState:
    """Inspection record for one task worktree or one local claim."""

    task_id: str
    branch: str | None
    path: str
    registered: bool
    exists: bool
    dirty: bool
    unique_commits: int
    merged: bool
    claimed: bool
    errors: tuple[str, ...]

    @property
    def state(self) -> str:
        """Render the short state word used by `make agent-worktrees`."""
        if not self.exists:
            return "missing"
        if self.errors:
            return "inconsistent"
        if self.dirty:
            return "dirty"
        return "clean"


def worktree_state(
    task_id: str, *, entry: WorktreeEntry | None, claim: TaskClaim | None
) -> WorktreeState:
    """Inspect one task worktree without deciding whether it may be removed."""
    path_text = entry.path if entry is not None else (claim.worktree if claim is not None else "")
    branch = entry.branch if entry is not None else (claim.branch if claim is not None else None)
    location = Path(path_text)
    exists = bool(path_text) and location.is_dir()
    errors: list[str] = []
    if path_text and not exists:
        errors.append("worktree path is missing; release the claim or recreate the worktree")
    if claim is not None and branch is not None and claim.branch != branch:
        errors.append(f"claim branch {claim.branch} does not match branch {branch}")
    if claim is not None and path_text and str(location.resolve()) != claim.worktree:
        errors.append(f"claim worktree {claim.worktree} does not match {path_text}")
    return WorktreeState(
        task_id=task_id,
        branch=branch,
        path=path_text,
        registered=entry is not None,
        exists=exists,
        dirty=worktree_is_dirty(location) if exists else False,
        unique_commits=unique_commit_count(branch) if branch else 0,
        merged=branch_merged(branch) if branch else False,
        claimed=claim is not None,
        errors=tuple(errors),
    )


def worktree_states() -> list[WorktreeState]:
    """Inspect every registered worktree and every local claim, task-ordered.

    A task appears once whether it is reachable from a registered worktree, from
    a local claim, or from both, so a stale claim pointing at a removed worktree
    stays observable instead of disappearing.
    """
    entries: dict[str, WorktreeEntry] = {}
    for entry in list_worktrees():
        task_id = task_id_from_branch(entry.branch)
        if task_id is not None:
            entries.setdefault(task_id, entry)
    claims = {claim.task_id: claim for claim in inspect_claims()}
    return [
        worktree_state(task_id, entry=entries.get(task_id), claim=claims.get(task_id))
        for task_id in sorted(set(entries) | set(claims))
    ]


@dataclass(frozen=True)
class WorktreeOwner:
    """Which task the current checkout owns, derived from branch and claim."""

    task_id: str | None
    branch: str | None
    worktree: str
    control_checkout: bool
    claim: TaskClaim | None
    errors: tuple[str, ...]
    notes: tuple[str, ...]

    @property
    def valid(self) -> bool:
        """Whether this checkout's ownership is internally consistent."""
        return not self.errors


def resolve_owner(cwd: Path | None = None) -> WorktreeOwner:
    """Resolve the task owned by this checkout, deterministically.

    The branch name is the primary identity: it survives process restarts and
    needs no extra state. The local claim is the concurrency record and must
    agree with the branch and worktree when it exists. Inconsistent ownership
    fails loudly instead of being guessed.
    """
    location = str(Path(cwd or ROOT).resolve())
    if not git_repository_available():
        return WorktreeOwner(
            task_id=None,
            branch=None,
            worktree=location,
            control_checkout=False,
            claim=None,
            errors=(),
            notes=("No Git repository here: worktree ownership is not enforced.",),
        )
    branch = current_branch(cwd=cwd)
    if branch is None:
        return WorktreeOwner(
            task_id=None,
            branch=None,
            worktree=location,
            control_checkout=False,
            claim=None,
            errors=(),
            notes=("Detached HEAD: the owned task cannot be derived from a branch.",),
        )
    if branch in CONTROL_BRANCHES:
        return WorktreeOwner(
            task_id=None,
            branch=branch,
            worktree=location,
            control_checkout=True,
            claim=None,
            errors=(),
            notes=(f"{branch} is the control checkout and owns no task.",),
        )
    task_id = task_id_from_branch(branch)
    if task_id is None:
        return WorktreeOwner(
            task_id=None,
            branch=branch,
            worktree=location,
            control_checkout=False,
            claim=None,
            errors=(),
            notes=(
                f"Branch {branch} does not name a task id (T-###); "
                "task ownership cannot be derived from it.",
            ),
        )
    claim = read_claim(task_id)
    errors: list[str] = []
    notes: list[str] = []
    if claim is None:
        notes.append(f"Branch {branch} names {task_id} but this checkout holds no local claim.")
    else:
        if claim.branch != branch:
            errors.append(
                f"Claim for {task_id} points at branch {claim.branch}, "
                f"but this checkout is on {branch}."
            )
        if Path(claim.worktree).resolve() != Path(location):
            errors.append(
                f"Claim for {task_id} belongs to worktree {claim.worktree}, not {location}."
            )
    return WorktreeOwner(
        task_id=task_id,
        branch=branch,
        worktree=location,
        control_checkout=False,
        claim=claim,
        errors=tuple(errors),
        notes=tuple(notes),
    )


def ownership_errors(task_id: str, *, owner: WorktreeOwner | None = None) -> list[str]:
    """Return why this checkout may not act as ``task_id``.

    A conflicting branch task id is always rejected. A missing claim, a branch
    without a task id, and a detached HEAD are reported as notes by
    :func:`resolve_owner` rather than errors, so the single-agent path stays
    simple while genuine inconsistencies fail loudly.
    """
    resolved = owner or resolve_owner()
    errors = list(resolved.errors)
    if resolved.task_id is not None and resolved.task_id != task_id:
        errors.append(
            f"This checkout owns {resolved.task_id}, not {task_id}. "
            "One worktree owns at most one task."
        )
    return errors


@dataclass(frozen=True)
class WorktreeCreation:
    """Result of creating an isolated worktree for one task."""

    task_id: str
    branch: str
    path: str
    base: str
    reused_branch: bool
    claim: TaskClaim

    @property
    def next_command(self) -> str:
        """The deterministic next command for the agent inside the new worktree."""
        return f"cd {self.path} && make agent-status"


@dataclass(frozen=True)
class WorktreeRemoval:
    """Result of removing an isolated worktree for one task."""

    task_id: str
    branch: str | None
    path: str
    claim_released: bool
    forced: bool
    merged_into_base: bool
