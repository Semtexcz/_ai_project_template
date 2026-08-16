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
        raise AssertionError(f"Command unexpectedly passed: {' '.join(command)}")
    return result


def copy_project(tmp_path: Path, *, project_type: str = "script") -> Path:
    generated = tmp_path / project_type
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
            f"project_name=Agent {project_type}",
            "--data",
            f"project_type={project_type}",
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
    if project_type == "script":
        run(["make", "setup"], generated, env=env)
    run(["make", "sync-project-docs"], generated, env=env)
    return generated


def complete_initial_task(root: Path) -> None:
    task = root / "project" / "tasks" / "T-001-initialize-project.md"
    text = task.read_text(encoding="utf-8")
    text = text.replace("- [ ]", "- [x]")
    text = text.replace("`make validate-project`", "`make validate-project` passed")
    text = text.replace("Project initialization pending.", "Project initialization completed.")
    task.write_text(text, encoding="utf-8")
    run(["make", "task-complete", "TASK=T-001"], root)


def parse_make_json(stdout: str) -> dict[str, object]:
    payload, _ = json.JSONDecoder().raw_decode(stdout[stdout.index("{") :])
    return payload


def write_task(
    root: Path,
    task_id: str,
    *,
    status: str = "backlog",
    approval_level: str = "A0",
    approval_status: str = "not-required",
    checked: bool = False,
) -> Path:
    checkbox = "x" if checked else " "
    path = root / "project" / "tasks" / f"{task_id}-agent-workflow.md"
    path.write_text(
        f"""---
id: {task_id}
title: Add a tested public greeting function
status: {status}
priority: 1
milestone: M-01
depends_on: []
approval_level: {approval_level}
approval_status: {approval_status}
approved_by:
approved_at:
blocked_reason:
unblock_action:
---

# {task_id}: Add a Tested Public Greeting Function

## Goal

Expose a small public greeting function.

## Context

Agent workflow integration test fixture.

## Scope

- Add a greeting function.
- Add a matching test.

## Out of Scope

- Runtime or infrastructure changes.

## Acceptance Criteria

- [{checkbox}] Greeting function returns a personalized greeting.

## Verification

`make check` pending.

## Documentation Impact

No separate documentation required.

## Completion Notes

Pending.
""",
        encoding="utf-8",
    )
    return path


def complete_task_notes(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = text.replace("- [ ] Greeting function", "- [x] Greeting function")
    text = text.replace("`make check` pending.", "`make check` passed.")
    text = text.replace("Pending.", "Implemented and verified.")
    path.write_text(text, encoding="utf-8")


def test_script_local_a0_one_task_workflow(tmp_path: Path) -> None:
    root = copy_project(tmp_path, project_type="script")
    run(["make", "validate-project"], root)
    run(["make", "validate-agent-skills"], root)
    assert "Next action" in run(["make", "agent-status"], root).stdout

    task_path = write_task(root, "T-002")
    complete_initial_task(root)
    run(["make", "task-ready", "TASK=T-002"], root)
    run(["make", "agent-pre-task", "TASK=T-002"], root)
    run(["make", "task-start", "TASK=T-002"], root)

    context = parse_make_json(run(["make", "agent-context", "TASK=T-002", "FORMAT=json"], root).stdout)
    files = set(context["files"])
    assert "AGENTS.md" in files
    assert "project/state.yaml" in files
    assert "project/tasks/T-002-agent-workflow.md" in files
    assert any(path.startswith("src/") for path in files)
    assert any(path.startswith("tests/") for path in files)
    assert not any(".env" in path or ".git" in path or "dist/" in path for path in files)

    package = next((root / "src").iterdir())
    init_path = package / "__init__.py"
    init_path.write_text(
        init_path.read_text(encoding="utf-8")
        + '\n\ndef greeting(name: str) -> str:\n    return f"Hello, {name}!"\n',
        encoding="utf-8",
    )
    (root / "tests" / "test_greeting.py").write_text(
        "from " + package.name + " import greeting\n\n\n"
        "def test_greeting() -> None:\n"
        '    assert greeting("Ada") == "Hello, Ada!"\n',
        encoding="utf-8",
    )

    run(["make", "check"], root)
    run(["make", "agent-pre-review", "TASK=T-002"], root)
    complete_task_notes(task_path)
    run(["make", "task-complete", "TASK=T-002"], root)
    run(["make", "agent-post-task", "TASK=T-002"], root)
    assert "Active task | None" in run(["make", "project-status"], root).stdout
    run(["make", "validate-project"], root)


def test_a1_and_a2_approval_boundaries(tmp_path: Path) -> None:
    root = copy_project(tmp_path, project_type="script")
    complete_initial_task(root)
    a1_path = write_task(root, "T-002", approval_level="A1", approval_status="pending")
    run(["make", "task-ready", "TASK=T-002"], root)
    run(["make", "task-start", "TASK=T-002"], root)
    complete_task_notes(a1_path)
    run(["make", "task-review", "TASK=T-002"], root)
    result = run(["make", "task-complete", "TASK=T-002"], root, expect_success=False)
    assert "Human A1 approval is required" in result.stdout
    run(["make", "task-approve", "TASK=T-002", "APPROVED_BY=Test Human"], root)
    run(["make", "task-complete", "TASK=T-002"], root)

    write_task(root, "T-003", approval_level="A2", approval_status="pending")
    run(["make", "task-ready", "TASK=T-003"], root)
    result = run(["make", "agent-pre-task", "TASK=T-003"], root, expect_success=False)
    assert "Human A2 approval is required" in result.stdout
    result = run(["make", "task-start", "TASK=T-003"], root, expect_success=False)
    assert "Human A2 approval is required" in result.stdout


def test_fullstack_context_routing(tmp_path: Path) -> None:
    root = copy_project(tmp_path, project_type="fullstack")
    complete_initial_task(root)
    write_task(root, "T-002")
    run(["make", "task-ready", "TASK=T-002"], root)
    context = parse_make_json(run(["make", "agent-context", "TASK=T-002", "FORMAT=json"], root).stdout)
    files = set(context["files"])
    assert "backend/src/app/main.py" in files
    assert "frontend/package.json" in files
    assert not any("node_modules" in path or ".env" in path for path in files)


def test_agent_negative_scenarios(tmp_path: Path) -> None:
    root = copy_project(tmp_path, project_type="script")
    skill = root / ".agents" / "managed" / "skills" / "prepare-task" / "SKILL.md"
    skill.write_text(skill.read_text(encoding="utf-8").replace("version: 1", "version: 2"), encoding="utf-8")
    result = run(["make", "validate-agent-skills"], root, expect_success=False)
    assert "version must be 1" in result.stdout

    skill.write_text(skill.read_text(encoding="utf-8").replace("version: 2", "version: 1"), encoding="utf-8")
    (root / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
    context_map = root / ".agents" / "context-map.yaml"
    context_map.write_text(
        context_map.read_text(encoding="utf-8").replace("  - AGENTS.md", "  - AGENTS.md\n  - .env"),
        encoding="utf-8",
    )
    result = run(["make", "agent-context", "TASK=T-001"], root, expect_success=False)
    assert "Sensitive or excluded file .env" in result.stdout

    model = root / ".agents" / "skills" / "conventional-commit" / "agents" / "model.yaml"
    model.write_text(model.read_text(encoding="utf-8").replace("gpt-5-mini", "gpt-5"), encoding="utf-8")
    result = run(["make", "validate-agent-skills"], root, expect_success=False)
    assert "must use a cheap model" in result.stdout
