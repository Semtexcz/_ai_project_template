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
AGENT_TOOL = ROOT / "template" / "tools" / "agent.py"


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
    return run(["git", *command], cwd, expect_success=check)


def copy_project(
    tmp_path: Path,
    name: str,
    *,
    project_type: str,
    governance: str,
    runtime_level: str = "local",
) -> Path:
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
            f"project_name=Agent Efficiency {name}",
            "--data",
            f"project_type={project_type}",
            "--data",
            f"runtime_level={runtime_level}",
            "--data",
            f"governance={governance}",
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
def managed_script(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return copy_project(
        tmp_path_factory.mktemp("agent-efficiency"),
        "managed-script",
        project_type="script",
        governance="managed",
    )


def fresh_copy(managed_script: Path, tmp_path: Path, name: str) -> Path:
    target = tmp_path / name
    shutil.copytree(managed_script, target)
    return target


def context_json(root: Path, *extra: str) -> dict[str, object]:
    result = run(
        [
            sys.executable,
            "tools/agent.py",
            "context",
            "--task",
            "T-001",
            "--format",
            "json",
            *extra,
        ],
        root,
    )
    return json.loads(result.stdout)


def init_git_repo(root: Path, *, with_origin: bool = True) -> Path | None:
    git(["init", "-b", "main"], root)
    git(["add", "-A"], root)
    git(
        [
            "-c",
            "user.name=Test Agent",
            "-c",
            "user.email=agent@example.com",
            "commit",
            "-m",
            "chore: baseline",
        ],
        root,
    )
    if not with_origin:
        return None
    origin = root.parent / f"{root.name}-origin.git"
    run(["git", "init", "--bare", "-b", "main", str(origin)], root)
    git(["remote", "add", "origin", str(origin)], root)
    git(["push", "-u", "origin", "main"], root)
    return origin


def load_agent_module() -> object:
    spec = importlib.util.spec_from_file_location(
        "agent_efficiency_under_test", AGENT_TOOL
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_skill_reads_route_context_and_stay_isolated(
    managed_script: Path, tmp_path: Path
) -> None:
    root = fresh_copy(managed_script, tmp_path, "skill-routing")
    default = context_json(root)
    assert default["skill"] is None

    implement = context_json(root, "--skill", "implement-change")
    implement_files = set(implement["files"])
    assert ".agents/context-map.yaml" in implement_files
    assert "Makefile" in implement_files
    # Unrelated skill metadata must not leak into implement-change context.
    assert not any(
        ".agents/skills/conventional-commit/" in path for path in implement_files
    )

    commit = context_json(root, "--skill", "conventional-commit")
    commit_files = set(commit["files"])
    assert ".agents/skills/conventional-commit/agents/model.yaml" in commit_files
    assert (
        ".agents/skills/conventional-commit/scripts/validate_commit_message.py"
        in commit_files
    )

    # Unknown skills fail clearly with a deterministic error.
    result = run(
        [
            sys.executable,
            "tools/agent.py",
            "context",
            "--task",
            "T-001",
            "--skill",
            "does-not-exist",
        ],
        root,
        expect_success=False,
    )
    assert "does not exist" in result.stdout + result.stderr


def test_directories_are_search_roots_not_recursive_context(
    managed_script: Path, tmp_path: Path
) -> None:
    root = fresh_copy(managed_script, tmp_path, "roots-not-context")
    context = context_json(root)
    files = set(context["files"])
    roots = set(context["search_roots"])
    assert "src" in roots
    assert "tests" in roots
    assert "pyproject.toml" in files
    assert not any(path.startswith("src/") for path in files)
    assert not any(path.startswith("tests/") for path in files)
    # Default mode loads narrow profile files; resume mode does not.
    resume = context_json(root, "--mode", "resume")
    resume_files = set(resume["files"])
    assert resume["mode"] == "resume"
    assert "pyproject.toml" not in resume_files
    assert not any(path.startswith("src/") for path in resume_files)


def test_budget_file_limit_omits_and_reports(
    managed_script: Path, tmp_path: Path
) -> None:
    root = fresh_copy(managed_script, tmp_path, "file-budget")
    map_path = root / ".agents" / "context-map.yaml"
    map_path.write_text(
        map_path.read_text(encoding="utf-8").replace("max_files: 20", "max_files: 5"),
        encoding="utf-8",
    )
    context = context_json(root)
    files = context["files"]
    assert len(files) <= 5
    # Protected task/bootstrap material is never dropped.
    assert "AGENTS.md" in files
    assert any("project/tasks/T-001-initialize-project.md" in path for path in files)
    omitted = context["omitted"]
    assert omitted
    assert any(item["reason"] == "file budget" for item in omitted)

    second = context_json(root)
    assert files == second["files"]
    assert omitted == second["omitted"]


def test_budget_byte_limit_omits_large_changed_file(
    managed_script: Path, tmp_path: Path
) -> None:
    root = fresh_copy(managed_script, tmp_path, "byte-budget")
    init_git_repo(root, with_origin=False)
    large = root / "large-change.txt"
    large.write_text("x" * 6000, encoding="utf-8")
    protected_bytes = sum(
        (root / path).stat().st_size
        for path in ["AGENTS.md", "project/tasks/T-001-initialize-project.md"]
    )
    map_path = root / ".agents" / "context-map.yaml"
    map_path.write_text(
        map_path.read_text(encoding="utf-8").replace(
            "max_bytes: 120000", f"max_bytes: {protected_bytes + 2000}"
        ),
        encoding="utf-8",
    )
    context = context_json(root)
    assert "large-change.txt" in context["changed_files"]
    assert context["total_bytes"] <= protected_bytes + 2000
    assert any(
        item["path"] == "large-change.txt" and item["reason"] == "byte budget"
        for item in context["omitted"]
    )


def test_branch_aware_change_detection(managed_script: Path, tmp_path: Path) -> None:
    # Unstaged, staged, and untracked files are detected without a branch base.
    root = fresh_copy(managed_script, tmp_path, "worktree-changes")
    init_git_repo(root, with_origin=False)
    (root / "README.md").write_text((root / "README.md").read_text() + "\nunstaged\n")
    (root / "staged.txt").write_text("staged\n", encoding="utf-8")
    git(["add", "staged.txt"], root)
    (root / "untracked.txt").write_text("untracked\n", encoding="utf-8")
    context = context_json(root)
    changed = set(context["changed_files"])
    assert "README.md" in changed
    assert "staged.txt" in changed
    assert "untracked.txt" in changed

    # Committed branch changes survive a clean worktree plus local changes.
    root2 = fresh_copy(managed_script, tmp_path, "branch-committed")
    init_git_repo(root2)
    git(["switch", "-c", "feat/change"], root2)
    (root2 / "docs" / "feature.md").write_text("# Feature\n", encoding="utf-8")
    git(["add", "docs/feature.md"], root2)
    git(
        [
            "-c",
            "user.name=Test Agent",
            "-c",
            "user.email=agent@example.com",
            "commit",
            "-m",
            "docs: add feature note",
        ],
        root2,
    )
    clean = git(["status", "--porcelain"], root2)
    assert clean.stdout.strip() == ""
    context = context_json(root2)
    assert "docs/feature.md" in context["changed_files"]
    (root2 / "local-extra.txt").write_text("extra\n", encoding="utf-8")
    context = context_json(root2)
    assert "docs/feature.md" in context["changed_files"]
    assert "local-extra.txt" in context["changed_files"]

    # Without origin/main the local base still carries the committed branch set.
    root3 = fresh_copy(managed_script, tmp_path, "fallback-base")
    init_git_repo(root3)
    git(["switch", "-c", "feat/fallback"], root3)
    (root3 / "notes.md").write_text("notes\n", encoding="utf-8")
    git(["add", "notes.md"], root3)
    git(
        [
            "-c",
            "user.name=Test Agent",
            "-c",
            "user.email=agent@example.com",
            "commit",
            "-m",
            "docs: fallback note",
        ],
        root3,
    )
    git(["update-ref", "-d", "refs/remotes/origin/main"], root3)
    context = context_json(root3)
    assert "notes.md" in context["changed_files"]


def test_recommended_checks_are_change_aware() -> None:
    agent = load_agent_module()

    def checks_for(changes: list[str]) -> list[str]:
        config = agent.read_yaml(ROOT / ".agents" / "context-map.yaml")
        return agent.recommended_checks(config, changes)

    assert checks_for(["docs/quality.md"]) == ["make validate-template-docs"]
    assert checks_for([".agents/skills/implement-change/SKILL.md"]) == [
        "make validate-agent-skills"
    ]
    assert checks_for(["src/example.py"]) == ["make check"]
    # A clean worktree on a feature branch still routes on the committed diff.
    assert checks_for(["docs/template-development.md"]) == [
        "make validate-template-docs"
    ]
    assert checks_for(["project/tasks/T-001-example.md"]) == ["make validate-project"]
    assert checks_for([]) == ["make check"]


def test_pre_review_runs_one_canonical_gate() -> None:
    text = AGENT_TOOL.read_text(encoding="utf-8")
    marker = "def pre_review("
    body = text[text.index(marker) :]
    body = body[: body.index("\n\ndef ")]
    assert body.count('run_command("make check")') == 1
    assert "validate_agent_skills()" not in body
    assert "make validate-project" not in body
    # The whole tool contains only the single canonical full-gate invocation.
    assert text.count('run_command("make check")') == 1


def test_representative_generated_profiles_render_concise_context(
    tmp_path: Path,
) -> None:
    lightweight = copy_project(
        tmp_path, "script-lightweight", project_type="script", governance="lightweight"
    )
    managed_fullstack = copy_project(
        tmp_path,
        "fullstack-managed",
        project_type="fullstack",
        governance="managed",
        runtime_level="production",
    )

    for generated in [lightweight, managed_fullstack]:
        agents = (generated / "AGENTS.md").read_text(encoding="utf-8")
        assert "Tier 0 bootstrap" in agents
        workflow = (generated / "docs" / "workflow.md").read_text(encoding="utf-8")
        assert "## Agent Context" in workflow
        assert "## Task Records" in workflow
        assert "search_roots" in workflow
        assert "MODE=resume" in workflow
        context_map = (generated / ".agents" / "context-map.yaml").read_text(
            encoding="utf-8"
        )
        assert "schema_version: 2" in context_map
        assert "search_roots:" in context_map
        assert "budget:" in context_map

    # Managed full-stack projects expose profile files and no recursive trees.
    managed_context = context_json(managed_fullstack)
    managed_files = set(managed_context["files"])
    assert "backend/src/app/main.py" in managed_files
    assert "frontend/package.json" in managed_files
    assert not any("node_modules" in path for path in managed_files)
    assert not any(path.startswith("backend/tests/") for path in managed_files)

    # Lightweight projects keep canonical skill validation but no lifecycle CLI.
    lightweight_makefile = (lightweight / "Makefile").read_text(encoding="utf-8")
    assert "agent-context:" not in lightweight_makefile
    assert "validate-agent-skills:" in lightweight_makefile
    assert run(["make", "validate-agent-skills"], lightweight).returncode == 0
