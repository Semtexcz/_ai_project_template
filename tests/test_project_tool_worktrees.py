"""Focused seam tests for task-scoped worktree isolation and local claims.

These tests exercise the real Git and filesystem primitives in a throwaway
governed repository, so the concurrency guarantees of issue #18 are proven
directly: atomic claims, one worktree per task, loud branch/claim mismatches,
explicit stale-claim release, and safe cleanup defaults.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "template" / "tools"

STATE = """schema_version: 1

project:
  name: Worktree fixture
  type: script
  runtime_level: local
  governance: managed
  workflow_mode: branch
  risk: medium
  status: active

lifecycle:
  phase: delivery
  milestone: M-01
  next_gate: fixture-gate

template:
  version: v1.0.0
"""

TASK_TEMPLATE = """---
id: {task_id}
title: Task {task_id}
status: {status}
priority: 1
milestone: M-01
depends_on: {depends_on}
approval_level: A0
approval_status: not-required
approved_by:
approved_at:
blocked_reason:
unblock_action:
---

# {task_id}: Fixture Task

## Goal

Ship the fixture task.

## Context

Worktree/claim seam fixture.

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

PREFIX = """
import json
from pathlib import Path
from project_tool import claims, commands, worktrees

def report(payload):
    print(json.dumps(payload, default=str))
"""


def git(args: list[str], cwd: Path) -> None:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)


def env_for(root: Path) -> dict[str, str]:
    return {
        **os.environ,
        "PYTHONPATH": str(TOOLS_DIR),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PROJECT_WORKTREE_ROOT": str(root.parent / f"{root.name}-worktrees"),
    }


def run_snippet(root: Path, snippet: str, *, expect_success: bool = True) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, "-c", PREFIX + snippet],
        cwd=root,
        env=env_for(root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if expect_success and result.returncode != 0:
        raise AssertionError(snippet + "\n" + result.stdout + result.stderr)
    if not expect_success and result.returncode == 0:
        raise AssertionError(f"Snippet unexpectedly passed:\n{snippet}\n{result.stdout}")
    for line in reversed(result.stdout.splitlines()):
        if line.startswith("{"):
            payload: dict[str, object] = json.loads(line)
            return payload
    raise AssertionError(f"No JSON result from snippet:\n{snippet}\n{result.stdout}{result.stderr}")


def make_repo(tmp_path: Path) -> Path:
    root = tmp_path / "governed"
    (root / "project" / "tasks").mkdir(parents=True)
    (root / "project" / "state.yaml").write_text(STATE, encoding="utf-8")
    for task_id, status, depends_on in [
        ("T-101", "ready", "[]"),
        ("T-102", "ready", "[]"),
        ("T-103", "backlog", "[T-101]"),
    ]:
        (root / "project" / "tasks" / f"{task_id}-fixture.md").write_text(
            TASK_TEMPLATE.format(task_id=task_id, status=status, depends_on=depends_on),
            encoding="utf-8",
        )
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
            "chore: fixture",
        ],
        root,
    )
    return root


def test_two_racing_agents_cannot_both_claim_one_task(tmp_path: Path) -> None:
    """Exactly one of two concurrent claim attempts wins."""
    root = make_repo(tmp_path)
    snippet = (
        PREFIX
        + """
try:
    claim = claims.create_claim("T-101", "task/T-101-fixture", Path("."))
    report({"ok": True, "pid": claim.pid})
except Exception as exc:
    report({"ok": False, "error": str(exc)})
"""
    )
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", snippet],
            cwd=root,
            env=env_for(root),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(2)
    ]
    outputs = [process.communicate()[0] for process in processes]
    results = [
        json.loads(line)
        for output in outputs
        for line in output.splitlines()
        if line.startswith("{")
    ]
    assert len(results) == 2, outputs
    assert sum(1 for result in results if result["ok"]) == 1, results
    loser = next(result for result in results if not result["ok"])
    assert "already claimed" in str(loser["error"])

    # The winner is observable and survives separate processes.
    listing = run_snippet(
        root, 'report({"claims": [claim.as_dict() for claim in claims.inspect_claims()]})'
    )
    assert len(listing["claims"]) == 1


