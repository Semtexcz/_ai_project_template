"""Focused tests for the project-governance module seams.

These tests are deliberately cheap and unit-level: they exercise the extracted
seams directly so that a change to Git provenance, dashboard rendering,
documentation validation, or a lifecycle transition rule has a fast
neighborhood that does not require the golden-path suite. End-to-end lifecycle
behavior remains covered by
``tests/test_project_state_validation_golden_path.py``.
"""

from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "template" / "tools"
PACKAGE_DIR = TOOLS_DIR / "project_tool"
CLI_PATH = TOOLS_DIR / "project.py"

# Concept -> owning module. Mirrors the ownership map documented in
# docs/template-development.md; a moved responsibility fails this test.
OWNERSHIP = {
    "model.py": "root layout, task records, status vocabulary",
    "storage.py": "YAML codec, state/task loading, generated block text",
    "git.py": "Git merge provenance",
    "worktrees.py": "Git worktree and branch mechanics",
    "claims.py": "local task claims and worktree ownership resolution",
    "lifecycle.py": "effective status, readiness, dependencies, transition rules",
    "rendering.py": "persisted and runtime dashboard derivation",
    "docs.py": "documentation validation",
    "validation.py": "project and task validation",
    "mutations.py": "explicit multi-file mutation boundary",
    "commands.py": "public command implementations",
}
# Names that would indicate a generic dumping ground instead of a cohesive owner.
FORBIDDEN_MODULES = {"utils.py", "helpers.py", "common.py", "misc.py"}

COMPLETE_BODY = """
## Goal

Ship the task.

## Context

Fixture context for the module seam tests.

## Scope

- Implement the scoped change.

## Out of Scope

- Unrelated work.

## Acceptance Criteria

- [x] Criterion is met.

## Verification

`make validate-project` passed.

## Documentation Impact

Handled.

## Completion Notes

Completed.
"""


def load_module(name: str) -> Any:
    """Import one ``project_tool`` module the way the CLI does."""
    tools = str(TOOLS_DIR)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    return importlib.import_module(f"project_tool.{name}")


def make_task(task_id: str = "T-002", **overrides: Any) -> Any:
    """Build a task record without touching the filesystem."""
    model = load_module("model")
    fields: dict[str, Any] = {
        "id": task_id,
        "title": f"Task {task_id}",
        "status": "ready",
        "priority": 1,
        "milestone": "M-01",
        "depends_on": (),
        "approval_level": "A0",
        "approval_status": "not-required",
        "approved_by": None,
        "approved_at": None,
        "blocked_reason": None,
        "unblock_action": None,
        "path": ROOT / "project" / "tasks" / f"{task_id}-fixture.md",
        "body": COMPLETE_BODY,
    }
    fields.update(overrides)
    return model.Task(**fields)


def make_state(*, workflow_mode: str = "local") -> dict[str, Any]:
    """Build a minimal valid state mapping for rendering/lifecycle seams."""
    return {
        "schema_version": 1,
        "project": {
            "name": "Fixture",
            "type": "script",
            "runtime_level": "local",
            "workflow_mode": workflow_mode,
            "risk": "low",
            "status": "active",
        },
        "lifecycle": {"phase": "delivery", "milestone": "M-01", "next_gate": "fixture-gate"},
        "template": {"version": "v1.1.0"},
    }


def test_cli_stays_a_thin_composition_layer() -> None:
    text = CLI_PATH.read_text(encoding="utf-8")
    assert len(text.splitlines()) <= 250
    assert "def build_parser(" in text
    assert "def dispatch(" in text
    assert "def main()" in text
    # No governance implementation may leak back into the CLI module.
    for marker in [
        "def persisted_status_block",
        "def task_merge_completed",
        "def validate_all",
        "def controlled_transition",
        "class Task",
    ]:
        assert marker not in text, marker


def test_package_layout_matches_the_documented_ownership_map() -> None:
    present = {path.name for path in PACKAGE_DIR.glob("*.py")}
    assert present == {"__init__.py", *OWNERSHIP}
    assert not present & FORBIDDEN_MODULES
    for module in [*OWNERSHIP, "__init__.py"]:
        text = (PACKAGE_DIR / module).read_text(encoding="utf-8")
        assert text.startswith('"""'), module
        assert len(text.splitlines()) <= 500, module


