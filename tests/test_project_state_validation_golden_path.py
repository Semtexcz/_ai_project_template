from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], cwd: Path, *, expect_success: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if expect_success and result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)
    if not expect_success and result.returncode == 0:
        raise AssertionError(f"Command unexpectedly passed: {' '.join(command)}")
    return result


def write_task(
    root: Path,
    task_id: str,
    *,
    status: str = "backlog",
    depends_on: str = "[]",
    approval_level: str = "A0",
    approval_status: str = "not-required",
    approved_by: str = "",
    approved_at: str = "",
    blocked_reason: str = "",
    unblock_action: str = "",
    priority: str = "1",
    milestone: str = "M-01",
    checked: bool = True,
    include_ready: bool = True,
    completion_notes: str = "Completed.",
) -> None:
    ready_sections = """
## Goal

Ship the task.

## Context

Project-state validation test fixture.

## Scope

- Implement the scoped task.

## Out of Scope

- Unrelated work.
""" if include_ready else """
## Goal

Ship the task.
"""
    checkbox = "x" if checked else " "
    text = f"""---
id: {task_id}
title: Task {task_id}
status: {status}
priority: {priority}
milestone: {milestone}
depends_on: {depends_on}
approval_level: {approval_level}
approval_status: {approval_status}
approved_by: {approved_by}
approved_at: {approved_at}
blocked_reason: {blocked_reason}
unblock_action: {unblock_action}
---

# {task_id}: Task
{ready_sections}
## Acceptance Criteria

- [{checkbox}] Criterion is met.

## Verification

`make validate-project` passed.

## Documentation Impact

Handled.

## Completion Notes

{completion_notes}
"""
    (root / "project" / "tasks" / f"{task_id}-task.md").write_text(text)


def make_project(tmp_path: Path, *, profile: str = "script") -> Path:
    root = tmp_path / profile
    (root / "tools").mkdir(parents=True)
    (root / "project" / "tasks").mkdir(parents=True)
    (root / "docs").mkdir()
    shutil.copy(ROOT / "template" / "tools" / "project.py", root / "tools" / "project.py")
    (root / "Makefile").write_text(
        "\n".join(
            [
                "project-status:",
                "\tpython tools/project.py status",
                "sync-project-docs:",
                "\tpython tools/project.py sync",
                "validate-project:",
                "\tpython tools/project.py validate",
                "task-ready:",
                "\tpython tools/project.py ready $(TASK)",
                "task-start:",
                "\tpython tools/project.py start $(TASK)",
                "task-review:",
                "\tpython tools/project.py review $(TASK)",
                "task-complete:",
                "\tpython tools/project.py complete $(TASK)",
                "task-block:",
                "\tpython tools/project.py block $(TASK) --reason \"$(REASON)\" --unblock \"$(UNBLOCK)\"",
                "task-approve:",
                "\tpython tools/project.py approve $(TASK) --approved-by \"$(APPROVED_BY)\"",
                "",
            ]
        )
    )
    (root / "project" / "state.yaml").write_text(
        f"""schema_version: 1

project:
  name: Test Project
  type: {profile}
  runtime_level: local
  risk: medium
  status: active

lifecycle:
  phase: delivery
  milestone: M-01
  next_gate: project-state-validation-complete

work:
  active_task: T-001
  blocked: false

template:
  version: v1.1.0
"""
    )
    write_task(root, "T-001", status="in-progress")
    write_task(root, "T-002", status="backlog", depends_on="[T-001]", approval_level="A1", approval_status="pending")
    write_task(root, "T-003", status="backlog", depends_on="[T-002]", approval_level="A2", approval_status="pending")
    (root / "README.md").write_text(
        "# Test Project\n\n<!-- project-status:start -->\nstale\n<!-- project-status:end -->\n\n[Project](project/index.md)\n"
    )
    (root / "project" / "index.md").write_text(
        "# Project Dashboard\n\n<!-- project-index:start -->\nstale\n<!-- project-index:end -->\n\n[Board](board.md)\n[Roadmap](roadmap.md)\n"
    )
    (root / "project" / "board.md").write_text(
        "# Board\n\n<!-- kanban:start -->\nstale\n<!-- kanban:end -->\n"
    )
    (root / "project" / "roadmap.md").write_text("# Roadmap\n")
    (root / "AGENTS.md").write_text("# Agents\n\n[Workflow](docs/workflow.md)\n")
    (root / "docs" / "workflow.md").write_text("# Workflow\n")
    run(["make", "sync-project-docs"], root)
    return root


def test_project_state_validation_positive_lifecycle(tmp_path: Path) -> None:
    root = make_project(tmp_path)
    run(["make", "validate-project"], root)
    status = run(["make", "project-status"], root).stdout
    assert "Complete T-001" in status

    run(["make", "task-complete", "TASK=T-001"], root)
    run(["make", "task-ready", "TASK=T-002"], root)
    run(["make", "task-start", "TASK=T-002"], root)
    run(["make", "task-review", "TASK=T-002"], root)
    result = run(["make", "task-complete", "TASK=T-002"], root, expect_success=False)
    assert "Human A1 approval is required" in result.stdout
    run(["make", "task-approve", "TASK=T-002", "APPROVED_BY=Test Human"], root)
    run(["make", "task-complete", "TASK=T-002"], root)

    run(["make", "task-ready", "TASK=T-003"], root)
    result = run(["make", "task-start", "TASK=T-003"], root, expect_success=False)
    assert "Human A2 approval is required" in result.stdout
    run(["make", "task-approve", "TASK=T-003", "APPROVED_BY=Test Human"], root)
    run(["make", "task-start", "TASK=T-003"], root)
    run(["make", "validate-project"], root)

    before = (root / "README.md").read_text() + (root / "project" / "index.md").read_text() + (root / "project" / "board.md").read_text()
    run(["make", "sync-project-docs"], root)
    after = (root / "README.md").read_text() + (root / "project" / "index.md").read_text() + (root / "project" / "board.md").read_text()
    assert before == after


