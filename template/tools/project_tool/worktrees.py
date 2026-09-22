"""Git worktree and branch mechanics for task-scoped parallel agent work.

This module owns Git mechanics only: deterministic branch naming, worktree
discovery, base resolution, worktree creation and removal, and dirty or
merged-state predicates. Local task claims and the ownership policy that decides
which task a worktree owns live in :mod:`project_tool.claims`, which builds on
these primitives. Lifecycle policy stays in :mod:`project_tool.lifecycle` and
read-only merge provenance stays in :mod:`project_tool.git`.

Nothing here decides whether work is allowed: these are the Git primitives a
caller composes with lifecycle rules.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from project_tool.model import ROOT, TASK_TOKEN_RE, ProjectError, relative

BRANCH_PREFIX = "task/"
WORKTREE_DIR_SUFFIX = "-worktrees"
WORKTREE_ROOT_ENV = "PROJECT_WORKTREE_ROOT"
SLUG_MAX_LENGTH = 40
CONTROL_BRANCHES = {"main", "master"}


def run_git(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run one Git command in ``cwd`` (or the project root) without raising."""
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd or ROOT),
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:  # pragma: no cover - only reachable without Git installed
        raise ProjectError("Git is required for worktree operations.") from exc


def git_text(args: list[str], *, cwd: Path | None = None) -> str:
    """Return stdout of a Git command that must succeed."""
    result = run_git(args, cwd=cwd)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ProjectError(f"git {' '.join(args)} failed: {detail or 'unknown error'}")
    return result.stdout


def git_ok(args: list[str], *, cwd: Path | None = None) -> bool:
    """Whether a quiet Git predicate command succeeded."""
    return run_git(args, cwd=cwd).returncode == 0


def optional_git_text(args: list[str], *, cwd: Path | None = None) -> str | None:
    """Return stdout of a Git command, or ``None`` when it cannot run."""
    result = run_git(args, cwd=cwd)
    if result.returncode != 0:
        return None
    return result.stdout


def git_repository_available() -> bool:
    """Whether the current directory is inside a Git work tree."""
    return git_ok(["rev-parse", "--is-inside-work-tree"])


def slugify(title: str) -> str:
    """Return a deterministic, path-safe slug for a task title."""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:SLUG_MAX_LENGTH].strip("-") or "task"


def task_branch_name(task_id: str, title: str) -> str:
    """Return the canonical branch name for a task: ``task/T-101-<slug>``."""
    return f"{BRANCH_PREFIX}{task_id}-{slugify(title)}"


def task_id_from_branch(branch: str | None) -> str | None:
    """Return the machine-detectable task id in a branch name, when present."""
    if not branch:
        return None
    match = TASK_TOKEN_RE.search(branch)
    return match.group(0) if match else None


def current_branch(cwd: Path | None = None) -> str | None:
    """Return the checked-out branch of ``cwd``, or ``None`` on a detached HEAD."""
    text = optional_git_text(["branch", "--show-current"], cwd=cwd)
    if text is None:
        return None
    return text.strip() or None


def local_branch_exists(branch: str) -> bool:
    """Whether ``branch`` already exists as a local branch."""
    return git_ok(["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"])


@dataclass(frozen=True)
class WorktreeEntry:
    """One registered Git worktree."""

    path: str
    branch: str | None


def list_worktrees() -> list[WorktreeEntry]:
    """Return every worktree registered for this repository, path-sorted."""
    text = optional_git_text(["worktree", "list", "--porcelain"]) or ""
    entries: list[WorktreeEntry] = []
    path: str | None = None
    branch: str | None = None
    for line in [*text.splitlines(), ""]:
        if not line.strip():
            if path is not None:
                entries.append(WorktreeEntry(path=path, branch=branch))
            path, branch = None, None
            continue
        if line.startswith("worktree "):
            path = line[len("worktree ") :].strip()
        elif line.startswith("branch "):
            branch = line[len("branch ") :].strip().removeprefix("refs/heads/")
    return sorted(entries, key=lambda entry: entry.path)


def worktree_for_task(task_id: str) -> WorktreeEntry | None:
    """Return the registered worktree whose branch names ``task_id``."""
    for entry in list_worktrees():
        if task_id_from_branch(entry.branch) == task_id:
            return entry
    return None