def test_package_imports_without_cycles_and_never_parses_cli_arguments() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import project_tool.commands, project_tool.validation, project_tool.mutations,"
            " project_tool.rendering, project_tool.docs, project_tool.lifecycle,"
            " project_tool.storage, project_tool.git, project_tool.model; print('ok')",
        ],
        cwd=ROOT,
        env={"PYTHONPATH": str(TOOLS_DIR)},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ok" in result.stdout
    for module in [*OWNERSHIP, "__init__.py"]:
        text = (PACKAGE_DIR / module).read_text(encoding="utf-8")
        assert "import argparse" not in text, module


def test_direct_script_and_file_location_loading_both_expose_compat_names() -> None:
    direct = subprocess.run(
        [sys.executable, "tools/project.py", "--help"],
        cwd=ROOT / "template",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert direct.returncode == 0, direct.stdout + direct.stderr
    assert "pr-validate" in direct.stdout

    spec = importlib.util.spec_from_file_location("seam_project_tool", CLI_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    for name in [
        "load_tasks",
        "task_by_id",
        "nonempty",
        "read_state",
        "recommended_next_action",
        "validate_all",
        "validate_candidate",
        "validate_active_claims",
        "active_tasks",
        "available_tasks",
        "claimable_tasks",
        "definition_of_ready",
        "definition_of_done",
        "dependencies_done",
        "parse_simple_yaml",
        "write_state",
        "resolve_owner",
        "ownership_errors",
        "ownership_start_errors",
        "inspect_claims",
        "claim_dicts",
        "release_claim",
        "worktree_states",
        "worktrees_command",
        "create_worktree",
        "remove_worktree_command",
        "release_claim_command",
    ]:
        assert hasattr(module, name), name


def test_persisted_and_runtime_views_stay_distinct() -> None:
    rendering = load_module("rendering")
    state = make_state(workflow_mode="pr")
    tasks = [make_task("T-001", status="review", approval_level="A1", approval_status="pending")]

    persisted = rendering.persisted_status_block(state)
    runtime = rendering.runtime_status_block(state, tasks)
    # Committed rows are project-global only: no task transition can change them,
    # so parallel task branches never conflict in shared Markdown.
    for row in rendering.PERSISTED_STATUS_ROWS:
        assert f"| {row} |" in persisted, row
    for row in rendering.TASK_DERIVED_STATUS_ROWS:
        assert f"| {row} |" not in persisted, row
        assert f"| {row} |" in runtime, row
    assert rendering.persisted_status_block(make_state()) == persisted

    persisted_board = rendering.persisted_board_block(state)
    runtime_board = rendering.runtime_board_block(tasks, state)
    assert rendering.PERSISTED_BOARD_NOTE in persisted_board
    assert rendering.PERSISTED_BOARD_NOTE not in runtime_board
    assert "## Review" not in persisted_board
    assert "## Review" in runtime_board
    assert "awaiting human GitHub merge" not in persisted_board

    local = make_state()
    assert rendering.persisted_status_block(local) == persisted
    assert rendering.runtime_worktree_table(
        [("T-001", "task/T-001-x", "/tmp/T-001", "clean")]
    ) == (
        "| Task | Branch | Worktree | State |\n"
        "|---|---|---|---|\n"
        "| T-001 | task/T-001-x | /tmp/T-001 | clean |"
    )
    assert rendering.runtime_available_block([]) == "Available tasks: none."


def test_lifecycle_transition_rules_are_explicit_and_local() -> None:
    lifecycle = load_module("lifecycle")
    state = make_state()
    ready = make_task("T-002")
    blocked = make_task(
        "T-003", status="blocked", blocked_reason="waiting", unblock_action="fix it"
    )
    tasks = [ready, blocked]
    tasks_by = {task.id: task for task in tasks}

    def blocker(task: Any, new_status: str, **kwargs: Any) -> str | None:
        return lifecycle.transition_blocker(
            task, new_status, tasks=tasks, tasks_by=tasks_by, state=state, **kwargs
        )

    unknown = blocker(ready, "published")
    assert unknown == "Invalid target status published. Use a supported task status."
    assert "Invalid transition: ready -> done" in str(blocker(ready, "done"))

    running = make_task("T-012", status="in-progress")
    tasks.append(running)
    tasks_by[running.id] = running
    assert "Blocking requires REASON and UNBLOCK" in str(blocker(running, "blocked", reason="r"))

    a2 = make_task("T-004", approval_level="A2", approval_status="pending")
    tasks.append(a2)
    tasks_by[a2.id] = a2
    a2_blocker = blocker(a2, "in-progress")
    assert a2_blocker == "Human A2 approval is required for T-004 before work starts."

    incomplete = make_task("T-005", status="backlog", body="## Goal\n\nShip it.\n")
    tasks.append(incomplete)
    tasks_by[incomplete.id] = incomplete
    assert str(blocker(incomplete, "ready")).startswith("T-005 is not ready:")

    dependent = make_task("T-006", status="backlog", depends_on=("T-002",))
    tasks.append(dependent)
    tasks_by[dependent.id] = dependent
    assert "cannot become ready until dependencies are done" in str(blocker(dependent, "ready"))

    review = make_task("T-007", status="review", approval_level="A1", approval_status="pending")
    pr_blocker = lifecycle.transition_blocker(
        review,
        "done",
        tasks=[review],
        tasks_by={review.id: review},
        state=make_state(workflow_mode="pr"),
    )
    assert "human GitHub merge of its pull request is the completion boundary" in str(pr_blocker)


def test_multiple_independent_tasks_may_be_in_progress() -> None:
    """Concurrency is bounded by worktree claims, not by global project state."""
    lifecycle = load_module("lifecycle")
    rendering = load_module("rendering")
    state = make_state()
    first = make_task("T-002", status="in-progress")
    second = make_task("T-003", status="in-progress")
    third = make_task("T-004")
    tasks = [first, second, third]
    tasks_by = {task.id: task for task in tasks}

    # A second in-progress task is no longer a lifecycle violation.
    assert lifecycle.transition_blocker(
        third,
        "in-progress",
        tasks=tasks,
        tasks_by=tasks_by,
        state=state,
    ) is None
    assert [task.id for task in rendering.active_tasks(tasks)] == ["T-002", "T-003"]
    assert rendering.active_task_links(tasks, ROOT) == (
        "[T-002](project/tasks/T-002-fixture.md), [T-003](project/tasks/T-003-fixture.md)"
    )


def test_available_tasks_exposes_every_runnable_task_without_a_global_next() -> None:
    lifecycle = load_module("lifecycle")
    state = make_state()
    ready_one = make_task("T-002")
    ready_two = make_task("T-003")
    waiting = make_task("T-004", status="backlog")
    dependent = make_task("T-005", depends_on=("T-002",))
    a2_pending = make_task("T-006", approval_level="A2", approval_status="pending")
    tasks = [ready_one, ready_two, waiting, dependent, a2_pending]

    assert [task.id for task in lifecycle.available_tasks(tasks, state)] == ["T-002", "T-003"]

    a2_approved = make_task("T-006", approval_level="A2", approval_status="approved")
    assert [task.id for task in lifecycle.available_tasks([*tasks[:-1], a2_approved], state)] == [
        "T-002",
        "T-003",
        "T-006",
    ]


def test_claim_validation_rejects_inconsistent_and_malformed_claims() -> None:
    validation = load_module("validation")
    worktrees = load_module("worktrees")
    tasks = [make_task("T-002"), make_task("T-003")]
    shared = {
        "task_id": "T-002",
        "branch": "task/T-002-fixture",
        "worktree": "/tmp/fixture",
        "pid": 1,
        "created_at": "now",
    }
    other = {**shared, "task_id": "T-003", "branch": "task/T-003-fixture"}

    assert validation.validate_active_claims(tasks, [shared]) == []
    errors = validation.validate_active_claims(tasks, [shared, other])
    assert any("claims multiple tasks" in error for error in errors)
    duplicate = validation.validate_active_claims(tasks, [shared, dict(shared)])
    assert any("has 2 claims" in error for error in duplicate)
    mismatch = validation.validate_active_claims(
        tasks, [{**shared, "branch": "task/T-999-other"}]
    )
    assert any("does not name T-002" in error for error in mismatch)
    malformed = validation.validate_active_claims(tasks, [{**shared, "branch": "", "worktree": ""}])
    assert any("empty branch" in error for error in malformed)
    assert any("empty worktree path" in error for error in malformed)
    registered = validation.validate_active_claims(
        tasks,
        [shared],
        worktrees=[worktrees.WorktreeEntry(path="/tmp/fixture", branch="task/T-002-fixture")],
    )
    assert registered == []
    unregistered = validation.validate_active_claims(
        tasks,
        [shared],
        worktrees=[worktrees.WorktreeEntry(path="/tmp/elsewhere", branch="task/T-002-fixture")],
    )
    assert any("not registered" in error for error in unregistered)


def test_claimable_tasks_exclude_locally_claimed_runnable_tasks() -> None:
    commands = load_module("commands")
    state = make_state()
    first = make_task("T-002")
    second = make_task("T-003")
    claims = [{"task_id": "T-003", "branch": "task/T-003-fixture", "worktree": "/tmp/t3"}]

    assert [task.id for task in commands.claimable_tasks([first, second], state, claims)] == ["T-002"]


def test_worktree_mechanics_naming_and_claims_are_deterministic(tmp_path: Path) -> None:
    worktrees = load_module("worktrees")
    claims = load_module("claims")

    assert worktrees.task_branch_name("T-101", "Add the API endpoint") == (
        "task/T-101-add-the-api-endpoint"
    )
    assert worktrees.task_id_from_branch("feat/T-101-api") == "T-101"
    assert worktrees.task_id_from_branch("main") is None
    assert worktrees.slugify("!!") == "task"

    claim = claims.TaskClaim(
        task_id="T-101",
        branch="task/T-101-x",
        worktree=str(tmp_path),
        pid=1,
        created_at="2026-01-01T00:00:00+00:00",
    )
    payload = claim.as_dict()
    assert payload["task_id"] == "T-101"
    assert claims.claim_from_payload(payload, tmp_path / "T-101.json") == claim

    model = load_module("model")
    with pytest.raises(model.ProjectError):
        claims.claim_from_payload({"task_id": "T-101"}, tmp_path / "T-101.json")


def test_approval_and_readiness_decisions_are_unit_testable() -> None:
    lifecycle = load_module("lifecycle")
    pr_state = make_state(workflow_mode="pr")
    a0 = make_task("T-008")
    a1 = make_task("T-009", approval_level="A1", approval_status="pending")
    a2 = make_task("T-010", approval_level="A2", approval_status="pending")

    assert lifecycle.approval_blocker(a0, pr_state) == "T-008 is A0 and does not require approval."
    assert "only A1" in str(lifecycle.approval_blocker(a1, pr_state))
    assert lifecycle.approval_blocker(a2, pr_state) is None
    assert lifecycle.definition_of_ready(make_task("T-011")) == []
    assert lifecycle.definition_of_done(make_task("T-011")) == []
    assert lifecycle.valid_datetime("2026-07-31T10:00:00+02:00")
    assert not lifecycle.valid_datetime("not-a-date")


def test_documentation_validation_seams_run_without_the_full_lifecycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    docs = load_module("docs")
    readme = tmp_path / "README.md"
    readme.write_text("# Fixture\n\nRun `make missing-target` now.\n", encoding="utf-8")
    (tmp_path / "Makefile").write_text("validate-project:\n\t@true\n", encoding="utf-8")
    monkeypatch.setattr(docs, "ROOT", tmp_path)

    errors = docs.validate_documented_make_commands()
    assert any("has no Makefile target" in error for error in errors)

    readme.write_text(
        "# Fixture\n\nRun `make validate-project` from the maintainer machine.\n",
        encoding="utf-8",
    )
    assert docs.validate_doc_text_hygiene() == []
    readme.write_text("# Fixture\n\nUnrendered {{ placeholder }} here.\n", encoding="utf-8")
    hygiene = docs.validate_doc_text_hygiene()
    assert any("unrendered Jinja placeholder" in error for error in hygiene)
