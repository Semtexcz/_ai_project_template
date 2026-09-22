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
        "work": {"active_task": None, "blocked": False},
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
        "find_active",
        "definition_of_ready",
        "definition_of_done",
        "dependencies_done",
        "parse_simple_yaml",
        "write_state",
    ]:
        assert hasattr(module, name), name


def test_persisted_and_runtime_views_stay_distinct() -> None:
    rendering = load_module("rendering")
    state = make_state(workflow_mode="pr")
    tasks = [make_task("T-001", status="review", approval_level="A1", approval_status="pending")]

    persisted = rendering.persisted_status_block(state, tasks)
    runtime = rendering.runtime_status_block(state, tasks)
    for row in rendering.GIT_RELATIVE_STATUS_ROWS:
        assert f"| {row} |" not in persisted, row
        assert f"| {row} |" in runtime, row
    assert "| Active task |" in persisted
    assert "| Next gate |" in persisted

    persisted_board = rendering.persisted_board_block(tasks, state)
    runtime_board = rendering.runtime_board_block(tasks, state)
    assert rendering.PR_BOARD_SNAPSHOT_NOTE in persisted_board
    assert rendering.PR_BOARD_SNAPSHOT_NOTE not in runtime_board
    assert "## Review" in persisted_board
    assert "awaiting human GitHub merge" not in persisted_board

    local = make_state()
    assert "| Last completed task |" in rendering.persisted_status_block(local, tasks)


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
