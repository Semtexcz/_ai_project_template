"""Read-only Git provenance for PR-mode completion.

Every Git read is explicit and deterministic: no GitHub API calls and no merge
commit message parsing. Merge commits, squash merges, and rebase/fast-forward
merges therefore behave alike, because provenance compares the task record text
present in the authoritative base tree with the working copy.
"""

from __future__ import annotations

import subprocess
from typing import Any

from project_tool.model import (
    GITHUB_MERGE_LEVELS,
    ROOT,
    Task,
    is_github_pr_mode,
    relative,
)


def git_stdout(args: list[str]) -> str | None:
    """Return stdout from a read-only Git command, or None when it cannot run."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def git_authoritative_base_ref() -> str | None:
    """Resolve the branch whose history is authoritative for PR completion.

    A checkout of main/master is itself the authoritative post-merge view. On a
    feature branch, prefer the remote-tracking base and retain Agent Efficiency's
    local main/master fallbacks for repositories without a configured remote.
    """
    current = (git_stdout(["branch", "--show-current"]) or "").strip()
    if current in {"main", "master"}:
        return "HEAD"
    for ref in ["origin/main", "origin/master", "main", "master"]:
        if git_stdout(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"]) is not None:
            return ref
    return None


def task_merge_completed(state: dict[str, Any] | None, task: Task) -> bool:
    """Whether this review-ready A1/A2 record has landed on the base branch.

    The persisted record remains ``review``/``pending``. Completion is derived
    only when the same task record is present in the authoritative base tree, so
    merge commits, squash merges, and rebase/fast-forward merges behave alike.
    """
    if (
        state is None
        or not is_github_pr_mode(state)
        or task.status != "review"
        or task.approval_level not in GITHUB_MERGE_LEVELS
    ):
        return False
    base_ref = git_authoritative_base_ref()
    if base_ref is None:
        return False
    task_path = relative(task.path)
    base_text = git_stdout(["show", f"{base_ref}:{task_path}"])
    if base_text is None:
        return False
    return base_text == task.path.read_text(encoding="utf-8")


def github_merge_completes(state: dict[str, Any] | None, task: Task) -> bool:
    """Compatibility name for the canonical Git-provenance completion check."""
    return task_merge_completed(state, task)