def base_ref() -> str:
    """Return the branch a new task branch starts from, preferring main."""
    for ref in ["origin/main", "origin/master", "main", "master"]:
        if git_ok(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"]):
            return ref
    return "HEAD"


def worktree_root() -> Path:
    """Return the deterministic root that holds task worktrees.

    Default: a sibling directory named ``<repository>-worktrees``, so no worktree
    path is ever inside the tracked project. ``PROJECT_WORKTREE_ROOT`` overrides
    it for machines that keep worktrees elsewhere. No absolute developer-specific
    path is hard-coded.
    """
    override = os.environ.get(WORKTREE_ROOT_ENV, "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (ROOT.parent / f"{ROOT.name}{WORKTREE_DIR_SUFFIX}").resolve()


def worktree_path(task_id: str) -> Path:
    """Return the deterministic worktree path for ``task_id``."""
    return worktree_root() / task_id


def ensure_root_is_outside_project(root: Path) -> None:
    """Reject a worktree root that would live inside the tracked project."""
    resolved_project = ROOT.resolve()
    if root == resolved_project or resolved_project in root.parents:
        raise ProjectError(
            f"Worktree root {root} is inside the project. Set {WORKTREE_ROOT_ENV} "
            f"to a directory outside {relative(resolved_project)}."
        )


def worktree_is_dirty(path: Path) -> bool:
    """Whether a registered worktree has staged, unstaged, or untracked changes."""
    return bool(git_text(["status", "--porcelain"], cwd=path).strip())


def unique_commit_count(branch: str, base: str | None = None) -> int:
    """Return how many commits ``branch`` has that ``base`` does not."""
    reference = base or base_ref()
    text = git_text(["rev-list", "--count", f"{reference}..{branch}"])
    return int(text.strip() or 0)


def branch_merged(branch: str, base: str | None = None) -> bool:
    """Whether ``branch`` is already contained in the authoritative base."""
    reference = base or base_ref()
    return git_ok(["merge-base", "--is-ancestor", branch, reference])


@dataclass(frozen=True)
class WorktreeAdd:
    """Result of adding one Git worktree for a task branch."""

    task_id: str
    branch: str
    path: str
    base: str
    reused_branch: bool


def add_worktree(task_id: str, title: str) -> WorktreeAdd:
    """Add the worktree and branch for ``task_id``; pure Git mechanics.

    ``task_id`` and ``title`` are the only inputs, so branch and path naming stay
    deterministic. Refuses to touch an existing worktree, path, or branch, and
    leaves the repository unchanged when ``git worktree add`` fails.
    """
    root = worktree_root()
    ensure_root_is_outside_project(root)
    existing = worktree_for_task(task_id)
    if existing is not None:
        raise ProjectError(
            f"Task {task_id} already has worktree {existing.path}. "
            f"Enter it with: cd {existing.path}"
        )
    branch = task_branch_name(task_id, title)
    path = worktree_path(task_id)
    if path.exists():
        raise ProjectError(
            f"Worktree path {path} already exists but is not registered for {task_id}. "
            f"Remove it or set {WORKTREE_ROOT_ENV} to another directory."
        )
    root.mkdir(parents=True, exist_ok=True)
    base = base_ref()
    reused_branch = local_branch_exists(branch)
    args = ["worktree", "add"]
    if not reused_branch:
        args += ["-b", branch]
    args += [str(path), branch if reused_branch else base]
    try:
        git_text(args)
    except ProjectError:
        run_git(["worktree", "remove", "--force", str(path)])
        if not reused_branch:
            run_git(["branch", "-D", branch])
        raise
    return WorktreeAdd(
        task_id=task_id,
        branch=branch,
        path=str(path),
        base=base,
        reused_branch=reused_branch,
    )


def remove_worktree(path: Path) -> None:
    """Remove a registered worktree directory. Callers check safety first."""
    git_text(["worktree", "remove", "--force", str(path)])


def delete_branch(branch: str, *, forced: bool) -> None:
    """Delete a task branch, using the safe form unless ``forced``."""
    run_git(["branch", "-D" if forced else "-d", branch])
