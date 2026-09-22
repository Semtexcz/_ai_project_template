"""Two-agent parallel worktree golden path in a rendered managed project.

This is the realistic end-to-end proof for issue #18: two independent tasks are
worked concurrently in separate Git worktrees, each with its own deterministic
branch and local claim, and each reaching its own review-ready pull request. It
also proves that merging one task leaves the other worktree valid and usable.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(
    command: list[str],
    cwd: Path,
    *,
    expect_success: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if expect_success and result.returncode != 0:
        raise AssertionError(
            f"Command failed: {' '.join(command)}\n{result.stdout}\n{result.stderr}"
        )
    if not expect_success and result.returncode == 0:
        raise AssertionError(f"Command unexpectedly passed: {' '.join(command)}\n{result.stdout}")
    return result


GIT_IDENTITY = [
    "-c",
    "user.name=Test Human",
    "-c",
    "user.email=human@example.com",
]


def git(command: list[str], cwd: Path) -> str:
    """Run Git with an explicit identity, so CI without user config still works."""
    return run(["git", *GIT_IDENTITY, *command], cwd).stdout


def parse_json(stdout: str) -> dict[str, object]:
    payload, _ = json.JSONDecoder().raw_decode(stdout[stdout.index("{") :])
    return payload


TASK_BODY = """
## Goal

Ship the task.

## Context

Parallel worktree golden-path fixture.

## Scope

- Implement the scoped change.

## Out of Scope

- Unrelated work.

## Acceptance Criteria

- [ ] Criterion is met.

## Verification

`make validate-project` passes.

## Documentation Impact

Handled.
"""


def write_task(root: Path, task_id: str) -> None:
    path = root / "project" / "tasks" / f"{task_id}-parallel.md"
    path.write_text(
        f"""---
