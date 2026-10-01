"""Multi-session template-authoring golden path for validation boundaries.

This is the deterministic end-to-end proof for issue #29. It runs the real
generated tooling inside a throwaway managed project and proves that template
authoring separates three validation boundaries:

* Level 1 - focused, change-aware implementation checks;
* Level 2 - exactly one canonical local pre-review gate per review cycle;
* Level 3 - exhaustive validation that CI runs after the push.

The workflow spans several fresh processes (implementation, focused resume, CI
repair). Nothing is carried in memory or persisted: every session derives the
durable task, branch, worktree, claim, and pull-request association from
repository state plus explicit CI failure evidence. No GitHub connection is
required; the exhaustive CI step is a deterministic repository-side proxy (a
fixture contract that is deliberately outside the local ``make check`` subset).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "T-002"
BRANCH = f"task/{TASK_ID}-multi-session"
# Representative cross-cutting change size: the branch must exceed the "30+
# changed files can resume with a small working set" bar.
AREA_COUNT = 10
# A normal handoff is bounded at 8 kB.
HANDOFF_BYTE_BOUND = 8192
# The focused resume working set must stay small and cheap.
FOCUSED_FILE_BOUND = 8
FOCUSED_BYTE_BOUND = 40000

TASK_TEMPLATE = """---
id: {task_id}
title: Add a greeting feature across the managed surfaces
status: in-progress
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

# {task_id}: Add a Greeting Feature Across the Managed Surfaces

## Goal

Introduce a small greeting feature and its focused test as a representative
cross-cutting change.

## Context

Multi-session validation-boundary fixture.

## Scope

- Add the greeting feature and focused coverage.

## Out of Scope

- Unrelated work.

## Acceptance Criteria

- [ ] The greeting feature is implemented and covered.

## Verification

`make check` pending.

## Documentation Impact

Handled by the fixture.

## Completion Notes

Pending.
"""

EXHAUSTIVE_CONTRACT = '''"""Exhaustive-only public API contract check used as the CI proxy.

