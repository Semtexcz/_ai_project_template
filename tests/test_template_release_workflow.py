from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_project_tool() -> Any:
    spec = importlib.util.spec_from_file_location(
        "project_tool",
        ROOT / "template" / "tools" / "project.py",
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Could not load project tool module.")
    module = importlib.util.module_from_spec(spec)
    sys.modules["project_tool"] = module
    spec.loader.exec_module(module)
    return module


def run(
    command: list[str],
    cwd: Path,
    *,
    expect_success: bool = True,
) -> subprocess.CompletedProcess[str]:
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


def copy_template_repo(target: Path) -> None:
    shutil.copytree(
        ROOT,
        target,
        ignore=shutil.ignore_patterns(
            ".git",
            ".venv",
            ".pytest_cache",
            ".ruff_cache",
            "__pycache__",
        ),
    )
    makefile = target / "Makefile"
    text = makefile.read_text()
    text = text.replace(
        "release-check: validate-project validate-template-docs validate-agent-skills\n"
        "\tUV_CACHE_DIR=$${UV_CACHE_DIR:-/tmp/uv-cache} UV_LINK_MODE=$${UV_LINK_MODE:-copy} uv run pytest\n",
        "release-check:\n"
        "\t@echo release-check fixture\n",
    )
    makefile.write_text(text)


def init_release_repo(path: Path) -> None:
    run(["git", "init", "-q"], path)
    run(["git", "checkout", "-q", "-b", "main"], path)
    run(["git", "config", "user.email", "release-test@example.invalid"], path)
    run(["git", "config", "user.name", "Release Test"], path)
    run(["git", "add", "-A"], path)
    run(["git", "commit", "-q", "-m", "initial template"], path)


def state_text(path: Path) -> str:
    return (path / "project" / "state.yaml").read_text()


def test_template_version_bumps() -> None:
    project_tool = load_project_tool()

    assert project_tool.bump_template_version("v1.1.1", "patch") == "v1.1.2"
    assert project_tool.bump_template_version("v1.1.1", "minor") == "v1.2.0"
    assert project_tool.bump_template_version("v1.1.1", "major") == "v2.0.0"


def test_invalid_template_version_fails_clearly() -> None:
    project_tool = load_project_tool()

    try:
        project_tool.bump_template_version("1.1.1", "patch")
    except project_tool.ProjectError as exc:
        assert "vX.Y.Z" in str(exc)
    else:
        raise AssertionError("Invalid template version unexpectedly passed.")


def test_template_release_dry_run_does_not_mutate(tmp_path: Path) -> None:
    repo = tmp_path / "template"
    copy_template_repo(repo)
    init_release_repo(repo)
    before = state_text(repo)

    result = run(["make", "template-release", "DRY_RUN=1"], repo)

    assert "Template release: v1.1.1 -> v1.1.2 (patch)" in result.stdout
    assert "Dry run only" in result.stdout
    assert state_text(repo) == before
    assert run(["git", "tag", "--list"], repo).stdout.strip() == ""
    assert run(["git", "status", "--porcelain"], repo).stdout.strip() == ""


def test_template_release_updates_state_commits_and_tags(tmp_path: Path) -> None:
    repo = tmp_path / "template"
    copy_template_repo(repo)
    init_release_repo(repo)

    result = run(["make", "template-release", "BUMP=minor"], repo)

    assert "Created template release v1.2.0" in result.stdout
    assert "version: v1.2.0" in state_text(repo)
    subject = run(["git", "log", "-1", "--pretty=%s"], repo).stdout.strip()
    assert subject == "chore(release): v1.2.0"
    assert run(["git", "tag", "--list", "v1.2.0"], repo).stdout.strip() == "v1.2.0"
    assert run(["git", "status", "--porcelain"], repo).stdout.strip() == ""


def test_template_release_existing_tag_fails_before_mutation(tmp_path: Path) -> None:
    repo = tmp_path / "template"
    copy_template_repo(repo)
    init_release_repo(repo)
    run(["git", "tag", "v1.1.2"], repo)
    before = state_text(repo)

    result = run(["make", "template-release"], repo, expect_success=False)

    assert "Git tag v1.1.2 already exists" in result.stdout
    assert state_text(repo) == before


def test_template_release_dirty_worktree_fails_before_mutation(tmp_path: Path) -> None:
    repo = tmp_path / "template"
    copy_template_repo(repo)
    init_release_repo(repo)
    before = state_text(repo)
    (repo / "docs" / "template-development.md").write_text("dirty\n")

    result = run(["make", "template-release"], repo, expect_success=False)

    assert "Git worktree must be clean" in result.stdout
    assert state_text(repo) == before
