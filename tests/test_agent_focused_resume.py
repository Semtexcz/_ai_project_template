"""Focused tests for the optional, ephemeral FOCUS working-set selector (issue #28).

These tests exercise the real generated tooling inside throwaway managed
projects. They prove the core invariant ``branch scope != session working set``:
the complete branch change set stays authoritative and observable, while an
explicit ``FOCUS`` selects only the files a fresh resume session eagerly loads.
Focus is request input, never persisted, and never changes routing, checks,
governance, or safety.
"""

from __future__ import annotations

import importlib.util
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
depends_on: []
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

Focused-resume fixture.

## Scope

- Implement the scoped change.

## Out of Scope

- Unrelated work.

## Acceptance Criteria

- [ ] The first criterion still needs work.

## Verification

`make check` pending.

## Documentation Impact

Handled by the fixture.

## Completion Notes

Pending.
"""

# A realistic cross-cutting change set: 32 files spread across the generated
# project's tools, docs, agent layer, tests, and source surfaces.
LARGE_CHANGE_FILES = [
    *(f"tools/mod_{index:02d}.py" for index in range(8)),
    *(f"docs/note-{index:02d}.md" for index in range(6)),
    *(f".agents/skills-notes/note-{index:02d}.md" for index in range(6)),
    *(f"tests/test_area_{index:02d}.py" for index in range(6)),
    *(f"src/area_{index:02d}.py" for index in range(6)),
]


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


def git(
    command: list[str], cwd: Path, *, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return run(
        [
            "git",
            "-c",
            "user.name=Focus Test",
            "-c",
            "user.email=focus@example.com",
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
            f"project_name=Focus {name}",
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


def prepare(
    source: Path,
    tmp_path: Path,
    name: str,
    *,
    task_id: str = "T-002",
    baseline_files: tuple[str, ...] = (),
    change_files: tuple[str, ...] = (),
) -> Path:
    """Copy the rendered project, add a task branch, and commit the change set.

    The task record, baseline files, and the (optionally large) change set are
    all committed on the task branch, so the branch diff the resolver reports is
    exactly that set while the worktree itself stays clean.
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
    branch = f"task/{task_id}-focus-fixture"
    git(["checkout", "-q", "-b", branch], root)
    task_path = root / "project" / "tasks" / f"{task_id}-focus-fixture.md"
    task_path.write_text(
        TASK_TEMPLATE.format(
            task_id=task_id, title="Add focused resume", status="in-progress"
        ),
        encoding="utf-8",
    )
    for relative in change_files:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.suffix == ".md":
            target.write_text(f"# {relative}\n", encoding="utf-8")
        else:
            target.write_text("value = 1\n", encoding="utf-8")
    git(["add", "-A"], root)
    git(["commit", "-q", "-m", "feat: fixture change set"], root)
    return root


def context_payload(
    root: Path,
    *extra: str,
    task_id: str = "T-002",
    expect_success: bool = True,
) -> tuple[str, dict[str, object]]:
    result = run(
        [
            sys.executable,
            "tools/agent.py",
            "context",
            "--task",
            task_id,
            "--format",
            "json",
            *extra,
        ],
        root,
        env=env_for(root),
        expect_success=expect_success,
    )
    output = result.stdout + result.stderr
    if not expect_success:
        return output, {}
    payload, _ = json.JSONDecoder().raw_decode(output[output.index("{") :])
    assert isinstance(payload, dict)
    return output, payload


def resume(root: Path, *focus: str, task_id: str = "T-002") -> dict[str, object]:
    extra = ["--mode", "resume"]
    if focus:
        extra += ["--focus", *focus]
    return context_payload(root, *extra, task_id=task_id)[1]


@pytest.fixture(scope="module")
def managed_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return copy_project(tmp_path_factory.mktemp("agent-focus"), "managed-script")


