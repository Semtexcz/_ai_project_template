"""Focused tests for the deterministic, runtime-only agent handoff (issue #27).

These tests exercise the real generated tooling inside a throwaway managed
project, so the handoff contract is proven directly: two derivations of the same
repository state are identical, a fresh process reconstructs the same task,
branch, worktree, and claim, the payload stays bounded and free of session
artifacts, ownership mismatches fail loudly, and the ordinary single-session
workflow never needs the handoff.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

TASK_TEMPLATE = """---
id: {task_id}
title: {title}
status: {status}
priority: 1
milestone: M-01
depends_on: {depends_on}
approval_level: A1
approval_status: pending
approved_by:
approved_at:
blocked_reason:
unblock_action:
---

# {task_id}: {title}

## Goal

Ship the fixture task.

## Context

Deterministic handoff fixture.

## Scope

- Implement the scoped change.

## Out of Scope

- Unrelated work.

## Acceptance Criteria

- [x] The first criterion is already satisfied.
- [ ] The second criterion still needs work.
- [ ] The third criterion still needs work.

## Verification

`make check` pending.

## Documentation Impact

Handled by the fixture.

## Completion Notes

Pending.
"""


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
        raise AssertionError(f"Command unexpectedly passed: {' '.join(command)}")
    return result


def git(command: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(
        [
            "git",
            "-c",
            "user.name=Handoff Test",
            "-c",
            "user.email=handoff@example.com",
            *command,
        ],
        cwd,
        expect_success=check,
    )


def copy_project(tmp_path: Path, name: str) -> Path:
    generated = tmp_path / name
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
            "--skip-tasks",
            "--data",
            f"project_name=Handoff {name}",
            "--data",
            "project_type=script",
            "--data",
            "runtime_level=local",
            "--data",
            "governance=managed",
            "--data",
            "workflow_mode=branch",
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


@pytest.fixture(scope="module")
def managed_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return copy_project(tmp_path_factory.mktemp("agent-handoff"), "managed-script")


def env_for(root: Path) -> dict[str, str]:
    return {
        **os.environ,
        "PYTHONPATH": str(root / "tools"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def prepare(
    source: Path,
    tmp_path: Path,
    name: str,
    *,
    task_id: str = "T-002",
    title: str = "Add deterministic handoff",
    status: str = "in-progress",
    baseline_files: tuple[str, ...] = (),
) -> Path:
    """Copy the rendered project, add a task, and claim it on a task branch.

    The task record is committed on the task branch, so the branch diff the
    handoff reports is non-empty and the worktree itself is clean.
    """
    root = tmp_path / name
    shutil.copytree(source, root)
    git(["init", "-b", "main"], root)
    git(["add", "-A"], root)
    git(["commit", "-q", "-m", "chore: fixture"], root)
    for relative in baseline_files:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("baseline\n", encoding="utf-8")
    if baseline_files:
        git(["add", "-A"], root)
        git(["commit", "-q", "-m", "chore: add baseline files"], root)
    branch = f"task/{task_id}-handoff-fixture"
    git(["checkout", "-q", "-b", branch], root)
    task_path = root / "project" / "tasks" / f"{task_id}-handoff-fixture.md"
    task_path.write_text(
        TASK_TEMPLATE.format(task_id=task_id, title=title, status=status, depends_on="[]"),
        encoding="utf-8",
    )
    git(["add", "-A"], root)
    git(["commit", "-q", "-m", "chore: add fixture task"], root)
    claim = (
        "from pathlib import Path\n"
        "from project_tool import claims\n"
        f"claim = claims.create_claim({task_id!r}, {branch!r}, Path.cwd())\n"
        "print(claim.task_id)\n"
    )
    run([sys.executable, "-c", claim], root, env=env_for(root))
    return root


def handoff_text(root: Path, task_id: str = "T-002") -> str:
    return run(
        [sys.executable, "tools/agent.py", "handoff", "--task", task_id],
        root,
        env=env_for(root),
    ).stdout


def handoff_json_output(root: Path, task_id: str = "T-002") -> tuple[str, dict[str, object]]:
    result = run(
        [sys.executable, "tools/agent.py", "handoff", "--task", task_id, "--format", "json"],
        root,
        env=env_for(root),
    )
    payload, _ = json.JSONDecoder().raw_decode(result.stdout[result.stdout.index("{") :])
    assert isinstance(payload, dict)
    return result.stdout, payload


def handoff_json(root: Path, task_id: str = "T-002") -> dict[str, object]:
    return handoff_json_output(root, task_id)[1]


def test_handoff_is_deterministic_across_processes(
    managed_project: Path, tmp_path: Path
) -> None:
    root = prepare(managed_project, tmp_path, "determinism")
    first = run(
        [sys.executable, "tools/agent.py", "handoff", "--task", "T-002", "--format", "json"],
        root,
        env=env_for(root),
    ).stdout
    second = run(
        [sys.executable, "tools/agent.py", "handoff", "--task", "T-002", "--format", "json"],
        root,
        env=env_for(root),
    ).stdout
    # Byte-identical: no timestamp, pid, or other nondeterministic field leaks in.
    assert first == second
    payload = handoff_json(root)
    assert payload["schema_version"] == 1
    assert payload["task"]["id"] == "T-002"
    assert payload["task"]["status"] == "in-progress"
    assert payload["worktree"]["branch"] == "task/T-002-handoff-fixture"
    assert payload["worktree"]["claimed"] is True
    assert payload["worktree"]["ownership_consistent"] is True
    assert payload["worktree"]["head_sha"]
    assert payload["metrics"]["handoff_bytes"] <= 8192
    assert len(first.encode("utf-8")) == payload["metrics"]["handoff_bytes"]


def test_fresh_process_reconstructs_the_same_task_branch_worktree_and_claim(
    managed_project: Path, tmp_path: Path
) -> None:
    root = prepare(managed_project, tmp_path, "fresh-process")
    # Process A: an agent session that then exits, leaving only repository state.
    session_a = handoff_json(root)

    # Process B: a brand-new process with no shared in-memory state.
    session_b = handoff_json(root)

    for field in ("task", "worktree", "resume", "next_action"):
        assert session_a[field] == session_b[field], field
    assert session_a["worktree"]["path"] == session_b["worktree"]["path"]
    assert session_a["worktree"]["claim_task_id"] == "T-002"
    assert session_a["worktree"]["dirty"] is False

    # A third, independent process can resume from the same derived state.
    text = handoff_text(root)
    assert "Task T-002:" in text
    assert "make agent-status" in text
    assert "make agent-context TASK=T-002 MODE=resume" in text


def test_handoff_stays_bounded_for_a_large_deleted_branch_and_compacts_changes(
    managed_project: Path, tmp_path: Path
) -> None:
    deleted_paths = tuple(
        "docs/reference/"
        f"section-{index:03d}-with-a-deliberately-long-descriptive-baseline-name.md"
        for index in range(150)
    )
    root = prepare(managed_project, tmp_path, "large-deletion-task", baseline_files=deleted_paths)
    git(["rm", *deleted_paths], root)
    git(["commit", "-q", "-m", "chore: delete large baseline"], root)

    output, payload = handoff_json_output(root)
    changes = payload["changes"]
    assert len(output.encode("utf-8")) <= 8192
    assert payload["metrics"]["handoff_bytes"] == len(output.encode("utf-8"))
    assert changes["count"] >= len(deleted_paths)
    assert changes["deleted_count"] == len(deleted_paths)
    assert changes["listed"] + changes["omitted"] == changes["count"]
    assert changes["deleted_listed"] + changes["deleted_omitted"] == changes["deleted_count"]
    assert changes["listed"] <= 28
    assert changes["omitted"] > 0
    assert changes["deleted_omitted"] > 0
    assert any(item["deleted"] is True for item in changes["files"])
    assert payload["metrics"]["changed_files_count"] == changes["count"]


def test_handoff_carries_no_transcript_reasoning_diff_log_or_command_history(
    managed_project: Path, tmp_path: Path
) -> None:
    root = prepare(managed_project, tmp_path, "no-leakage")
    text = handoff_text(root)
    payload = handoff_json(root)
    serialized = json.dumps(payload, sort_keys=True)

    forbidden_keys: set[str] = set()

    def collect(value: object) -> None:
        if isinstance(value, dict):
            forbidden_keys.update(str(key) for key in value)
            for item in value.values():
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(payload)
    forbidden = {
        "transcript",
        "reasoning",
        "diff",
        "patch",
        "log",
        "logs",
        "command_history",
        "history",
        "session",
        "session_id",
        "conversation",
        "messages",
        "commands_run",
    }
    assert not (forbidden_keys & forbidden), sorted(forbidden_keys & forbidden)
    for marker in [
        "diff --git",
        "+++ b/",
        "Traceback (most recent call last)",
        "git log -p",
        "command history",
    ]:
        assert marker not in serialized, marker
        assert marker not in text, marker
    # Prose from the task record is not copied; only canonical criteria are kept.
    assert "Deterministic handoff fixture" not in serialized
    assert payload["remaining_acceptance_criteria"] == [
        "The second criterion still needs work.",
        "The third criterion still needs work.",
    ]


def test_handoff_from_the_wrong_task_or_worktree_fails_loudly(
    managed_project: Path, tmp_path: Path
) -> None:
    root = prepare(managed_project, tmp_path, "wrong-task")
    mismatch = run(
        [sys.executable, "tools/agent.py", "handoff", "--task", "T-003"],
        root,
        env=env_for(root),
        expect_success=False,
    )
    output = mismatch.stdout + mismatch.stderr
    assert "owns T-002" in output

    # A control checkout that owns no task must not silently guess one.
    control = tmp_path / "control-checkout"
    shutil.copytree(managed_project, control)
    (control / "project" / "tasks" / "T-002-handoff-fixture.md").write_text(
        TASK_TEMPLATE.format(
            task_id="T-002",
            title="Add deterministic handoff",
            status="in-progress",
            depends_on="[]",
        ),
        encoding="utf-8",
    )
    git(["init", "-b", "main"], control)
    git(["add", "-A"], control)
    git(["commit", "-q", "-m", "chore: control fixture"], control)
    unowned = run(
        [sys.executable, "tools/agent.py", "handoff", "--task", "T-002"],
        control,
        env=env_for(control),
        expect_success=False,
    )
    assert "owns no task" in unowned.stdout + unowned.stderr


def test_handoff_reports_dirty_and_clean_state_deterministically(
    managed_project: Path, tmp_path: Path
) -> None:
    root = prepare(managed_project, tmp_path, "dirty-state")
    assert handoff_json(root)["worktree"]["dirty"] is False
    assert handoff_json(root)["worktree"]["dirty"] is False

    (root / "scratch-note.txt").write_text("uncommitted\n", encoding="utf-8")
    dirty_first = handoff_json(root)["worktree"]["dirty"]
    dirty_second = handoff_json(root)["worktree"]["dirty"]
    assert dirty_first is True
    assert dirty_first == dirty_second


def test_changed_file_summary_is_branch_aware_and_never_embeds_contents(
    managed_project: Path, tmp_path: Path
) -> None:
    root = prepare(managed_project, tmp_path, "change-sources")
    marker = "UNIQUE-INTERNAL-MARKER-DO-NOT-LEAK"
    (root / "staged-module.py").write_text("value = 1\n", encoding="utf-8")
    git(["add", "staged-module.py"], root)
    readme = root / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + f"\n{marker}\n", encoding="utf-8")
    (root / "untracked-note.md").write_text("scratch\n", encoding="utf-8")

    payload = handoff_json(root)
    files = payload["changes"]["files"]
    sources = {item["source"] for item in files}
    assert {"branch", "staged", "worktree", "untracked"} <= sources
    paths = {item["path"] for item in files}
    assert "staged-module.py" in paths
    assert "untracked-note.md" in paths
    assert "README.md" in paths
    assert any(path.startswith("project/tasks/T-002") for path in paths)
    # Sources and paths only: no file contents are embedded anywhere.
    assert marker not in json.dumps(payload, sort_keys=True)


def test_changed_file_entries_preserve_source_and_deletion_state(
    managed_project: Path, tmp_path: Path
) -> None:
    deleted_path = "docs/old-branch-file.md"
    root = prepare(managed_project, tmp_path, "mixed-change-sources", baseline_files=(deleted_path,))
    git(["rm", deleted_path], root)
    git(["commit", "-q", "-m", "chore: delete branch file"], root)
    (root / "staged-added.py").write_text("value = 1\n", encoding="utf-8")
    git(["add", "staged-added.py"], root)
    readme = root / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\nworktree change\n", encoding="utf-8")
    (root / "untracked-file.md").write_text("scratch\n", encoding="utf-8")

    payload = handoff_json(root)
    files = {item["path"]: item for item in payload["changes"]["files"]}
    assert files[deleted_path] == {"source": "branch", "path": deleted_path, "deleted": True}
    assert files["staged-added.py"] == {
        "source": "staged",
        "path": "staged-added.py",
        "deleted": False,
    }
    assert files["README.md"] == {"source": "worktree", "path": "README.md", "deleted": False}
    assert files["untracked-file.md"] == {
        "source": "untracked",
        "path": "untracked-file.md",
        "deleted": False,
    }


def test_recommended_checks_match_agent_context_routing(
    managed_project: Path, tmp_path: Path
) -> None:
    root = prepare(managed_project, tmp_path, "checks-consistency")
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "quality-note.md").write_text("# Note\n", encoding="utf-8")
    context = run(
        [sys.executable, "tools/agent.py", "context", "--task", "T-002", "--format", "json"],
        root,
        env=env_for(root),
    ).stdout
    context_payload, _ = json.JSONDecoder().raw_decode(context[context.index("{") :])

    payload = handoff_json(root)
    assert payload["recommended_checks"] == context_payload["recommended_checks"]
    assert payload["recommended_checks"]
    assert payload["stop_conditions"] == context_payload["stop_conditions"]
    assert payload["next_action"] == context_payload["next_action"]


def test_single_session_workflow_never_requires_handoff(
    managed_project: Path, tmp_path: Path
) -> None:
    root = prepare(managed_project, tmp_path, "single-session")
    status = run(
        ["make", "agent-status"], root, env={**env_for(root), "MAKE": "make"}
    ).stdout
    assert "Owned task: T-002" in status
    assert "make agent-context TASK=T-002" in status

    context = run(
        ["make", "agent-context", "TASK=T-002", "FORMAT=json"],
        root,
        env=env_for(root),
    ).stdout
    context_payload, _ = json.JSONDecoder().raw_decode(context[context.index("{") :])
    assert "project/tasks/T-002-handoff-fixture.md" in context_payload["files"]
    assert context_payload["recommended_checks"]
    # The ordinary loop is complete without ever invoking the handoff.
    assert "agent-handoff" not in status


def test_generated_make_target_renders_and_runs_handoff(
    managed_project: Path, tmp_path: Path
) -> None:
    root = prepare(managed_project, tmp_path, "generated-target")
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    assert "agent-handoff:" in makefile
    assert (root / "tools" / "agent_handoff.py").exists()

    result = run(
        ["make", "agent-handoff", "TASK=T-002", "FORMAT=json"], root, env=env_for(root)
    )
    payload, _ = json.JSONDecoder().raw_decode(result.stdout[result.stdout.index("{") :])
    assert payload["task"]["id"] == "T-002"
    assert payload["metrics"]["recommended_checks_count"] >= 1

    text = run(["make", "agent-handoff", "TASK=T-002"], root, env=env_for(root)).stdout
    assert "Resume: cd " in text
    assert "Handoff bytes:" in text