def test_one_worktree_owns_at_most_one_task(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    first = run_snippet(
        root,
        'claim = claims.create_claim("T-101", "task/T-101-fixture", Path(".")); '
        'report({"task": claim.task_id})',
    )
    assert first["task"] == "T-101"
    second = run_snippet(
        root,
        """
try:
    claims.create_claim("T-102", "task/T-102-fixture", Path("."))
    report({"ok": True})
except Exception as exc:
    report({"ok": False, "error": str(exc)})
""",
    )
    assert second["ok"] is False
    assert "already owns T-101" in str(second["error"])


def test_branch_claim_and_task_argument_mismatches_fail_loudly(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    git(["checkout", "-q", "-b", "task/T-101-fixture"], root)
    run_snippet(
        root,
        'claims.create_claim("T-101", "task/T-101-fixture", Path(".")); report({"ok": True})',
    )
    # The branch says T-101: asking the resolver about T-102 is a conflict.
    conflict = run_snippet(
        root,
        'report({"errors": claims.ownership_errors("T-102"), '
        '"notes": list(claims.resolve_owner().notes)})',
    )
    assert any("owns T-101" in error for error in conflict["errors"])

    # A claim that points at another branch is rejected instead of guessed.
    mismatch = run_snippet(
        root,
        """
claim = claims.read_claim("T-101")
claims.claim_path("T-101").write_text(
    json.dumps({**claim.as_dict(), "branch": "task/T-999-other"})
)
report({"errors": claims.resolve_owner().errors})
""",
    )
    assert any("points at branch task/T-999-other" in error for error in mismatch["errors"])

    # A claim owned by another worktree is rejected as well.
    moved = run_snippet(
        root,
        """
claim = claims.read_claim("T-101")
claims.claim_path("T-101").write_text(
    json.dumps({**claim.as_dict(), "worktree": str(Path("/tmp/elsewhere"))})
)
report({"errors": claims.resolve_owner().errors})
""",
    )
    assert any("belongs to worktree" in error for error in moved["errors"])


def test_conflicting_branch_task_id_rejects_agent_commands(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    git(["checkout", "-q", "-b", "task/T-102-fixture"], root)
    run_snippet(
        root,
        'claims.create_claim("T-102", "task/T-102-fixture", Path(".")); report({"ok": True})',
    )
    errors = run_snippet(root, 'report({"errors": claims.ownership_errors("T-101")})')
    assert errors["errors"]
    assert any("owns T-102" in str(error) for error in errors["errors"])


def test_dependent_task_cannot_be_claimed_early(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    blocked = subprocess.run(
        [sys.executable, "-c", PREFIX + "commands.create_worktree('T-103')"],
        cwd=root,
        env=env_for(root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert blocked.returncode != 0
    assert "cannot start until dependencies are done: T-101" in blocked.stdout + blocked.stderr
    assert not (root.parent / f"{root.name}-worktrees" / "T-103").exists()
    assert run_snippet(root, 'report({"claims": claims.claim_dicts()})')["claims"] == []


def test_stale_claim_is_released_explicitly(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    run_snippet(
        root,
        'claims.create_claim("T-101", "task/T-101-fixture", Path(".")); report({"ok": True})',
    )
    released = run_snippet(
        root,
        'claim = claims.release_claim("T-101"); report({"branch": claim.branch, '
        '"gone": claims.read_claim("T-101") is None})',
    )
    assert released["branch"] == "task/T-101-fixture"
    assert released["gone"] is True
    again = run_snippet(
        root,
        """
try:
    claims.release_claim("T-101")
    report({"ok": True})
except Exception as exc:
    report({"ok": False, "error": str(exc)})
""",
    )
    assert again["ok"] is False
    assert "no local claim to release" in str(again["error"])


def test_cleanup_refuses_dirty_and_unmerged_work(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    created = run_snippet(
        root,
        'creation = commands.create_task_worktree("T-101", "Task T-101"); '
        'report({"path": creation.path, "branch": creation.branch})',
    )
    worktree = Path(str(created["path"]))
    branch = str(created["branch"])
    assert worktree.is_dir()
    assert branch == "task/T-101-task-t-101"

    # Dirty work is refused.
    (worktree / "scratch.txt").write_text("wip\n", encoding="utf-8")
    dirty = run_snippet(
        root,
        """
try:
    commands.remove_task_worktree("T-101")
    report({"ok": True})
except Exception as exc:
    report({"ok": False, "error": str(exc)})
""",
    )
    assert dirty["ok"] is False
    assert "uncommitted changes" in str(dirty["error"])
    assert worktree.exists()

    # Unique unmerged commits are refused even when the worktree is clean.
    (worktree / "scratch.txt").unlink()
    (worktree / "feature.txt").write_text("reviewed work\n", encoding="utf-8")
    git(["add", "-A"], worktree)
    git(
        [
            "-c",
            "user.name=Test Agent",
            "-c",
            "user.email=agent@example.com",
            "commit",
            "-q",
            "-m",
            "feat: unique work",
        ],
        worktree,
    )
    unmerged = run_snippet(
        root,
        """
try:
    commands.remove_task_worktree("T-101")
    report({"ok": True})
except Exception as exc:
    report({"ok": False, "error": str(exc)})
""",
    )
    assert unmerged["ok"] is False
    assert "unique" in str(unmerged["error"])
    assert worktree.exists()

    # An explicit override is the only destructive path.
    forced = run_snippet(
        root,
        'removal = commands.remove_task_worktree("T-101", force=True); '
        'report({"released": removal.claim_released, "forced": removal.forced})',
    )
    assert forced == {"released": True, "forced": True}
    assert not worktree.exists()
    remaining = subprocess.run(
        ["git", "branch", "--list", branch],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        check=False,
    ).stdout
    assert branch not in remaining
    assert run_snippet(root, 'report({"claims": claims.claim_dicts()})')["claims"] == []


def test_worktree_states_report_claim_worktree_and_state(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    run_snippet(
        root,
        'commands.create_task_worktree("T-101", "Task T-101"); report({"ok": True})',
    )
    listing = run_snippet(
        root,
        'report({"rows": [[state.task_id, state.branch, state.state, state.claimed] '
        "for state in claims.worktree_states()]})",
    )
    rows = listing["rows"]
    assert len(rows) == 1
    assert rows[0][0] == "T-101"
    assert rows[0][1] == "task/T-101-task-t-101"
    assert rows[0][2] == "clean"
    assert rows[0][3] is True