def env_for(root: Path) -> dict[str, str]:
    return {
        **os.environ,
        "PYTHONPATH": str(root / "tools"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def test_exact_focus_files_are_eagerly_loaded(
    managed_project: Path, tmp_path: Path
) -> None:
    root = prepare(
        managed_project,
        tmp_path,
        "exact-focus",
        change_files=("tools/mod_00.py", "docs/note-00.md"),
    )
    payload = resume(root, "tools/mod_00.py", "docs/note-00.md")
    eager = set(payload["files"])
    assert {"tools/mod_00.py", "docs/note-00.md"} <= eager
    assert payload["focused_files"] == ["docs/note-00.md", "tools/mod_00.py"]
    assert payload["focused_loaded_files"] == payload["focused_files"]
    assert payload["metrics"]["focused_loaded_files_count"] == 2


def test_unchanged_file_can_be_explicitly_focused(
    managed_project: Path, tmp_path: Path
) -> None:
    root = prepare(
        managed_project,
        tmp_path,
        "non-changed-focus",
        baseline_files=("tests/test_baseline_helper.py",),
        change_files=("tools/mod_00.py",),
    )
    changed = set(context_payload(root, "--mode", "resume")[1]["changed_files"])
    assert "tests/test_baseline_helper.py" not in changed
    payload = resume(root, "tools/mod_00.py", "tests/test_baseline_helper.py")
    assert "tests/test_baseline_helper.py" in payload["files"]
    assert payload["focused_files"] == [
        "tests/test_baseline_helper.py",
        "tools/mod_00.py",
    ]


@pytest.mark.parametrize(
    "spec",
    [
        ("../outside.py", "cannot traverse"),
        ("/absolute/path.py", "cannot traverse"),
        ("does/not/exist.py", "does not exist"),
        ("secrets.txt", "sensitive or excluded"),
        ("dist/app.js", "sensitive or excluded"),
        ("tests", "directory"),
    ],
)
def test_invalid_focus_paths_are_rejected(
    managed_project: Path, tmp_path: Path, spec: tuple[str, str]
) -> None:
    focus, expected = spec
    root = prepare(managed_project, tmp_path, f"invalid-{abs(hash(focus))}")
    (root / "secrets.txt").write_text("token\n", encoding="utf-8")
    (root / "dist").mkdir(exist_ok=True)
    (root / "dist" / "app.js").write_text("x\n", encoding="utf-8")
    output, _ = context_payload(
        root, "--mode", "resume", "--focus", focus, expect_success=False
    )
    assert expected in output


def test_escaping_symlink_focus_is_rejected(
    managed_project: Path, tmp_path: Path
) -> None:
    root = prepare(managed_project, tmp_path, "symlink-escape")
    link = root / "escape.py"
    try:
        link.symlink_to("/etc/hostname")
    except OSError:
        pytest.skip("symlinks are unavailable on this filesystem")
    output, _ = context_payload(
        root, "--mode", "resume", "--focus", "escape.py", expect_success=False
    )
    assert "outside the project root" in output


def test_dot_prefix_focus_cannot_bypass_exclusion(
    managed_project: Path, tmp_path: Path
) -> None:
    # The user spelling "./dist/app.js" resolves to the excluded "dist/app.js";
    # the policy must apply to the resolved target, not the raw spelling.
    root = prepare(managed_project, tmp_path, "dot-prefix-exclusion")
    (root / "dist").mkdir(exist_ok=True)
    (root / "dist" / "app.js").write_text("built\n", encoding="utf-8")
    output, _ = context_payload(
        root, "--mode", "resume", "--focus", "./dist/app.js", expect_success=False
    )
    assert "sensitive or excluded" in output


def test_dot_prefixed_focus_target_uses_canonical_default_policy(
    managed_project: Path, tmp_path: Path
) -> None:
    # Seam-level regression: the resolver's own default exclusion policy must
    # apply to the resolved target, so a dot-prefixed spelling of an excluded
    # path cannot bypass it even when no configured pattern covers the spelling.
    root = prepare(managed_project, tmp_path, "canonical-default-policy")
    (root / "dist").mkdir(exist_ok=True)
    (root / "dist" / "app.js").write_text("built\n", encoding="utf-8")
    spec = importlib.util.spec_from_file_location(
        "focus_policy_under_test", root / "tools" / "agent.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    previous = os.getcwd()
    os.chdir(root)
    try:
        spec.loader.exec_module(module)
        module.ROOT = root
        module.AGENTS_DIR = root / ".agents"
        with pytest.raises(module.AgentError, match="sensitive or excluded"):
            module.validate_focus_paths(["./dist/app.js"], list(module.DEFAULT_EXCLUDES))
    finally:
        os.chdir(previous)


def test_in_repo_symlink_to_excluded_target_is_rejected(
    managed_project: Path, tmp_path: Path
) -> None:
    root = prepare(managed_project, tmp_path, "symlink-excluded-target")
    (root / "dist").mkdir(exist_ok=True)
    (root / "dist" / "app.js").write_text("built\n", encoding="utf-8")
    alias = root / "safe-alias.js"
    try:
        alias.symlink_to(root / "dist" / "app.js")
    except OSError:
        pytest.skip("symlinks are unavailable on this filesystem")
    output, _ = context_payload(
        root, "--mode", "resume", "--focus", "safe-alias.js", expect_success=False
    )
    assert "sensitive or excluded" in output


def test_in_repo_symlink_to_sensitive_target_is_rejected(
    managed_project: Path, tmp_path: Path
) -> None:
    root = prepare(managed_project, tmp_path, "symlink-sensitive-target")
    (root / ".env").write_text("SECRET=1\n", encoding="utf-8")
    alias = root / "safe-alias"
    try:
        alias.symlink_to(root / ".env")
    except OSError:
        pytest.skip("symlinks are unavailable on this filesystem")
    output, _ = context_payload(
        root, "--mode", "resume", "--focus", "safe-alias", expect_success=False
    )
    assert "sensitive or excluded" in output


def test_in_repo_symlink_to_valid_target_uses_canonical_identity(
    managed_project: Path, tmp_path: Path
) -> None:
    root = prepare(
        managed_project, tmp_path, "symlink-valid-target", change_files=("tools/a.py",)
    )
    alias = root / "alias.py"
    try:
        alias.symlink_to(root / "tools" / "a.py")
    except OSError:
        pytest.skip("symlinks are unavailable on this filesystem")
    payload = resume(root, "alias.py")
    # The alias inherits its target's canonical repository-relative identity.
    assert payload["focused_files"] == ["tools/a.py"]
    assert payload["files"].count("tools/a.py") == 1


def test_equivalent_focus_spellings_deduplicate(
    managed_project: Path, tmp_path: Path
) -> None:
    root = prepare(
        managed_project, tmp_path, "canonical-dedup", change_files=("tools/a.py",)
    )
    payload = resume(root, "tools/a.py", "./tools/a.py", "tools//a.py")
    assert payload["focused_files"] == ["tools/a.py"]
    assert payload["metrics"]["focused_requested_files_count"] == 1
    assert payload["metrics"]["focused_loaded_files_count"] == 1
    # The canonical file consumes the eager budget exactly once.
    assert payload["files"].count("tools/a.py") == 1


def test_focus_is_rejected_in_non_resume_mode(
    managed_project: Path, tmp_path: Path
) -> None:
    root = prepare(
        managed_project, tmp_path, "wrong-mode", change_files=("tools/mod_00.py",)
    )
    output, _ = context_payload(
        root, "--mode", "new", "--focus", "tools/mod_00.py", expect_success=False
    )
    assert "FOCUS is only supported with MODE=resume" in output


def test_complete_branch_stays_visible_with_a_large_fixture(
    managed_project: Path, tmp_path: Path
) -> None:
    root = prepare(
        managed_project,
        tmp_path,
        "large-fixture",
        baseline_files=("tests/test_baseline_helper.py",),
        change_files=tuple(LARGE_CHANGE_FILES),
    )
    full = context_payload(root, "--mode", "resume")[1]
    assert full["metrics"]["branch_changed_files_count"] >= 30

    focus = ["tools/mod_00.py", "docs/note-00.md", "tests/test_baseline_helper.py"]
    focused = resume(root, *focus)
    # Branch scope stays complete and machine-readable.
    assert focused["changed_files"] == full["changed_files"]
    assert focused["metrics"]["branch_changed_files_count"] >= 30
    # The eager working set is only the explicit focus plus protected/routed context.
    eager = set(focused["files"])
    assert set(focus) <= eager
    assert "tools/mod_01.py" not in eager
    assert "src/area_00.py" not in eager
    assert focused["metrics"]["focused_loaded_files_count"] == len(focus)
    assert focused["metrics"]["eager_files_count"] <= 8
    assert focused["metrics"]["total_bytes"] <= 40_000


def test_unfocused_changed_files_report_outside_focus(
    managed_project: Path, tmp_path: Path
) -> None:
    root = prepare(
        managed_project,
        tmp_path,
        "outside-focus-reason",
        change_files=("tools/mod_00.py", "tools/mod_01.py"),
    )
    payload = resume(root, "tools/mod_00.py")
    omitted = {item["path"]: item["reason"] for item in payload["omitted"]}
    assert omitted.get("tools/mod_01.py") == "outside focus"
    assert "tools/mod_00.py" not in omitted
    assert set(payload["search_roots"]) >= {"tools", "tests", "src"}


def test_recommended_checks_ignore_focus(managed_project: Path, tmp_path: Path) -> None:
    root = prepare(
        managed_project,
        tmp_path,
        "checks-parity",
        change_files=("tools/mod_00.py", "docs/note-00.md", "src/area_00.py"),
    )
    full = context_payload(root, "--mode", "resume")[1]
    focused = resume(root, "tools/mod_00.py")
    assert full["recommended_checks"] == focused["recommended_checks"]
    assert focused["recommended_checks"]


def test_governance_invariants_survive_focus(
    managed_project: Path, tmp_path: Path
) -> None:
    root = prepare(
        managed_project, tmp_path, "governance", change_files=("tools/mod_00.py",)
    )
    output, _ = context_payload(
        root,
        "--mode",
        "resume",
        "--focus",
        "tools/mod_00.py",
        task_id="T-999",
        expect_success=False,
    )
    assert "owns T-002" in output


def test_focus_is_deterministic(managed_project: Path, tmp_path: Path) -> None:
    root = prepare(
        managed_project, tmp_path, "determinism", change_files=("tools/mod_00.py",)
    )
    first = context_payload(root, "--mode", "resume", "--focus", "tools/mod_00.py")[0]
    second = context_payload(root, "--mode", "resume", "--focus", "tools/mod_00.py")[0]
    assert first == second


def test_no_focus_resume_is_backward_compatible(
    managed_project: Path, tmp_path: Path
) -> None:
    root = prepare(
        managed_project, tmp_path, "no-focus", change_files=("tools/mod_00.py",)
    )
    payload = context_payload(root, "--mode", "resume")[1]
    assert payload["focus_enabled"] is False
    assert payload["focused_files"] == []
    assert payload["metrics"]["focused_requested_files_count"] == 0
    # Existing behavior: non-deleted changed files are eager candidates.
    assert "tools/mod_00.py" in payload["files"]


def test_small_task_does_not_require_focus(
    managed_project: Path, tmp_path: Path
) -> None:
    root = prepare(
        managed_project, tmp_path, "small-task", change_files=("tools/mod_00.py",)
    )
    payload = context_payload(root, "--mode", "resume")[1]
    assert payload["recommended_checks"]
    assert "tools/mod_00.py" in payload["files"]


def test_structured_python_api_accepts_focus(
    managed_project: Path, tmp_path: Path
) -> None:
    root = prepare(
        managed_project, tmp_path, "python-api", change_files=("tools/mod_00.py",)
    )
    spec = importlib.util.spec_from_file_location(
        "focus_api_under_test", root / "tools" / "agent.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    previous = os.getcwd()
    os.chdir(root)
    try:
        spec.loader.exec_module(module)
        module.ROOT = root
        module.AGENTS_DIR = root / ".agents"
        payload = module.resolve_context(
            "T-002", mode="resume", focus=["tools/mod_00.py"]
        )
        assert payload["focused_files"] == ["tools/mod_00.py"]
        assert "tools/mod_00.py" in payload["files"]
        with pytest.raises(module.AgentError, match="MODE=resume"):
            module.resolve_context("T-002", mode="new", focus=["tools/mod_00.py"])
    finally:
        os.chdir(previous)


def test_handoff_carries_no_focus_state(managed_project: Path, tmp_path: Path) -> None:
    root = prepare(
        managed_project, tmp_path, "handoff-compat", change_files=("tools/mod_00.py",)
    )
    claim = (
        "from pathlib import Path\n"
        "from project_tool import claims\n"
        "claims.create_claim('T-002', 'task/T-002-focus-fixture', Path.cwd())\n"
    )
    run([sys.executable, "-c", claim], root, env=env_for(root))
    result = run(
        [
            sys.executable,
            "tools/agent.py",
            "handoff",
            "--task",
            "T-002",
            "--format",
            "json",
        ],
        root,
        env=env_for(root),
    )
    payload, _ = json.JSONDecoder().raw_decode(
        result.stdout[result.stdout.index("{") :]
    )

    def has_key(node: object, name: str) -> bool:
        if isinstance(node, dict):
            return name in node or any(has_key(value, name) for value in node.values())
        if isinstance(node, list):
            return any(has_key(value, name) for value in node)
        return False

    # The handoff payload owns no focus state: FOCUS stays an agent-context input.
    assert not has_key(payload, "focus")
    assert not has_key(payload, "focused_files")
    assert not has_key(payload, "focus_enabled")
    assert payload["metrics"]["recommended_checks_count"] >= 1
