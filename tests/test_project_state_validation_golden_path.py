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


def make_project(tmp_path: Path, *, profile: str = "script", workflow_mode: str = "") -> Path:
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
    # Rendered managed projects receive the whole governance package, so the
    # fixture mirrors the real tools/ layout instead of the CLI file alone.
    shutil.copytree(
        ROOT / "template" / "tools" / "project_tool",
        root / "tools" / "project_tool",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
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
                "pr-validate:",
                "\tPYTHONDONTWRITEBYTECODE=1 python tools/project.py pr-validate",
                "",
            ]
        )
    )
    workflow_line = f"  workflow_mode: {workflow_mode}\n" if workflow_mode else ""
    (root / "project" / "state.yaml").write_text(
        f"""schema_version: 1

project:
  name: Test Project
  type: {profile}
  runtime_level: local
  risk: medium
  status: active
{workflow_line}
lifecycle:
  phase: delivery
  milestone: M-01
  next_gate: project-state-validation-complete

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


def test_dashboard_rendering_failure_is_reported_without_partial_writes(tmp_path: Path) -> None:
    """Rendering now belongs to synchronization, not to task transitions."""
    root = make_project(tmp_path / "sync-render")
    before = {path: (root / path).read_bytes() for path in CONTROL_PATHS}
    result = run_with_env(
        ["make", "sync-project-docs"],
        root,
        {"PROJECT_TOOL_FAIL_RENDER": "1"},
        expect_success=False,
    )
    assert "Injected dashboard rendering failure" in result.stdout
    for path, content in before.items():
        assert (root / path).read_bytes() == content, path

    # A task transition does not render at all, so the same injection is a no-op.
    run(["make", "task-complete", "TASK=T-001"], root)
    run_with_env(
        ["make", "task-ready", "TASK=T-002"],
        root,
        {"PROJECT_TOOL_FAIL_RENDER": "1"},
    )
    assert "status: ready" in (root / "project" / "tasks" / "T-002-task.md").read_text()


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


def runtime_status(root: Path) -> str:
    """Return the live status view: task-derived rows are rendered at read time."""
    return run([sys.executable, "tools/project.py", "status"], root).stdout


def test_runtime_status_next_actions_for_task_states(tmp_path: Path) -> None:
    active = make_project(tmp_path / "active")
    status = runtime_status(active)
    assert "| Active task | [T-001]" in status
    assert "| Next action command | `make task-review TASK=T-001` |" in status

    a1_review = make_project(tmp_path / "a1-review")
    run(["make", "task-complete", "TASK=T-001"], a1_review)
    run(["make", "task-ready", "TASK=T-002"], a1_review)
    run(["make", "task-start", "TASK=T-002"], a1_review)
    run(["make", "task-review", "TASK=T-002"], a1_review)
    status = runtime_status(a1_review)
    assert "| Waiting | A1 approval pending: T-002 |" in status
    assert '| Next action command | `make task-approve TASK=T-002 APPROVED_BY="<human>"` |' in status

    a2_ready = make_project(tmp_path / "a2-ready")
    run(["make", "task-complete", "TASK=T-001"], a2_ready)
    run(["make", "task-ready", "TASK=T-002"], a2_ready)
    run(["make", "task-start", "TASK=T-002"], a2_ready)
    run(["make", "task-review", "TASK=T-002"], a2_ready)
    run(["make", "task-approve", "TASK=T-002", "APPROVED_BY=Test Human"], a2_ready)
    run(["make", "task-complete", "TASK=T-002"], a2_ready)
    run(["make", "task-ready", "TASK=T-003"], a2_ready)
    status = runtime_status(a2_ready)
    assert "| Waiting | A2 approval required before start: T-003 |" in status
    assert '| Next action command | `make task-approve TASK=T-003 APPROVED_BY="<human>"` |' in status

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
    status = runtime_status(blocked)
    assert "| Waiting | Blocked: T-001 |" in status
    assert "| Blocker | T-001: Waiting on input |" in status
    assert "| Next action command | `make task-unblock TASK=T-001` |" in status

    no_ready = make_project(tmp_path / "no-ready")
    run(["make", "task-complete", "TASK=T-001"], no_ready)
    status = runtime_status(no_ready)
    assert "No ready task exists" in status
    assert "| Next action command | `make task-ready TASK=<new-task-id>` |" in status

    # Committed Markdown carries only project-global rows and never changes with
    # a task transition, so parallel branches cannot conflict there.
    for root in [active, a1_review, a2_ready, blocked, no_ready]:
        committed = readme_dashboard(root)
        for row in TASK_DERIVED_STATUS_ROWS:
            assert f"| {row} |" not in committed, (root, row)


def set_task(root: Path, task_id: str, old: str, new: str) -> None:
    path = root / "project" / "tasks" / f"{task_id}-task.md"
    path.write_text(path.read_text().replace(old, new))


NEGATIVE_CASES: list[tuple[str, Callable[[Path], None], str]] = [
    (
        "blocked without metadata",
        lambda root: set_task(root, "T-001", "status: in-progress", "status: blocked"),
        "blocked task requires",
    ),
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
    ("started dependent task", lambda root: set_task(root, "T-002", "status: backlog", "status: in-progress"), "dependencies are not done"),
    ("missing Definition of Ready", lambda root: write_task(root, "T-001", status="in-progress", include_ready=False), "Definition of Ready"),
    ("done unchecked criterion", lambda root: write_task(root, "T-001", status="done", checked=False), "all Acceptance Criteria"),
    ("done missing completion notes", lambda root: write_task(root, "T-001", status="done", completion_notes=""), "Completion Notes"),
    ("A1 done without approval", lambda root: write_task(root, "T-001", status="done", approval_level="A1", approval_status="pending"), "A1 task cannot be done"),
    ("A2 started without approval", lambda root: write_task(root, "T-001", status="in-progress", approval_level="A2", approval_status="pending"), "A2 task cannot start"),
    ("blocked without reason", lambda root: write_task(root, "T-001", status="blocked", blocked_reason="", unblock_action=""), "blocked task requires"),
    ("stale README", lambda root: (root / "README.md").write_text((root / "README.md").read_text().replace("Project type", "Project kind")), "README.md generated block is stale"),
    ("stale project index", lambda root: (root / "project" / "index.md").write_text((root / "project" / "index.md").read_text().replace("| Milestone |", "| Iteration |")), "project/index.md generated block is stale"),
    ("stale board", lambda root: (root / "project" / "board.md").write_text((root / "project" / "board.md").read_text().replace("rendered at read time", "persisted")), "project/board.md generated block is stale"),
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


def test_two_independent_tasks_may_be_in_progress_together(tmp_path: Path) -> None:
    """Project-global state no longer allows exactly one active task."""
    root = make_project(tmp_path / "parallel")
    write_task(root, "T-002", status="in-progress")
    run(["make", "sync-project-docs"], root)
    run([sys.executable, "tools/project.py", "validate"], root)

    status = run(["make", "project-status"], root).stdout
    in_progress = status.split("## In Progress", 1)[1].split("## Review", 1)[0]
    assert "T-001" in in_progress and "T-002" in in_progress
    active_row = next(line for line in status.splitlines() if line.startswith("| Active task |"))
    assert "[T-001](project/tasks/T-001-task.md)" in active_row
    assert "[T-002](project/tasks/T-002-task.md)" in active_row
    state = (root / "project" / "state.yaml").read_text()
    assert "active_task" not in state
    assert "T-002" not in readme_dashboard(root)


def test_legacy_work_section_in_state_is_tolerated(tmp_path: Path) -> None:
    """State written before T-031 keeps validating; ownership lives elsewhere now."""
    root = make_project(tmp_path / "legacy")
    state_path = root / "project" / "state.yaml"
    state_path.write_text(
        state_path.read_text().replace(
            "template:",
            "work:\n  active_task: T-999\n  blocked: true\n\ntemplate:",
        )
    )
    run([sys.executable, "tools/project.py", "validate"], root)
    assert "make sync-project-docs" not in run(
        [sys.executable, "tools/project.py", "validate"], root
    ).stdout


GIT_RELATIVE_TEXT_MARKERS = (
    "awaiting human GitHub merge",
    "completed by merged Git provenance",
)
TASK_DERIVED_STATUS_ROWS = (
    "Last completed task",
    "Active task",
    "Approval",
    "Waiting",
    "Blocker",
    "Recommended next action",
    "Next action command",
)


def committed_block_text(root: Path) -> str:
    return "\n".join(
        (root / path).read_text()
        for path in ["README.md", "project/index.md", "project/board.md"]
    )


def git_commit(root: Path, message: str) -> None:
    run(["git", "add", "-A"], root)
    run(
        [
            "git",
            "-c",
            "user.name=Test Human",
            "-c",
            "user.email=human@example.com",
            "commit",
            "-q",
            "-m",
            message,
        ],
        root,
    )


def git_porcelain(root: Path) -> str:
    return run(["git", "status", "--porcelain"], root).stdout


def test_github_pr_a1_merge_lifecycle_needs_no_cleanup(tmp_path: Path) -> None:
    """A merged review record completes with no file mutation anywhere."""
    root = make_project(tmp_path / "pr-a1", workflow_mode="pr")
    write_task(root, "T-003", depends_on="[T-002]")
    run(["git", "init", "-b", "main"], root)
    git_commit(root, "base")
    run(["git", "checkout", "-q", "-b", "feat/T-002-greeting"], root)
    run(["make", "task-complete", "TASK=T-001"], root)
    run(["make", "task-ready", "TASK=T-002"], root)
    run(["make", "task-start", "TASK=T-002"], root)
    run(["make", "task-review", "TASK=T-002"], root)

    # Before the merge the committed view is deterministic and task-free: it can
    # never claim a merge outcome that does not exist yet.
    board = (root / "project" / "board.md").read_text()
    assert "make project-status" in board
    assert "## Review" not in board
    committed = committed_block_text(root)
    for marker in GIT_RELATIVE_TEXT_MARKERS:
        assert marker not in committed
    for row in TASK_DERIVED_STATUS_ROWS:
        assert f"| {row} |" not in readme_dashboard(root)

    # The runtime view is the one that reports the review state and the merge wait.
    status = run(["make", "project-status"], root).stdout
    assert "T-002" in status.split("## Review", 1)[1].split("## Blocked", 1)[0]
    assert "Awaiting human GitHub merge: T-002" in status
    assert "Last completed task | [T-001]" in status
    assert "`make project-status` (await human GitHub merge of T-002)." in status
    result = run(["make", "task-ready", "TASK=T-003"], root, expect_success=False)
    assert "dependencies are done" in result.stdout
    result = run(["make", "task-start", "TASK=T-003"], root, expect_success=False)
    assert "Invalid transition" in result.stdout

    run_with_env(
        ["make", "pr-validate"],
        root,
        {"PR_HEAD_REF": "feat/T-002-greeting", "PR_TITLE": "T-002: Add greeting", "PR_BODY": ""},
    )
    git_commit(root, "review-ready state")
    merged_record = (root / "project" / "tasks" / "T-002-task.md").read_bytes()
    run(["git", "checkout", "-q", "main"], root)
    run(
        [
            "git",
            "-c",
            "user.name=Test Human",
            "-c",
            "user.email=human@example.com",
            "merge",
            "--no-ff",
            "-q",
            "-m",
            "unrelated wording",
            "feat/T-002-greeting",
        ],
        root,
    )

    # After the merge nothing is reconciled: no tracked file changes and
    # validation and synchronization stay clean and idempotent.
    assert git_porcelain(root) == ""
    run(["make", "validate-project"], root)
    run(["make", "sync-project-docs"], root)
    assert git_porcelain(root) == ""
    assert committed_block_text(root) == committed
    assert (root / "project" / "tasks" / "T-002-task.md").read_bytes() == merged_record
    assert "status: review" in (root / "project" / "tasks" / "T-002-task.md").read_text()

    # Runtime status, dependency resolution, and next-task logic are truthful.
    status = run(["make", "project-status"], root).stdout
    assert "Last completed task | [T-002]" in status
    assert "Awaiting human GitHub merge: T-002" not in status
    assert "T-002" in status.split("## Done", 1)[1].split("## Cancelled", 1)[0]
    assert "completed by merged Git provenance" in status
    run(["make", "task-ready", "TASK=T-003"], root)
    run(["make", "task-start", "TASK=T-003"], root)
    run(["make", "validate-project"], root)


def test_pr_mode_committed_blocks_stay_deterministic(tmp_path: Path) -> None:
    """Drift is still real drift, and task-derived rows can never be committed."""
    root = make_project(tmp_path / "pr-committed", workflow_mode="pr")
    readme_path = root / "README.md"
    original = readme_path.read_text()

    readme_path.write_text(original.replace("| Phase | delivery |", "| Phase | operation |"))
    result = run(["make", "validate-project"], root, expect_success=False)
    assert "README.md generated block is stale" in result.stdout

    readme_path.write_text(
        original.replace("| Next gate |", "| Waiting | None |\n| Next gate |")
    )
    result = run(["make", "validate-project"], root, expect_success=False)
    assert "must not persist the task-derived row 'Waiting'" in result.stdout


def test_task_merge_completed_is_merge_strategy_independent(tmp_path: Path) -> None:
    for strategy in ["merge", "squash", "fast-forward"]:
        root = make_project(tmp_path / strategy, workflow_mode="pr")
        run(["git", "init", "-b", "main"], root)
        run(["git", "add", "-A"], root)
        run(["git", "-c", "user.name=Test Human", "-c", "user.email=human@example.com", "commit", "-q", "-m", "base"], root)
        run(["git", "checkout", "-q", "-b", "feat/T-002"], root)
        run(["make", "task-complete", "TASK=T-001"], root)
        run(["make", "task-ready", "TASK=T-002"], root)
        run(["make", "task-start", "TASK=T-002"], root)
        run(["make", "task-review", "TASK=T-002"], root)
        run(["make", "sync-project-docs"], root)
        run(["git", "add", "-A"], root)
        run(["git", "-c", "user.name=Test Human", "-c", "user.email=human@example.com", "commit", "-q", "-m", "review-ready state"], root)
        run(["git", "checkout", "-q", "main"], root)
        if strategy == "merge":
            run(
                [
                    "git",
                    "-c",
                    "user.name=Test Human",
                    "-c",
                    "user.email=human@example.com",
                    "merge",
                    "--no-ff",
                    "-q",
                    "-m",
                    "not parsed",
                    "feat/T-002",
                ],
                root,
            )
        elif strategy == "squash":
            run(["git", "merge", "--squash", "-q", "feat/T-002"], root)
            run(["git", "-c", "user.name=Test Human", "-c", "user.email=human@example.com", "commit", "-q", "-m", "not parsed"], root)
        else:
            run(["git", "merge", "--ff-only", "-q", "feat/T-002"], root)
        status = run(["make", "project-status"], root).stdout
        assert "Last completed task | [T-002]" in status
        assert "completed by merged Git provenance" in status
        assert "Awaiting human GitHub merge: T-002" not in status
        run(["make", "validate-project"], root)
        assert git_porcelain(root) == ""
        run(["make", "sync-project-docs"], root)
        assert git_porcelain(root) == ""
        run(["make", "task-ready", "TASK=T-003"], root)


def test_github_pr_agent_cannot_manufacture_a1_approval(tmp_path: Path) -> None:
    root = make_project(tmp_path / "pr-self-approve", workflow_mode="pr")
    run(["make", "task-complete", "TASK=T-001"], root)
    run(["make", "task-ready", "TASK=T-002"], root)
    run(["make", "task-start", "TASK=T-002"], root)
    run(["make", "task-review", "TASK=T-002"], root)

    task_path = root / "project" / "tasks" / "T-002-task.md"
    text = task_path.read_text(encoding="utf-8")
    text = text.replace("approval_status: pending", "approval_status: approved")
    text = text.replace(
        "approved_by:\n", "approved_by: Test Human\napproved_at: 2026-01-01T10:00:00+00:00\n"
    )
    task_path.write_text(text, encoding="utf-8")

    result = run(["make", "validate-project"], root, expect_success=False)
    assert "A1 approval cannot be recorded locally in workflow_mode=pr" in result.stdout
    result = run_with_env(
        ["make", "pr-validate"],
        root,
        {
            "PR_HEAD_REF": "feat/T-002-greeting",
            "PR_TITLE": "T-002: Add greeting",
            "PR_BODY": "",
        },
        expect_success=False,
    )
    assert "must not record local A1 approval" in result.stdout

def test_github_pr_a2_keeps_stronger_prestart_boundary(tmp_path: Path) -> None:
    root = make_project(tmp_path / "pr-a2", workflow_mode="pr")
    run(["make", "task-complete", "TASK=T-001"], root)
    write_task(
        root,
        "T-004",
        depends_on="[]",
        approval_level="A2",
        approval_status="pending",
    )
    run(["make", "sync-project-docs"], root)
    run(["make", "task-ready", "TASK=T-004"], root)
    result = run(["make", "task-start", "TASK=T-004"], root, expect_success=False)
    assert "Human A2 approval is required" in result.stdout
    # A2 pre-start approval stays available even in pr mode.
    run(["make", "task-approve", "TASK=T-004", "APPROVED_BY=Test Human"], root)
    run(["make", "task-start", "TASK=T-004"], root)
    run(["make", "task-review", "TASK=T-004"], root)
    result = run(["make", "task-complete", "TASK=T-004"], root, expect_success=False)
    assert "GitHub merge" in result.stdout
    run_with_env(
        ["make", "pr-validate"],
        root,
        {
            "PR_HEAD_REF": "feat/T-004-audit",
            "PR_TITLE": "T-004: Audit",
            "PR_BODY": "T-004 implementation.",
        },
    )
    run(["make", "sync-project-docs"], root)
    status = run(["make", "project-status"], root).stdout
    assert "T-004" in status.split("## Review", 1)[1].split("## Blocked", 1)[0]
    run(["make", "validate-project"], root)


def test_pr_validate_requires_deterministic_association(tmp_path: Path) -> None:
    root = make_project(tmp_path / "pr-association", workflow_mode="pr")
    run(["make", "task-complete", "TASK=T-001"], root)
    run(["make", "task-ready", "TASK=T-002"], root)
    run(["make", "task-start", "TASK=T-002"], root)
    run(["make", "task-review", "TASK=T-002"], root)

    result = run_with_env(["make", "pr-validate"], root, {}, expect_success=False)
    assert "PR association is missing" in result.stdout
    result = run_with_env(
        ["make", "pr-validate"],
        root,
        {
            "PR_HEAD_REF": "feat/T-002-x",
            "PR_TITLE": "T-002 and T-003 work",
            "PR_BODY": "",
        },
        expect_success=False,
    )
    assert "references multiple task ids" in result.stdout
    result = run_with_env(
        ["make", "pr-validate"],
        root,
        {
            "PR_HEAD_REF": "feat/T-999-x",
            "PR_TITLE": "T-999: Missing",
            "PR_BODY": "",
        },
        expect_success=False,
    )
    assert "no such task exists" in result.stdout
    result = run_with_env(
        ["make", "pr-validate"],
        root,
        {
            "PR_HEAD_REF": "feat/T-003-x",
            "PR_TITLE": "T-003: Not reviewed",
            "PR_BODY": "",
        },
        expect_success=False,
    )
    assert "must be in review" in result.stdout


def test_offline_local_a1_approval_fallback_still_supported(tmp_path: Path) -> None:
    root = make_project(tmp_path / "local-fallback")
    run(["make", "task-complete", "TASK=T-001"], root)
    run(["make", "task-ready", "TASK=T-002"], root)
    run(["make", "task-start", "TASK=T-002"], root)
    run(["make", "task-review", "TASK=T-002"], root)
    # Local approval is still required before completion in the offline path.
    result = run(["make", "task-complete", "TASK=T-002"], root, expect_success=False)
    assert "Human A1 approval is required" in result.stdout
    run(["make", "task-approve", "TASK=T-002", "APPROVED_BY=Test Human"], root)
    run(["make", "task-complete", "TASK=T-002"], root)
    run(["make", "validate-project"], root)
    task_text = (root / "project" / "tasks" / "T-002-task.md").read_text()
    assert "status: done" in task_text
    assert "approval_status: approved" in task_text
    assert "approved_by: Test Human" in task_text


def test_historical_done_approval_metadata_remains_valid(tmp_path: Path) -> None:
    for label, workflow_mode in [("local", ""), ("pr", "pr")]:
        root = make_project(tmp_path / label, workflow_mode=workflow_mode)
        write_task(
            root,
            "T-004",
            status="done",
            depends_on="[]",
            approval_level="A1",
            approval_status="approved",
            approved_by="Project owner",
            approved_at="2026-01-01T10:00:00+00:00",
        )
        run(["make", "sync-project-docs"], root)
        run(["make", "validate-project"], root)

