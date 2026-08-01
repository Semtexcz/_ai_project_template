from __future__ import annotations

import os
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


def run_with_env(
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    *,
    expect_success: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env={**os.environ, **env},
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
    profile_markers = {
        "script": "Python CLI package",
        "library": "Python library package",
        "backend": "FastAPI service",
        "frontend": "Nuxt application",
        "fullstack": "FastAPI backend and Nuxt frontend",
    }
    marker = profile_markers[profile]
    (root / "tools").mkdir(parents=True)
    (root / "project" / "tasks").mkdir(parents=True)
    (root / "docs").mkdir()
    shutil.copy(ROOT / "template" / "tools" / "project.py", root / "tools" / "project.py")
    (root / "Makefile").write_text(
        "\n".join(
            [
                "project-status:",
                "\tPYTHONDONTWRITEBYTECODE=1 python tools/project.py status",
                "sync-project-docs:",
                "\tPYTHONDONTWRITEBYTECODE=1 python tools/project.py sync",
                "validate-project:",
                "\tPYTHONDONTWRITEBYTECODE=1 python tools/project.py validate",
                "validate-docs:",
                "\tPYTHONDONTWRITEBYTECODE=1 python tools/project.py validate-docs",
                "task-ready:",
                "\tPYTHONDONTWRITEBYTECODE=1 python tools/project.py ready $(TASK)",
                "task-start:",
                "\tPYTHONDONTWRITEBYTECODE=1 python tools/project.py start $(TASK)",
                "task-review:",
                "\tPYTHONDONTWRITEBYTECODE=1 python tools/project.py review $(TASK)",
                "task-complete:",
                "\tPYTHONDONTWRITEBYTECODE=1 python tools/project.py complete $(TASK)",
                "task-block:",
                "\tPYTHONDONTWRITEBYTECODE=1 python tools/project.py block $(TASK) --reason \"$(REASON)\" --unblock \"$(UNBLOCK)\"",
                "task-unblock:",
                "\tPYTHONDONTWRITEBYTECODE=1 python tools/project.py unblock $(TASK)",
                "task-cancel:",
                "\tPYTHONDONTWRITEBYTECODE=1 python tools/project.py cancel $(TASK)",
                "task-approve:",
                "\tPYTHONDONTWRITEBYTECODE=1 python tools/project.py approve $(TASK) --approved-by \"$(APPROVED_BY)\"",
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
        "\n".join(
            [
                "# Test Project",
                "",
                f"Test Project is a fixture. Current architecture: {marker}.",
                "",
                "<!-- project-status:start -->",
                "stale",
                "<!-- project-status:end -->",
                "",
                "[Product](docs/product.md)",
                "[Architecture](docs/architecture.md)",
                "[Workflow](docs/workflow.md)",
                "[Roadmap](project/roadmap.md)",
                "[Board](project/board.md)",
                "",
                "```bash",
                "make validate-project",
                "make validate-docs",
                "```",
                "",
            ]
        )
    )
    (root / "project" / "index.md").write_text(
        "# Project Dashboard\n\n<!-- project-index:start -->\nstale\n<!-- project-index:end -->\n\n[Board](board.md)\n[Roadmap](roadmap.md)\n"
    )
    (root / "project" / "board.md").write_text(
        "# Board\n\n<!-- kanban:start -->\nstale\n<!-- kanban:end -->\n"
    )
    (root / "project" / "roadmap.md").write_text("# Roadmap\n")
    (root / "AGENTS.md").write_text("# Agents\n\n[Workflow](docs/workflow.md)\n")
    (root / "docs" / "product.md").write_text("# Product\n\nTest fixture product.\n")
    (root / "docs" / "architecture.md").write_text(
        f"# Architecture\n\nCurrent architecture: {marker}.\n"
    )
    (root / "docs" / "workflow.md").write_text("# Workflow\n")
    (root / "docs" / "quality.md").write_text("# Quality\n")
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


CONTROL_PATHS = [
    Path("project/state.yaml"),
    Path("README.md"),
    Path("project/index.md"),
    Path("project/board.md"),
]


def control_snapshot(root: Path, task_id: str) -> dict[Path, bytes]:
    paths = [root / "project" / "tasks" / f"{task_id}-task.md"]
    paths.extend(root / path for path in CONTROL_PATHS)
    return {path: path.read_bytes() for path in paths}


def assert_control_snapshot(root: Path, before: dict[Path, bytes]) -> None:
    for path, content in before.items():
        assert path.read_bytes() == content, path
    leftovers = sorted(root.rglob("*.tmp")) + sorted(root.rglob("*.tmp-*"))
    assert leftovers == []


def prepare_transaction_command(root: Path, name: str) -> tuple[list[str], str]:
    if name == "approve":
        return ["make", "task-approve", "TASK=T-002", "APPROVED_BY=Test Human"], "T-002"
    if name == "ready":
        run(["make", "task-complete", "TASK=T-001"], root)
        return ["make", "task-ready", "TASK=T-002"], "T-002"
    if name == "start":
        run(["make", "task-complete", "TASK=T-001"], root)
        run(["make", "task-ready", "TASK=T-002"], root)
        return ["make", "task-start", "TASK=T-002"], "T-002"
    if name == "review":
        return ["make", "task-review", "TASK=T-001"], "T-001"
    if name == "complete":
        return ["make", "task-complete", "TASK=T-001"], "T-001"
    if name == "block":
        return [
            "make",
            "task-block",
            "TASK=T-001",
            "REASON=Waiting",
            "UNBLOCK=Continue",
        ], "T-001"
    if name == "unblock":
        run(
            [
                "make",
                "task-block",
                "TASK=T-001",
                "REASON=Waiting",
                "UNBLOCK=Continue",
            ],
            root,
        )
        return ["make", "task-unblock", "TASK=T-001"], "T-001"
    if name == "cancel":
        return ["make", "task-cancel", "TASK=T-001"], "T-001"
    raise AssertionError(name)


def test_mutating_task_commands_are_transactional_on_failure(tmp_path: Path) -> None:
    failures = {
        "validation": "PROJECT_TOOL_FAIL_VALIDATION",
        "render": "PROJECT_TOOL_FAIL_RENDER",
        "write": "PROJECT_TOOL_FAIL_WRITE",
        "final-validation": "PROJECT_TOOL_FAIL_FINAL_VALIDATE",
    }
    commands = ["approve", "ready", "start", "review", "complete", "block", "unblock", "cancel"]
    for command_name in commands:
        for failure_name, env_name in failures.items():
            root = make_project(tmp_path / f"{command_name}-{failure_name}")
            command, task_id = prepare_transaction_command(root, command_name)
            run(["make", "validate-project"], root)
            before = control_snapshot(root, task_id)
            result = run_with_env(command, root, {env_name: "1"}, expect_success=False)
            output = result.stdout + result.stderr
            assert "ERROR:" in output, (command_name, failure_name, output)
            assert_control_snapshot(root, before)
            run(["make", "validate-project"], root)


def test_failed_approval_does_not_persist_metadata(tmp_path: Path) -> None:
    root = make_project(tmp_path)
    before = control_snapshot(root, "T-002")
    result = run_with_env(
        ["make", "task-approve", "TASK=T-002", "APPROVED_BY=Test Human"],
        root,
        {"PROJECT_TOOL_FAIL_FINAL_VALIDATE": "1"},
        expect_success=False,
    )
    assert "final validation failure" in result.stdout
    assert_control_snapshot(root, before)
    task_text = (root / "project" / "tasks" / "T-002-task.md").read_text()
    assert "approval_status: pending" in task_text
    assert "approved_by: Test Human" not in task_text


def test_project_state_validation_fullstack_profile(tmp_path: Path) -> None:
    root = make_project(tmp_path, profile="fullstack")
    run(["make", "validate-project"], root)
    assert "Project state is valid" in run(["make", "validate-project"], root).stdout


def readme_dashboard(root: Path) -> str:
    text = (root / "README.md").read_text()
    return text.split("<!-- project-status:start -->", 1)[1].split(
        "<!-- project-status:end -->",
        1,
    )[0]


def test_readme_dashboard_next_actions_for_task_states(tmp_path: Path) -> None:
    active = make_project(tmp_path / "active")
    dashboard = readme_dashboard(active)
    assert "| Active task | [T-001]" in dashboard
    assert "| Next action command | `make task-review TASK=T-001` |" in dashboard

    a1_review = make_project(tmp_path / "a1-review")
    run(["make", "task-complete", "TASK=T-001"], a1_review)
    run(["make", "task-ready", "TASK=T-002"], a1_review)
    run(["make", "task-start", "TASK=T-002"], a1_review)
    run(["make", "task-review", "TASK=T-002"], a1_review)
    dashboard = readme_dashboard(a1_review)
    assert "| Waiting | A1 approval pending: T-002 |" in dashboard
    assert '| Next action command | `make task-approve TASK=T-002 APPROVED_BY="<human>"` |' in dashboard

    a2_ready = make_project(tmp_path / "a2-ready")
    run(["make", "task-complete", "TASK=T-001"], a2_ready)
    run(["make", "task-ready", "TASK=T-002"], a2_ready)
    run(["make", "task-start", "TASK=T-002"], a2_ready)
    run(["make", "task-review", "TASK=T-002"], a2_ready)
    run(["make", "task-approve", "TASK=T-002", "APPROVED_BY=Test Human"], a2_ready)
    run(["make", "task-complete", "TASK=T-002"], a2_ready)
    run(["make", "task-ready", "TASK=T-003"], a2_ready)
    dashboard = readme_dashboard(a2_ready)
    assert "| Waiting | A2 approval required before start: T-003 |" in dashboard
    assert '| Next action command | `make task-approve TASK=T-003 APPROVED_BY="<human>"` |' in dashboard

    blocked = make_project(tmp_path / "blocked")
    run(
        [
            "make",
            "task-block",
            "TASK=T-001",
            "REASON=Waiting on input",
            "UNBLOCK=Record the decision",
        ],
        blocked,
    )
    dashboard = readme_dashboard(blocked)
    assert "| Waiting | Blocked: T-001 |" in dashboard
    assert "| Blocker | T-001: Waiting on input |" in dashboard
    assert "| Next action command | `make task-unblock TASK=T-001` |" in dashboard

    no_ready = make_project(tmp_path / "no-ready")
    run(["make", "task-complete", "TASK=T-001"], no_ready)
    dashboard = readme_dashboard(no_ready)
    assert "No ready task exists" in dashboard
    assert "| Next action command | `make task-ready TASK=<new-task-id>` |" in dashboard


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
    ("documented missing command", lambda root: (root / "README.md").write_text((root / "README.md").read_text() + "\n`make missing-target`\n"), "has no Makefile target"),
    ("profile irrelevant FastAPI docs", lambda root: (root / "docs" / "architecture.md").write_text("# Architecture\n\nCurrent architecture: Python CLI package with FastAPI.\n"), "mentions FastAPI"),
    ("unrendered Jinja", lambda root: (root / "docs" / "product.md").write_text("# Product\n\n{{ project_name }}\n"), "unrendered Jinja"),
    (
        "personal path",
        lambda root: (root / "docs" / "product.md").write_text(
            "# Product\n\nSee " + "/" + "home" + "/" + "semtex" + "/project.\n"
        ),
        "personal absolute path",
    ),
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