def test_project_state_validation_fullstack_profile(tmp_path: Path) -> None:
    root = make_project(tmp_path, profile="fullstack")
    run(["make", "validate-project"], root)
    assert "Project state is valid" in run(["make", "validate-project"], root).stdout


def corrupt_state_active_missing(root: Path) -> None:
    text = (root / "project" / "state.yaml").read_text()
    (root / "project" / "state.yaml").write_text(text.replace("active_task: T-001", "active_task: T-999"))


def clear_state_active(root: Path) -> None:
    text = (root / "project" / "state.yaml").read_text()
    (root / "project" / "state.yaml").write_text(text.replace("active_task: T-001", "active_task:"))


def set_task(root: Path, task_id: str, old: str, new: str) -> None:
    path = root / "project" / "tasks" / f"{task_id}-task.md"
    path.write_text(path.read_text().replace(old, new))


NEGATIVE_CASES: list[tuple[str, Callable[[Path], None], str]] = [
    ("missing active task", clear_state_active, "must be T-001"),
    ("state references missing task", corrupt_state_active_missing, "does not exist"),
    ("two in-progress tasks", lambda root: set_task(root, "T-002", "status: backlog", "status: in-progress"), "More than one task"),
    ("active blocked task", lambda root: set_task(root, "T-001", "status: in-progress", "status: blocked"), "Active task T-001 is blocked"),
    ("invalid task status", lambda root: set_task(root, "T-001", "status: in-progress", "status: flying"), "invalid status"),
    (
        "duplicate task id",
        lambda root: (root / "project" / "tasks" / "T-900-duplicate.md").write_text(
            (root / "project" / "tasks" / "T-001-task.md").read_text()
        ),
        "Duplicate task id",
    ),
    ("missing dependency", lambda root: set_task(root, "T-002", "depends_on: [T-001]", "depends_on: [T-999]"), "dependency T-999 does not exist"),
    ("self dependency", lambda root: set_task(root, "T-001", "depends_on: []", "depends_on: [T-001]"), "cannot depend on itself"),
    ("direct dependency cycle", lambda root: (set_task(root, "T-001", "depends_on: []", "depends_on: [T-002]"), set_task(root, "T-002", "depends_on: [T-001]", "depends_on: [T-001]")), "Task dependency cycle detected"),
    ("indirect dependency cycle", lambda root: set_task(root, "T-001", "depends_on: []", "depends_on: [T-003]"), "Task dependency cycle detected"),
    ("ready dependency not done", lambda root: set_task(root, "T-002", "status: backlog", "status: ready"), "dependencies are not done"),
    ("missing Definition of Ready", lambda root: write_task(root, "T-001", status="in-progress", include_ready=False), "Definition of Ready"),
    ("done unchecked criterion", lambda root: write_task(root, "T-001", status="done", checked=False), "all Acceptance Criteria"),
    ("done missing completion notes", lambda root: write_task(root, "T-001", status="done", completion_notes=""), "Completion Notes"),
    ("A1 done without approval", lambda root: write_task(root, "T-001", status="done", approval_level="A1", approval_status="pending"), "A1 task cannot be done"),
    ("A2 started without approval", lambda root: write_task(root, "T-001", status="in-progress", approval_level="A2", approval_status="pending"), "A2 task cannot start"),
    ("blocked without reason", lambda root: write_task(root, "T-001", status="blocked", blocked_reason="", unblock_action=""), "blocked task requires"),
    ("stale README", lambda root: (root / "README.md").write_text((root / "README.md").read_text().replace("Project type", "Project kind")), "README.md generated block is stale"),
    ("stale project index", lambda root: (root / "project" / "index.md").write_text((root / "project" / "index.md").read_text().replace("Recommended next action", "Next")), "project/index.md generated block is stale"),
    ("stale board", lambda root: (root / "project" / "board.md").write_text((root / "project" / "board.md").read_text().replace("In Progress", "Doing")), "project/board.md generated block is stale"),
    ("broken internal link", lambda root: (root / "README.md").write_text((root / "README.md").read_text() + "\n[Broken](missing.md)\n"), "broken internal Markdown link"),
    ("invalid transition", lambda root: None, "Invalid transition"),
    ("invalid approval date", lambda root: write_task(root, "T-001", status="done", approval_level="A1", approval_status="approved", approved_by="Human", approved_at="not-a-date"), "approved_at is invalid"),
]


def test_project_state_validation_negative_cases(tmp_path: Path) -> None:
    for index, (name, mutate, expected) in enumerate(NEGATIVE_CASES):
        root = make_project(tmp_path / str(index))
        if name == "invalid transition":
            result = run(["make", "task-complete", "TASK=T-002"], root, expect_success=False)
        else:
            mutate(root)
            result = run([sys.executable, "tools/project.py", "validate"], root, expect_success=False)
        output = result.stdout + result.stderr
        assert expected in output, name