id: {task_id}
title: Parallel task {task_id}
status: ready
priority: 1
milestone: M-01
depends_on: []
approval_level: A1
approval_status: pending
approved_by:
approved_at:
blocked_reason:
unblock_action:
---
{TASK_BODY}""",
        encoding="utf-8",
    )


def copy_project(tmp_path: Path) -> Path:
    generated = tmp_path / "parallel-project"
    env = {
        **os.environ,
        "UV_LINK_MODE": "copy",
        "UV_CACHE_DIR": str(tmp_path / "uv-cache"),
    }
    run(
        [
            sys.executable,
            "-m",
            "copier",
            "copy",
            "--defaults",
            "--data",
            "project_name=Parallel project",
            "--data",
            "project_type=script",
            "--data",
            "runtime_level=local",
            "--data",
            "governance=managed",
            "--data",
            "workflow_mode=pr",
            "--data",
            "include_reference_feature=false",
            "--trust",
            "--vcs-ref=HEAD",
            str(ROOT),
            str(generated),
        ],
        ROOT,
        env=env,
    )
    return generated


def prepare(root: Path, tmp_path: Path) -> None:
    """Give the project a Git repository and two independent ready tasks."""
    env = {
        **os.environ,
        "UV_LINK_MODE": "copy",
        "UV_CACHE_DIR": str(tmp_path / "uv-cache"),
    }
    write_task(root, "T-002")
    write_task(root, "T-003")
    run(["make", "setup"], root, env=env)
    run(["make", "sync-project-docs"], root, env=env)
    git(["init", "-b", "main"], root)
    git(["add", "-A"], root)
    git(
        [
            "-c",
            "user.name=Test Human",
            "-c",
            "user.email=human@example.com",
            "commit",
            "-q",
            "-m",
            "chore: baseline",
        ],
        root,
    )


def worktree_path_of(stdout: str) -> Path:
    for line in stdout.splitlines():
        if line.startswith("Worktree:"):
            return Path(line.split("Worktree:", 1)[1].strip())
    raise AssertionError(f"No worktree path in output:\n{stdout}")


def branch_of(stdout: str) -> str:
    for line in stdout.splitlines():
        if line.startswith("Branch:"):
            return line.split("Branch:", 1)[1].strip()
    raise AssertionError(f"No branch in output:\n{stdout}")


def test_two_agents_work_independent_tasks_in_isolated_worktrees(tmp_path: Path) -> None:
    root = copy_project(tmp_path)
    prepare(root, tmp_path)
    env = {**os.environ, "UV_LINK_MODE": "copy", "UV_CACHE_DIR": str(tmp_path / "uv-cache")}

    creation_a = run(["make", "agent-worktree", "TASK=T-002"], root, env=env).stdout
    creation_b = run(["make", "agent-worktree", "TASK=T-003"], root, env=env).stdout
    worktree_a = worktree_path_of(creation_a)
    worktree_b = worktree_path_of(creation_b)
    branch_a = branch_of(creation_a)
    branch_b = branch_of(creation_b)

    # Distinct branches and worktrees, both outside the tracked project tree.
    assert branch_a != branch_b
    assert branch_a == "task/T-002-parallel-task-t-002"
    assert branch_b == "task/T-003-parallel-task-t-003"
    assert worktree_a != worktree_b
    assert root not in worktree_a.parents and root not in worktree_b.parents

    # Both tasks may be active at once, each in its own worktree.
    run(["make", "task-start", "TASK=T-002"], worktree_a, env=env)
    run(["make", "task-start", "TASK=T-003"], worktree_b, env=env)

    status_a = run(["make", "agent-status"], worktree_a, env=env).stdout
    status_b = run(["make", "agent-status"], worktree_b, env=env).stdout
    assert "Checkout: task/T-002-parallel-task-t-002" in status_a
    assert "Owned task: T-002" in status_a
    assert "Claim: yes" in status_a
    assert "Owned task: T-003" in status_b

    # Uncommitted work stays isolated to its own worktree.
    feature_a = worktree_a / "src" / "feature_a.py"
    feature_a.write_text("FEATURE_A = True\n", encoding="utf-8")
    assert feature_a.exists()
    assert not (worktree_b / "src" / "feature_a.py").exists()

    # Branch-specific context and diff never include the other worktree's work.
    context_a = parse_json(
        run(["make", "agent-context", "TASK=T-002", "FORMAT=json"], worktree_a, env=env).stdout
    )
    context_b = parse_json(
        run(["make", "agent-context", "TASK=T-003", "FORMAT=json"], worktree_b, env=env).stdout
    )
    assert "src/feature_a.py" in context_a["changed_files"]
    assert "src/feature_a.py" not in context_b["changed_files"]
    assert "project/tasks/T-002-parallel.md" in context_a["changed_files"]
    assert "project/tasks/T-002-parallel.md" not in context_b["changed_files"]

    # A transition never rewrites a shared global file.
    assert "active_task" not in (worktree_a / "project" / "state.yaml").read_text()
    run(["make", "validate-project"], worktree_a, env=env)
    run(["make", "validate-project"], worktree_b, env=env)

    # Each task independently reaches review and its own PR-ready state.
    run(["make", "agent-pre-review", "TASK=T-002"], worktree_a, env=env)
    run(["make", "task-review", "TASK=T-002"], worktree_a, env=env)
    run(["make", "task-review", "TASK=T-003"], worktree_b, env=env)
    for worktree, task_id in [(worktree_a, "T-002"), (worktree_b, "T-003")]:
        run(
            ["make", "pr-validate"],
            worktree,
            env={
                **env,
                "PR_HEAD_REF": f"task/{task_id}-x",
                "PR_TITLE": f"{task_id}: parallel work",
                "PR_BODY": "",
            },
        )

    # Agent A commits its own work on its own branch, so its PR is mergeable.
    git(["add", "-A"], worktree_a)
    git(
        [
            "commit",
            "-q",
            "-m",
            "feat(T-002): parallel work",
        ],
        worktree_a,
    )

    # Main is untouched by either task branch: the worktrees hold the work.
    assert "status: ready" in (root / "project" / "tasks" / "T-002-parallel.md").read_text()

    # Merging T-002 must leave T-003's worktree valid and usable.
    git(["merge", "--no-ff", "-q", "-m", "merge T-002", branch_a], root)
    assert "status: review" in (root / "project" / "tasks" / "T-002-parallel.md").read_text()
    run(["make", "validate-project"], worktree_b, env=env)
    assert "Owned task: T-003" in run(["make", "agent-status"], worktree_b, env=env).stdout
    assert "Claim: yes" in run(["make", "agent-status"], worktree_b, env=env).stdout
    task_b_text = (worktree_b / "project" / "tasks" / "T-003-parallel.md").read_text()
    assert task_b_text.count("status: review") == 1

    # Updating the surviving worktree uses normal Git and stays conflict-free,
    # because no committed shared file encoded task status.
    git(["merge", "-q", "-m", "update from main", "main"], worktree_b)
    run(["make", "validate-project"], worktree_b, env=env)
    assert "status: review" in (worktree_b / "project" / "tasks" / "T-002-parallel.md").read_text()
    assert "status: review" in (worktree_b / "project" / "tasks" / "T-003-parallel.md").read_text()
    assert "Owned task: T-003" in run(["make", "agent-status"], worktree_b, env=env).stdout

    # Cleanup refuses to discard the surviving worktree's unique commits, and
    # an explicit override is required to remove it.
    refusal = run(
        ["make", "agent-worktree-remove", "TASK=T-003"], root, env=env, expect_success=False
    )
    assert "Refusing to remove worktree" in refusal.stdout
    assert worktree_b.exists()
    run(["make", "agent-worktree-remove", "TASK=T-003", "FORCE=1"], root, env=env)
    assert not worktree_b.exists()
    listing = run(["make", "agent-worktrees"], root, env=env).stdout
    assert "T-003" not in listing