The fast local `make check` gate runs pytest over `tests/` and never loads this
module, so a change that satisfies the focused test can still fail here. The
exhaustive template CI runs additional contract checks like this one.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    module = importlib.import_module("{package}")
    if not hasattr(module, "build_greeting"):
        print("exhaustive contract failed: the package must re-export build_greeting")
        return 1
    print("exhaustive contract satisfied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


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


def git(command: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(
        [
            "git",
            "-c",
            "user.name=Multi Session Test",
            "-c",
            "user.email=multi-session@example.com",
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
            f"project_name=Multi Session {name}",
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


@pytest.fixture(scope="module")
def managed_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return copy_project(tmp_path_factory.mktemp("multi-session"), "managed-script")


def env_for(tmp_path: Path) -> dict[str, str]:
    return {
        **os.environ,
        "UV_LINK_MODE": "copy",
        "UV_CACHE_DIR": str(tmp_path / "uv-cache"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def package_name(root: Path) -> str:
    return next(path.name for path in sorted((root / "src").iterdir()) if path.is_dir())


def parse_payload(stdout: str) -> dict[str, Any]:
    payload, _ = json.JSONDecoder().raw_decode(stdout[stdout.index("{") :])
    assert isinstance(payload, dict)
    return payload


def agent_json(root: Path, env: dict[str, str], *args: str) -> dict[str, Any]:
    result = run([sys.executable, "tools/agent.py", *args], root, env=env)
    return parse_payload(result.stdout)

def prepare(source: Path, tmp_path: Path, name: str) -> tuple[Path, dict[str, str]]:
    """Build a realistic managed task worktree with a claim, ready to implement."""
    root = tmp_path / name
    shutil.copytree(source, root)
    env = env_for(tmp_path)
    package = package_name(root)

    # Close the generated seed task so this fixture begins from a single active
    # task, then reset the deterministic dashboards.
    run(["make", "setup"], root, env=env)
    run(["make", "task-cancel", "TASK=T-001"], root, env=env)
    run(["make", "sync-project-docs"], root, env=env)

    git(["init", "-b", "main"], root)
    git(["add", "-A"], root)
    git(["commit", "-q", "-m", "chore: baseline"], root)

    # The exhaustive CI proxy lives on the base commit, outside the local gate:
    # `make check` collects only `tests/` and pyright includes only src/tests/tools.
    ci_dir = root / "ci"
    ci_dir.mkdir()
    (ci_dir / "exhaustive_contract.py").write_text(
        EXHAUSTIVE_CONTRACT.format(package=package), encoding="utf-8"
    )
    git(["add", "-A"], root)
    git(["commit", "-q", "-m", "chore: add exhaustive CI proxy"], root)

    git(["checkout", "-q", "-b", BRANCH], root)
    task_path = root / "project" / "tasks" / f"{TASK_ID}-multi-session.md"
    task_path.write_text(TASK_TEMPLATE.format(task_id=TASK_ID), encoding="utf-8")
    git(["add", "-A"], root)
    git(["commit", "-q", "-m", "chore: add fixture task"], root)

    claim = (
        "from pathlib import Path\n"
        "from project_tool import claims\n"
        f"claims.create_claim({TASK_ID!r}, {BRANCH!r}, Path.cwd())\n"
    )
    run([sys.executable, "-c", claim], root, env={**env, "PYTHONPATH": str(root / "tools")})
    return root, env


def write_cross_cutting_change(root: Path) -> tuple[list[str], list[str]]:
    """Write a representative cross-cutting change.

    Returns ``(all_changed_files, focused_files)``. The focused working set is the
    feature module and its focused test; everything else is branch scope.
    """
    package = package_name(root)
    src = root / "src" / package
    tools = root / "tools"
    tests = root / "tests"
    changed: list[str] = []
    for index in range(AREA_COUNT):
        area = src / f"area_{index:02d}.py"
        area.write_text(
            f'"""Area {index:02d}."""\n\n\ndef value_{index:02d}() -> int:\n    return {index}\n',
            encoding="utf-8",
        )
        changed.append(area)
        tool = tools / f"tool_{index:02d}.py"
        tool.write_text(
            f'"""Maintainer helper {index:02d}."""\n\n\ndef helper_{index:02d}() -> int:\n'
            f"    return {index}\n",
            encoding="utf-8",
        )
        changed.append(tool)
        area_test = tests / f"test_area_{index:02d}.py"
        area_test.write_text(
            f"from {package}.area_{index:02d} import value_{index:02d}\n\n\n"
            "def test_value() -> None:\n"
            f"    assert value_{index:02d}() == {index}\n",
            encoding="utf-8",
        )
        changed.append(area_test)

    feature = src / "greeting.py"
    feature.write_text(
        '"""Greeting feature introduced by the task."""\n\n\n'
        "def build_greeting(name: str) -> str:\n"
        '    return f"Hello, {name}!"\n',
        encoding="utf-8",
    )
    focused_test = tests / "test_greeting.py"
    focused_test.write_text(
        f"from {package}.greeting import build_greeting\n\n\n"
        "def test_build_greeting() -> None:\n"
        '    assert build_greeting("Ada") == "Hello, Ada!"\n',
        encoding="utf-8",
    )
    changed.extend([feature, focused_test])
    focused = sorted(path.relative_to(root).as_posix() for path in (feature, focused_test))
    return (
        [path.relative_to(root).as_posix() for path in changed],
        focused,
    )

def test_multi_session_validation_and_ci_boundaries(tmp_path: Path, managed_project: Path) -> None:
    root, env = prepare(managed_project, tmp_path, "workflow")
    state_yaml = root / "project" / "state.yaml"

    # Deterministic repository-side observations for this golden path. They live
    # only in the test and are never written to project state.
    metrics = {
        "focused_check_invocations": 0,
        "local_pre_review_invocations": 0,
        "exhaustive_ci_invocations": 0,
        "manual_full_gate_invocations": 0,
    }

    def focused_checks() -> None:
        """Level 1: run only the focused, change-aware implementation check."""
        metrics["focused_check_invocations"] += 1
        run(["uv", "run", "pytest", focused_test], root, env=env)

    def local_pre_review() -> None:
        """Level 2: the single canonical local gate for this review cycle."""
        metrics["local_pre_review_invocations"] += 1
        run(["make", "agent-pre-review", f"TASK={TASK_ID}"], root, env=env)

    def exhaustive_ci(expect_success: bool) -> subprocess.CompletedProcess[str]:
        """Level 3: a deterministic proxy for exhaustive, asynchronous CI."""
        metrics["exhaustive_ci_invocations"] += 1
        return run(
            ["uv", "run", "python", "ci/exhaustive_contract.py"],
            root,
            env=env,
            expect_success=expect_success,
        )

    # ------------------------------------------------------------------ Phase A
    # Implementation session: a representative cross-cutting change, then only the
    # focused implementation checks. No `make check`, no `release-check`.
    _, focused = write_cross_cutting_change(root)
    focused_test = next(path for path in focused if path.endswith("test_greeting.py"))
    feature_path = next(path for path in focused if path.endswith("greeting.py"))
    focused_checks()

    handoff_a = agent_json(root, env, "handoff", "--task", TASK_ID, "--format", "json")
    assert handoff_a["task"]["id"] == TASK_ID
    assert handoff_a["metrics"]["handoff_bytes"] <= HANDOFF_BYTE_BOUND
    assert handoff_a["worktree"]["branch"] == BRANCH
    assert handoff_a["worktree"]["claimed"] is True
    identity_a = (
        handoff_a["task"]["id"],
        handoff_a["worktree"]["branch"],
        handoff_a["worktree"]["path"],
        handoff_a["worktree"]["claim_task_id"],
    )
    # The implementation session ends here: no in-memory state is carried on.

    # ------------------------------------------------------------------ Phase B
    # Fresh resume session in a new process: recover the same durable identity
    # from repository state and resume with a small, explicit working set.
    handoff_b = agent_json(root, env, "handoff", "--task", TASK_ID, "--format", "json")
    assert (
        handoff_b["task"]["id"],
        handoff_b["worktree"]["branch"],
        handoff_b["worktree"]["path"],
        handoff_b["worktree"]["claim_task_id"],
    ) == identity_a

    resume = agent_json(
        root,
        env,
        "context",
        "--task",
        TASK_ID,
        "--mode",
        "resume",
        "--format",
        "json",
        "--focus",
        *focused,
    )
    branch_changed = resume["changed_files"]
    assert isinstance(branch_changed, list)
    assert len(branch_changed) >= 30
    assert resume["focused_loaded_files"] == focused
    assert resume["metrics"]["focused_loaded_files_count"] <= FOCUSED_FILE_BOUND
    assert resume["total_bytes"] <= FOCUSED_BYTE_BOUND
    # The complete branch stays visible even though only the focus is eager.
    assert set(focused) <= set(branch_changed)
    assert set(branch_changed) - set(focused)

    focused_checks()
    local_pre_review()
    run(["make", "task-review", f"TASK={TASK_ID}"], root, env=env)

    # ------------------------------------------------------------------ Phase C
    # PR boundary: deterministic structural validation, no GitHub connection.
    pr_env = {
        **env,
        "PR_HEAD_REF": BRANCH,
        "PR_TITLE": f"{TASK_ID}: multi-session validation boundaries",
        "PR_BODY": "",
    }
    task_file = root / "project" / "tasks" / f"{TASK_ID}-multi-session.md"
    run(["make", "pr-validate"], root, env=pr_env)
    reviewed = task_file.read_text(encoding="utf-8")
    assert "status: review" in reviewed
    assert "approval_status: pending" in reviewed
    # The implementation session stops at "PR ready and pushed".

    # ------------------------------------------- Simulated asynchronous CI failure
    # The exhaustive CI may discover something the local pre-review gate did not.
    ci_failure = exhaustive_ci(expect_success=False)
    ci_evidence = (ci_failure.stdout + ci_failure.stderr).strip()
    assert "exhaustive contract failed" in ci_evidence
    assert "build_greeting" in ci_evidence
    assert metrics["local_pre_review_invocations"] == 1
    # No CI polling and no session/CI state: the failure is external evidence.

    # ------------------------------------------------------------------ Phase D
    # Fresh CI-repair session: same task/branch/worktree/claim/PR, review ->
    # in-progress through the existing controlled lifecycle (no `ci-failed` state).
    run(["make", "task-start", f"TASK={TASK_ID}"], root, env=env)
    assert "status: in-progress" in task_file.read_text(encoding="utf-8")

    handoff_d = agent_json(root, env, "handoff", "--task", TASK_ID, "--format", "json")
    assert (
        handoff_d["task"]["id"],
        handoff_d["worktree"]["branch"],
        handoff_d["worktree"]["path"],
        handoff_d["worktree"]["claim_task_id"],
    ) == identity_a

    # Focus the repair on the failing surface without hiding the full branch.
    repair_focus = [feature_path, f"src/{package_name(root)}/__init__.py"]
    repair_resume = agent_json(
        root,
        env,
        "context",
        "--task",
        TASK_ID,
        "--mode",
        "resume",
        "--format",
        "json",
        "--focus",
        *repair_focus,
    )
    assert len(repair_resume["changed_files"]) >= 30
    assert set(repair_focus) <= set(repair_resume["focused_loaded_files"])

    # Fix the exhaustive-contract violation the local gate could not see by
    # re-exporting the feature from the package root.
    init_path = root / "src" / package_name(root) / "__init__.py"
    init_body = init_path.read_text(encoding="utf-8").replace(
        '__all__ = ["__version__"]',
        '__all__ = ["build_greeting", "__version__"]',
    )
    init_path.write_text(
        "from .greeting import build_greeting\n\n" + init_body, encoding="utf-8"
    )

    focused_checks()
    local_pre_review()
    run(["make", "task-review", f"TASK={TASK_ID}"], root, env=env)

    # Push to the same PR (same branch, same task association), then the
    # exhaustive CI proxy passes.
    run(["make", "pr-validate"], root, env=pr_env)
    exhaustive_ci(expect_success=True)

    # ----------------------------------------------------------------- Invariants
    # Exactly one pre-review gate per review cycle, never duplicated with a manual
    # full gate, and never the exhaustive release gate.
    assert metrics["local_pre_review_invocations"] == 2
    assert metrics["manual_full_gate_invocations"] == 0
    assert metrics["exhaustive_ci_invocations"] == 2
    assert metrics["focused_check_invocations"] >= 2

    # One task -> one branch -> one worktree -> one claim -> one PR association.
    final_handoff = agent_json(root, env, "handoff", "--task", TASK_ID, "--format", "json")
    assert final_handoff["worktree"]["claim_task_id"] == TASK_ID
    assert final_handoff["worktree"]["branch"] == BRANCH
    assert task_file.exists()
    # No persistent session/CI state: the task record is the only durable record.
    assert "T-002" not in state_yaml.read_text(encoding="utf-8")
    assert "ci-failed" not in task_file.read_text(encoding="utf-8")
